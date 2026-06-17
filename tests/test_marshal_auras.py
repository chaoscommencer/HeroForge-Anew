"""Tests for marshal aura mechanics, effect application, and the tab (8e).

Reference: *Miniatures Handbook* p11–12.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database
from heroforge.logic.marshal import (
    MAJOR,
    MINOR,
    STANDARD_MARSHAL_AURAS,
    AuraBonuses,
    apply_aura_bonuses,
    get_aura,
    major_aura_value,
    minor_aura_value,
)

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


class TestApplyAuraBonuses:
    def test_minor_save_auras_scale_with_charisma(self) -> None:
        bonuses = apply_aura_bonuses(
            ["Demand Fortitude", "Watchful Eye", "Force of Will"],
            charisma_modifier=3,
            marshal_level=4,
        )
        assert bonuses.save_bonuses == {"fort": 3, "ref": 3, "will": 3}
        assert bonuses.ac_bonuses == ()
        assert dict(bonuses.attack_bonuses) == {}

    def test_major_save_aura_covers_all_saves(self) -> None:
        bonuses = apply_aura_bonuses(
            ["Resilient Troops"], charisma_modifier=0, marshal_level=8
        )
        assert bonuses.save_bonuses == {"fort": 4, "ref": 4, "will": 4}

    def test_minor_and_major_save_auras_stack(self) -> None:
        bonuses = apply_aura_bonuses(
            ["Demand Fortitude", "Resilient Troops"],
            charisma_modifier=2,
            marshal_level=10,
        )
        # Demand Fortitude (Cha +2) + Resilient Troops (half of 10 = +5).
        assert bonuses.save_bonuses["fort"] == 7
        assert bonuses.save_bonuses["ref"] == 5
        assert bonuses.save_bonuses["will"] == 5

    def test_ac_and_attack_auras(self) -> None:
        bonuses = apply_aura_bonuses(
            ["Motivate Care", "Motivate Attack", "Steady Hand"],
            charisma_modifier=5,
            marshal_level=6,
        )
        assert bonuses.ac_bonuses == (("", 3),)
        assert dict(bonuses.attack_bonuses) == {"melee": 3, "ranged": 3}

    def test_unmodelled_aura_contributes_nothing(self) -> None:
        bonuses = apply_aura_bonuses(
            ["Accurate Strike", "Motivate Urgency", "Insight (Draconic)"],
            charisma_modifier=4,
            marshal_level=6,
        )
        assert bonuses == AuraBonuses()

    def test_unknown_aura_ignored(self) -> None:
        bonuses = apply_aura_bonuses(["Bogus Aura"], 4, 6)
        assert bonuses == AuraBonuses()

    def test_zero_value_minor_aura_omitted(self) -> None:
        # A non-positive Charisma modifier yields no minor-aura bonus.
        bonuses = apply_aura_bonuses(["Demand Fortitude"], -1, 6)
        assert bonuses.save_bonuses == {}


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
