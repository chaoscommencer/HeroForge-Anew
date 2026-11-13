"""Tests for marshal aura mechanics, effect application, and the tab (8e).

Reference: *Miniatures Handbook* p11–12.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database
from heroforge.logic.derived_stats import compute_derived_stats
from heroforge.logic.marshal import (
    MAJOR,
    MINOR,
    STANDARD_MARSHAL_AURAS,
    aura_bonus_specs,
    get_aura,
    major_aura_value,
    marshal_level,
    minor_aura_value,
)
from heroforge.models.character import Character

# ---------------------------------------------------------------------------
# Pure-logic tests (no Qt required)
# ---------------------------------------------------------------------------


class TestAuraValues:
    def test_minor_uses_charisma_bonus(self) -> None:
        assert minor_aura_value(4) == 4
        assert minor_aura_value(0) == 0

    def test_minor_non_positive_charisma_confers_nothing(self) -> None:
        assert minor_aura_value(-2) == 0

    def test_major_is_half_level_minimum_one(self) -> None:
        assert major_aura_value(1) == 1  # rounds down to 0, floored to +1
        assert major_aura_value(2) == 1
        assert major_aura_value(6) == 3
        assert major_aura_value(20) == 10


class TestCatalogue:
    def test_thirty_two_auras(self) -> None:
        assert len(STANDARD_MARSHAL_AURAS) == 32

    def test_minor_and_major_counts(self) -> None:
        minor = [a for a in STANDARD_MARSHAL_AURAS if a.aura_type == MINOR]
        major = [a for a in STANDARD_MARSHAL_AURAS if a.aura_type == MAJOR]
        assert len(minor) == 15
        assert len(major) == 17

    def test_workbook_names_present(self) -> None:
        names = {a.name for a in STANDARD_MARSHAL_AURAS}
        assert "Accurate Strike" in names
        assert "Hardy Soldiers" in names
        assert "Toughness (Draconic)" in names

    def test_every_aura_has_a_description(self) -> None:
        assert all(a.description for a in STANDARD_MARSHAL_AURAS)

    def test_get_aura_lookup(self) -> None:
        aura = get_aura("Demand Fortitude")
        assert aura is not None and aura.aura_type == MINOR
        assert get_aura("Not An Aura") is None


def _marshal(level: int = 6, cha: int = 10, auras: tuple[str, ...] = ()) -> Character:
    """Build a Marshal of *level* with Charisma *cha* projecting *auras*."""
    character = Character()
    character.classes = [("Marshal", level)]
    character.ability_scores["CHA"] = cha
    character.marshal_auras = [
        {"aura_name": name, "aura_type": _aura_type(name), "active": True}
        for name in auras
    ]
    return character


def _aura_type(name: str) -> str:
    aura = get_aura(name)
    return aura.aura_type if aura is not None else ""


def _spec_values(character: Character, cha_mod: int) -> dict[str, int]:
    """Map each aura spec's target to its value."""
    return {
        str(spec["target"]): int(spec["value"])  # type: ignore[call-overload]
        for spec in aura_bonus_specs(character, cha_mod)
    }


class TestMarshalLevel:
    def test_sums_marshal_levels(self) -> None:
        character = Character()
        character.classes = [("Marshal", 3), ("Fighter", 2), ("marshal", 1)]
        assert marshal_level(character) == 4

    def test_no_marshal_levels(self) -> None:
        assert marshal_level(Character()) == 0


class TestAuraBonusSpecs:
    def test_specs_are_circumstance_bonuses(self) -> None:
        specs = aura_bonus_specs(_marshal(auras=("Demand Fortitude",)), 3)
        assert specs == [
            {
                "source": "Demand Fortitude",
                "target": "fort",
                "bonus_type": "circumstance",
                "value": 3,
            }
        ]

    def test_inactive_auras_are_skipped(self) -> None:
        character = _marshal()
        character.marshal_auras = [
            {"aura_name": "Demand Fortitude", "aura_type": MINOR, "active": False}
        ]
        assert aura_bonus_specs(character, 3) == []

    def test_unmodelled_aura_contributes_nothing(self) -> None:
        character = _marshal(auras=("Accurate Strike",))
        assert aura_bonus_specs(character, 4) == []

    def test_unknown_aura_ignored(self) -> None:
        character = _marshal()
        character.marshal_auras = [{"aura_name": "Bogus Aura", "active": True}]
        assert aura_bonus_specs(character, 4) == []

    def test_zero_value_minor_aura_omitted(self) -> None:
        # A non-positive Charisma modifier yields no minor-aura bonus.
        assert aura_bonus_specs(_marshal(auras=("Demand Fortitude",)), -1) == []


