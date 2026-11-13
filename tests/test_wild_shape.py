"""Tests for Druid Wild Shape (Excel tab 9d): logic and UI integration.

Reference: PHB p37.  Covers the form-availability gating by Druid level, the
physical-ability replacement maths, the active-form persistence helper, and the
integration of an active form into :meth:`CharacterModel.derived_stats` (size,
physical ability scores and natural armor) plus save/load round-tripping.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database
from heroforge.logic.wild_shape import (
    active_form_name,
    apply_wild_shape,
    available_forms,
    druid_wild_shape_level,
    wild_shape_ability_adjustments,
)

# ---------------------------------------------------------------------------
# Pure-logic tests (no Qt required)
# ---------------------------------------------------------------------------


def _creature(
    name: str, size: str, ctype: str, hit_dice: str = "1", **scores: int
) -> dict:
    base = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
    base.update(scores)
    return {
        "name": name,
        "size": size,
        "type": ctype,
        "hit_dice": hit_dice,
        "ability_scores": base,
        "natural_armor": 0,
    }


class TestDruidLevel:
    def test_counts_only_druid_levels(self) -> None:
        classes = [("Fighter", 4), ("Druid", 7), ("Rogue", 1)]
        assert druid_wild_shape_level(classes) == 7

    def test_sums_multiple_druid_entries(self) -> None:
        assert druid_wild_shape_level([("Druid", 3), ("druid", 2)]) == 5

    def test_zero_without_druid_levels(self) -> None:
        assert druid_wild_shape_level([("Wizard", 10)]) == 0


class TestAvailableForms:
    @pytest.fixture()
    def catalogue(self) -> list[dict]:
        return [
            _creature("Hawk", "Tiny", "Animal", "1"),
            _creature("Wolf", "Medium", "Animal", "2"),
            _creature("Brown Bear", "Large", "Animal", "6"),
            _creature("Elephant", "Huge", "Animal", "11"),
            _creature("Shambler", "Medium", "Plant", "8"),
            _creature("Air Elemental", "Large", "Elemental", "8"),
            _creature("Griffon", "Medium", "Magical Beast", "7"),
        ]

    def test_no_forms_below_level_5(self, catalogue: list[dict]) -> None:
        assert available_forms(4, catalogue) == []

    def test_level_5_small_and_medium_animals(self, catalogue: list[dict]) -> None:
        names = {c["name"] for c in available_forms(5, catalogue)}
        assert names == {"Wolf"}

    def test_large_animals_at_8(self, catalogue: list[dict]) -> None:
        assert "Brown Bear" not in {c["name"] for c in available_forms(7, catalogue)}
        names = {c["name"] for c in available_forms(8, catalogue)}
        assert "Brown Bear" in names
        assert "Hawk" not in names  # Tiny unlocks at 11

    def test_tiny_animals_at_11(self, catalogue: list[dict]) -> None:
        assert "Hawk" not in {c["name"] for c in available_forms(10, catalogue)}
        assert "Hawk" in {c["name"] for c in available_forms(11, catalogue)}

    def test_plants_at_12(self, catalogue: list[dict]) -> None:
        assert "Shambler" not in {c["name"] for c in available_forms(11, catalogue)}
        assert "Shambler" in {c["name"] for c in available_forms(12, catalogue)}

    def test_plants_share_animal_sizes(self, catalogue: list[dict]) -> None:
        # PHB p37: plant forms follow the animal size restrictions.
        catalogue.append(_creature("Treant", "Huge", "Plant", "7"))
        assert "Treant" not in {c["name"] for c in available_forms(14, catalogue)}
        assert "Treant" in {c["name"] for c in available_forms(15, catalogue)}

    def test_huge_animals_at_15(self, catalogue: list[dict]) -> None:
        assert "Elephant" not in {c["name"] for c in available_forms(14, catalogue)}
        assert "Elephant" in {c["name"] for c in available_forms(15, catalogue)}

    def test_elementals_at_16(self, catalogue: list[dict]) -> None:
        assert "Air Elemental" not in {
            c["name"] for c in available_forms(15, catalogue)
        }
        assert "Air Elemental" in {c["name"] for c in available_forms(16, catalogue)}

    def test_huge_elementals_at_20(self, catalogue: list[dict]) -> None:
        catalogue.append(_creature("Huge Fire Elemental", "Huge", "Elemental"))
        names19 = {c["name"] for c in available_forms(19, catalogue)}
        assert "Huge Fire Elemental" not in names19
        assert "Huge Fire Elemental" in {
            c["name"] for c in available_forms(20, catalogue)
        }

    def test_hit_dice_capped_by_druid_level(self, catalogue: list[dict]) -> None:
        # PHB p37 / workbook WildShapeHDLimit: the form's HD <= druid level.
        catalogue.append(_creature("Dire Bear", "Large", "Animal", "12"))
        for level in range(8, 12):
            names = {c["name"] for c in available_forms(level, catalogue)}
            assert "Dire Bear" not in names, level
        assert "Dire Bear" in {c["name"] for c in available_forms(12, catalogue)}

    def test_hit_dice_parses_leading_integer(self, catalogue: list[dict]) -> None:
        catalogue.append(_creature("Dire Bear", "Large", "Animal", "12d8+51"))
        assert "Dire Bear" not in {c["name"] for c in available_forms(11, catalogue)}
        assert "Dire Bear" in {c["name"] for c in available_forms(12, catalogue)}

    def test_forms_without_hit_dice_excluded(self, catalogue: list[dict]) -> None:
        # Workbook 'Creature Info' CD column requires LEN(HD)>0.
        catalogue.append(_creature("Mystery Cat", "Medium", "Animal", ""))
        assert "Mystery Cat" not in {
            c["name"] for c in available_forms(20, catalogue)
        }

    def test_magical_beasts_never(self, catalogue: list[dict]) -> None:
        # Only the Magical Beast Wild Shape feat grants these (workbook
        # TblWildshapeForms), never druid level alone.
        assert "Griffon" not in {c["name"] for c in available_forms(20, catalogue)}


class TestStatReplacement:
    def test_apply_replaces_physical_retains_mental(self) -> None:
        base = {"STR": 10, "DEX": 12, "CON": 11, "INT": 14, "WIS": 16, "CHA": 8}
        bear = _creature("Bear", "Large", "Animal", STR=21, DEX=13, CON=19, INT=2)
        result = apply_wild_shape(base, bear)
        assert result["STR"] == 21
        assert result["DEX"] == 13
        assert result["CON"] == 19
        # Mental scores are retained from the character, not the form.
        assert result["INT"] == 14
        assert result["WIS"] == 16
        assert result["CHA"] == 8

    def test_ability_adjustments_are_replacement_deltas(self) -> None:
        base = {"STR": 10, "DEX": 12, "CON": 11}
        bear = _creature("Bear", "Large", "Animal", STR=21, DEX=13, CON=19)
        adj = wild_shape_ability_adjustments(base, bear)
        assert adj == {"STR": 11, "DEX": 1, "CON": 8}
        # base + adjustment == form's physical score
        assert base["STR"] + adj["STR"] == 21


class TestActiveFormName:
    def test_returns_name_when_active(self) -> None:
        companions = [
            {
                "companion_type": "wild_shape",
                "creature": "Wolf",
                "notes": json.dumps({"active": True}),
            }
        ]
        assert active_form_name(companions) == "Wolf"

    def test_none_when_inactive(self) -> None:
        companions = [
            {
                "companion_type": "wild_shape",
                "creature": "Wolf",
                "notes": json.dumps({"active": False}),
            }
        ]
        assert active_form_name(companions) is None

    def test_none_without_entry(self) -> None:
        assert active_form_name([{"companion_type": "familiar"}]) is None

    def test_none_with_unparseable_notes(self) -> None:
        companions = [
            {"companion_type": "wild_shape", "creature": "Wolf", "notes": "{bad"}
        ]
        assert active_form_name(companions) is None


# ---------------------------------------------------------------------------
# UI / derived-stats integration (Qt required)
# ---------------------------------------------------------------------------


@pytest.fixture()
def catalog_db(tmp_path: Path) -> Path:
    """Seed a tiny catalogue with creatures spanning several Wild Shape tiers."""
    db_path = tmp_path / "catalog.db"
    initialize_database(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO creatures (name, size, type, subtype, hit_dice, str_score, "
            "dex_score, con_score, int_score, wis_score, cha_score, natural_armor, "
            "speed, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "Wolf",
                    "Medium",
                    "Animal",
                    "",
                    "2d8+4",
                    13,
                    15,
                    15,
                    2,
                    12,
                    6,
                    2,
                    "50 ft.",
                    "MM",
                ),
                (
                    "Dire Bear",
                    "Large",
                    "Animal",
                    "",
                    "12d8+51",
                    31,
                    13,
                    19,
                    2,
                    12,
                    10,
                    7,
                    "40 ft.",
                    "MM",
                ),
                (
                    "Hawk",
                    "Tiny",
                    "Animal",
                    "",
                    "1d8",
                    6,
                    17,
                    10,
                    2,
                    14,
                    6,
                    0,
                    "10 ft., fly 60 ft.",
                    "MM",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def model(qapp: object, catalog_db: Path) -> object:
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(str(catalog_db)))


def _round_trip(character: object, tmp_path: Path) -> object:
    from heroforge.db.character_repo import load_character, save_character
    from heroforge.db.schema import initialize_character_database

    conn = initialize_character_database(tmp_path / "chars.hfc")
    try:
        cid = save_character(conn, character)  # type: ignore[arg-type]
        return load_character(conn, cid)
    finally:
        conn.close()


class TestGetCreature:
    def test_get_creature_exposes_subtype_and_speed(self, catalog_db: Path) -> None:
        from heroforge.db.data_access import GameDataRepository

        repo = GameDataRepository(str(catalog_db))
        wolf = repo.get_creature("wolf")  # case-insensitive
        assert wolf is not None
        assert wolf.size == "Medium"
        assert wolf.speed == "50 ft."
        assert wolf.ability_scores["STR"] == 13

    def test_get_creature_unknown_returns_none(self, catalog_db: Path) -> None:
        from heroforge.db.data_access import GameDataRepository

        repo = GameDataRepository(str(catalog_db))
        assert repo.get_creature("Tarrasque") is None


class TestWildShapeTab:
    def test_low_level_druid_cannot_shape(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 4)]
        tab = WildShapeTab(model=model)
        assert tab._available_forms() == []
        assert tab._select_btn.isEnabled() is False

    def test_available_forms_gated_by_druid_level(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 5)]
        tab = WildShapeTab(model=model)
        names = {c.name for c in tab._available_forms()}
        assert names == {"Wolf"}  # Medium only at level 5

        model.character.classes = [("Druid", 12)]
        tab._refresh_availability()
        names = {c.name for c in tab._available_forms()}
        assert {"Wolf", "Dire Bear", "Hawk"} <= names  # Large 8, Tiny 11

    def test_active_form_changes_derived_stats(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        tab = WildShapeTab(model=model)
        bear = model.game_data().get_creature("Dire Bear")
        tab._form = bear
        tab._form_edit.setText("Dire Bear")
        tab._active_check.setChecked(True)
        tab._sync_to_model()

        ds = model.derived_stats()
        assert ds.size == "Large"
        # Physical scores replaced by the form, mental scores retained.
        assert ds.effective_ability_scores["STR"] == 31
        assert ds.effective_ability_scores["CON"] == 19
        assert ds.effective_ability_scores["INT"] == 10

    def test_inactive_form_does_not_change_stats(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        tab = WildShapeTab(model=model)
        tab._form = model.game_data().get_creature("Dire Bear")
        tab._form_edit.setText("Dire Bear")
        tab._active_check.setChecked(False)
        tab._sync_to_model()

        ds = model.derived_stats()
        assert ds.size == "Medium"
        assert ds.effective_ability_scores["STR"] == 10

    def test_selection_round_trips(self, model: object, tmp_path: Path) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        tab = WildShapeTab(model=model)
        tab._form = model.game_data().get_creature("Dire Bear")
        tab._form_edit.setText("Dire Bear")
        tab._active_check.setChecked(True)
        tab._sync_to_model()

        loaded = _round_trip(model.character, tmp_path)
        entry = next(
            c for c in loaded.companions if c["companion_type"] == "wild_shape"
        )
        assert entry["creature"] == "Dire Bear"
        assert json.loads(entry["notes"])["active"] is True

    def test_sync_from_model_restores_active_form(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        model.character.companions = [
            {
                "companion_type": "wild_shape",
                "name": "",
                "creature": "Wolf",
                "notes": json.dumps({"active": True}),
            }
        ]
        tab = WildShapeTab(model=model)
        assert tab._form_edit.text() == "Wolf"
        assert tab._active_check.isChecked() is True
        assert tab._size_label.text() == "Medium"
        assert tab._speed_label.text() == "50 ft."

    def test_clear_removes_entry(self, model: object) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        tab = WildShapeTab(model=model)
        tab._form = model.game_data().get_creature("Wolf")
        tab._form_edit.setText("Wolf")
        tab._active_check.setChecked(True)
        tab._sync_to_model()
        assert any(
            c["companion_type"] == "wild_shape" for c in model.character.companions
        )

        tab._clear_form()
        assert not any(
            c["companion_type"] == "wild_shape" for c in model.character.companions
        )


class TestFormLossOfLevels:
    """An active form stops applying once the druid can no longer assume it."""

    def _activate_dire_bear(self, model: object) -> object:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        tab = WildShapeTab(model=model)
        tab._form = model.game_data().get_creature("Dire Bear")
        tab._form_edit.setText("Dire Bear")
        tab._refresh_availability()
        tab._active_check.setChecked(True)
        assert model.derived_stats().size == "Large"
        return tab

    @pytest.mark.parametrize(
        "classes", [[("Druid", 4)], [("Druid", 11)], [("Fighter", 12)]]
    )
    def test_derived_stats_ignore_unavailable_form(
        self, model: object, classes: list
    ) -> None:
        self._activate_dire_bear(model)
        model.character.classes = classes
        ds = model.derived_stats()
        assert ds.size == "Medium"
        assert ds.effective_ability_scores["STR"] == 10
        assert ds.effective_ability_scores["CON"] == 10

    def test_loaded_active_form_without_druid_levels_ignored(
        self, model: object
    ) -> None:
        model.character.classes = [("Wizard", 12)]
        model.character.companions = [
            {
                "companion_type": "wild_shape",
                "name": "",
                "creature": "Dire Bear",
                "notes": json.dumps({"active": True}),
            }
        ]
        assert model.derived_stats().size == "Medium"

    def test_tab_unchecks_and_persists_when_form_lost(self, model: object) -> None:
        tab = self._activate_dire_bear(model)
        model.character.classes = [("Druid", 4)]
        model.class_levels_changed.emit()
        assert tab._active_check.isChecked() is False
        entry = next(
            c
            for c in model.character.companions
            if c["companion_type"] == "wild_shape"
        )
        assert json.loads(entry["notes"])["active"] is False
        assert entry["creature"] == "Dire Bear"


class TestMalformedNotes:
    @pytest.mark.parametrize("notes", ["[1]", "true", "5", '"active"', "null"])
    def test_non_object_notes_do_not_break_sync(
        self, model: object, notes: str
    ) -> None:
        from heroforge.ui.tabs.wild_shape import WildShapeTab

        model.character.classes = [("Druid", 12)]
        model.character.companions = [
            {
                "companion_type": "wild_shape",
                "name": "",
                "creature": "Wolf",
                "notes": notes,
            }
        ]
        tab = WildShapeTab(model=model)
        assert tab._form_edit.text() == "Wolf"
        assert tab._active_check.isChecked() is False
        assert tab._loading is False
        # The tab still persists later edits.
        tab._active_check.setChecked(True)
        entry = next(
            c
            for c in model.character.companions
            if c["companion_type"] == "wild_shape"
        )
        assert json.loads(entry["notes"])["active"] is True


def _activate(model: object, form_name: str, level: int = 12) -> None:
    """Persist *form_name* as the active Wild Shape form for a druid."""
    model.character.classes = [("Druid", level)]
    model.character.companions = [
        {
            "companion_type": "wild_shape",
            "name": "",
            "creature": form_name,
            "notes": json.dumps({"active": True}),
        }
    ]


class TestFormMovement:
    """The form's land speed replaces the character's (PHB p37, issue #78)."""

    def test_land_speed_parses_leading_integer(self) -> None:
        from heroforge.logic.wild_shape import creature_land_speed

        assert creature_land_speed({"speed": "50"}) == 50
        assert creature_land_speed({"speed": "10 ft., fly 60 ft."}) == 10
        # No land speed recorded (e.g. an air elemental, which only flies).
        assert creature_land_speed({"speed": ""}) == 0

    def test_active_form_sets_speed(self, model: object) -> None:
        assert model.derived_stats().speed == 30
        _activate(model, "Wolf")
        assert model.derived_stats().speed == 50

    def test_flying_form_uses_its_land_speed(self, model: object) -> None:
        _activate(model, "Hawk")
        assert model.derived_stats().speed == 10

    def test_reverting_restores_speed(self, model: object) -> None:
        _activate(model, "Wolf")
        model.character.companions[0]["notes"] = json.dumps({"active": False})
        assert model.derived_stats().speed == 30

    def test_form_speed_still_slowed_by_load(self, model: object) -> None:
        # The derived pipeline keeps applying armor and load to the new speed.
        _activate(model, "Wolf")
        model.character.equipment = [
            {"item_name": "Anvil", "slot": "", "weight": 1000.0, "quantity": 1}
        ]
        assert model.derived_stats().speed < 50

    def test_export_reports_form_speed(self, model: object) -> None:
        from heroforge.logic.export import character_sheet_data

        _activate(model, "Wolf")
        data = character_sheet_data(model.character, model.derived_stats())
        assert data["speed"] == 50