class TestAurasFeedDerivedStats:
    """Active auras reach compute_derived_stats without the UI model."""

    def test_major_aura_raises_armor_class(self) -> None:
        before = compute_derived_stats(_marshal(level=6))
        after = compute_derived_stats(_marshal(level=6, auras=("Motivate Care",)))
        assert after.armor_class - before.armor_class == 3

    def test_minor_aura_uses_buffed_charisma(self) -> None:
        character = _marshal(cha=12, auras=("Force of Will",))  # Cha +1
        base_will = compute_derived_stats(_marshal(cha=12)).will
        assert compute_derived_stats(character).will - base_will == 1
        # Eagle's Splendor (+4 enhancement to Cha) raises the modifier to +3.
        character.buffs = [
            {
                "id": "eagle",
                "name": "Eagle's Splendor",
                "bonus_type": "enhancement",
                "target_stat": "CHA",
                "amount": 4,
            }
        ]
        assert compute_derived_stats(character).will - base_will == 3

    def test_minor_aura_uses_racial_charisma(self) -> None:
        character = _marshal(cha=12, auras=("Watchful Eye",))
        base = compute_derived_stats(_marshal(cha=12)).reflex
        stats = compute_derived_stats(character, ability_adjustments={"CHA": 2})
        assert stats.reflex - base == 2


# ---------------------------------------------------------------------------
# Tab + derived-stats integration (Qt)
# ---------------------------------------------------------------------------


@pytest.fixture()
def marshal_db(tmp_path: Path) -> Path:
    """Seed a game database with the marshal aura catalogue."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.executemany(
            "INSERT INTO marshal_auras (name, type) VALUES (?, ?)",
            [
                ("Demand Fortitude", "Minor"),
                ("Force of Will", "Minor"),
                ("Watchful Eye", "Minor"),
                ("Motivate Care", "Major"),
                ("Motivate Attack", "Major"),
                ("Resilient Troops", "Major"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def model(qapp: object, marshal_db: Path) -> object:
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(str(marshal_db)))


class TestMarshalAurasTab:
    def test_lists_populate_from_data_access(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        minor_names = {
            tab._minor_list.item(i).text() for i in range(tab._minor_list.count())
        }
        major_names = {
            tab._major_list.item(i).text() for i in range(tab._major_list.count())
        }
        assert minor_names == {"Demand Fortitude", "Force of Will", "Watchful Eye"}
        assert major_names == {
            "Motivate Care",
            "Motivate Attack",
            "Resilient Troops",
        }

    def test_checking_persists_active_aura(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        item = tab._minor_list.item(0)
        assert item is not None
        item.setCheckState(Qt.CheckState.Checked)

        active = model.character.marshal_auras
        assert len(active) == 1
        assert active[0]["aura_name"] == item.text()
        assert active[0]["aura_type"] == "Minor"
        assert active[0]["active"] is True

    def test_sync_from_model_rechecks_active(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.marshal_auras = [
            {"aura_name": "Resilient Troops", "aura_type": "Major", "active": True}
        ]
        tab = MarshalAurasTab(model=model)
        checked = [
            tab._major_list.item(i).text()
            for i in range(tab._major_list.count())
            if tab._major_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        assert checked == ["Resilient Troops"]

    def test_active_auras_modify_derived_saves(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 6)]
        model.character.ability_scores["CHA"] = 16  # +3 modifier

        before = model.derived_stats()

        tab = MarshalAurasTab(model=model)
        # Demand Fortitude (minor, Cha +3) and Resilient Troops (major, +3).
        for lst in (tab._minor_list, tab._major_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item is not None and item.text() in (
                    "Demand Fortitude",
                    "Resilient Troops",
                ):
                    item.setCheckState(Qt.CheckState.Checked)

        after = model.derived_stats()
        # Fortitude gains both auras (+6); Reflex/Will gain Resilient Troops (+3).
        assert after.fortitude - before.fortitude == 6
        assert after.reflex - before.reflex == 3
        assert after.will - before.will == 3

    def test_active_attack_and_ac_auras_modify_derived_stats(
        self, model: object
    ) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 8)]  # major value +4

        before = model.derived_stats()

        tab = MarshalAurasTab(model=model)
        for i in range(tab._major_list.count()):
            item = tab._major_list.item(i)
            if item is not None and item.text() in ("Motivate Care", "Motivate Attack"):
                item.setCheckState(Qt.CheckState.Checked)

        after = model.derived_stats()
        assert after.armor_class - before.armor_class == 4
        assert after.melee_attack - before.melee_attack == 4

    def test_toggling_emits_derived_stats_changed(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        fired: list[int] = []
        model.derived_stats_changed.connect(lambda: fired.append(1))
        item = tab._major_list.item(0)
        assert item is not None
        item.setCheckState(Qt.CheckState.Checked)
        assert fired  # at least one recompute was requested

    def test_round_trips_through_persistence(
        self, model: object, tmp_path: Path
    ) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.db.character_repo import load_character, save_character
        from heroforge.db.schema import initialize_character_database
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        tab._minor_list.item(0).setCheckState(Qt.CheckState.Checked)
        tab._major_list.item(0).setCheckState(Qt.CheckState.Checked)

        conn = initialize_character_database(tmp_path / "chars.hfc")
        try:
            cid = save_character(conn, model.character)
            loaded = load_character(conn, cid)
        finally:
            conn.close()

        assert loaded.marshal_auras == model.character.marshal_auras
        assert all(entry["active"] for entry in loaded.marshal_auras)
