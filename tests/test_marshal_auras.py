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
    auras_known,
    get_aura,
    major_aura_value,
    marshal_level,
    max_active_auras,
    minor_aura_value,
    projected_auras,
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

    def test_major_follows_workbook_progression(self) -> None:
        # Tables!O338:O354: 1+(MrsLvl>=7)+(MrsLvl>=14)+(MrsLvl>=20).
        assert major_aura_value(2) == 1
        assert major_aura_value(6) == 1
        assert major_aura_value(7) == 2
        assert major_aura_value(10) == 2
        assert major_aura_value(13) == 2
        assert major_aura_value(14) == 3
        assert major_aura_value(19) == 3
        assert major_aura_value(20) == 4

    def test_no_major_aura_below_second_level(self) -> None:
        # Class Abilities!A1641 grants a major aura only when MrsLvl >= 2.
        assert major_aura_value(0) == 0
        assert major_aura_value(1) == 0


class TestCatalogue:
    def test_thirty_two_auras(self) -> None:
        assert len(STANDARD_MARSHAL_AURAS) == 32

    @pytest.mark.parametrize(
        ("name", "description"),
        [
            (
                "Power (Draconic)",
                "Bonus on caster level checks made to overcome spell resistance "
                "and manifester level checks made to overcome power resistance.",
            ),
            ("Toughness (Draconic)", "Grants damage reduction X/magic."),
            ("Hardy Soldiers", "Grants DR X/-."),
            (
                "Insight (Draconic)",
                "Bonus on Decipher Script, Knowledge, and Spellcraft checks.",
            ),
            (
                "Presence (Draconic)",
                "Bonus on Bluff, Diplomacy, and Intimidate checks.",
            ),
            (
                "Stamina (Draconic)",
                "Bonus on Constitution checks and Fortitude saves.",
            ),
        ],
    )
    def test_descriptions_follow_workbook(self, name: str, description: str) -> None:
        # Static wording of Tables!O321:O354.
        aura = get_aura(name)
        assert aura is not None
        assert aura.description == description

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


class TestAuraLimits:
    def test_auras_known_follow_workbook_table(self) -> None:
        # TblMarshallAurasKnown ('Marshal Auras'!H1:J21).
        assert auras_known(0) == (0, 0)
        assert auras_known(1) == (1, 0)
        assert auras_known(2) == (1, 1)
        assert auras_known(10) == (5, 3)
        assert auras_known(14) == (6, 4)
        assert auras_known(20) == (8, 5)
        assert auras_known(25) == (8, 5)

    def test_one_minor_and_one_major_projected(self) -> None:
        assert max_active_auras(0) == (0, 0)
        assert max_active_auras(1) == (1, 0)
        assert max_active_auras(2) == (1, 1)

    def test_two_active_minor_auras_do_not_stack(self) -> None:
        character = _marshal(level=10, auras=("Demand Fortitude", "Watchful Eye"))
        specs = aura_bonus_specs(character, 3)
        assert [spec["source"] for spec in specs] == ["Demand Fortitude"]

    def test_two_active_major_auras_do_not_stack(self) -> None:
        character = _marshal(level=10, auras=("Motivate Care", "Resilient Troops"))
        assert [a.name for a in projected_auras(character)] == ["Motivate Care"]

    def test_minor_and_major_project_together(self) -> None:
        character = _marshal(level=10, auras=("Demand Fortitude", "Motivate Care"))
        names = [a.name for a in projected_auras(character)]
        assert names == ["Demand Fortitude", "Motivate Care"]

    def test_no_marshal_levels_projects_nothing(self) -> None:
        character = _marshal(level=1, cha=16, auras=("Demand Fortitude",))
        character.classes = [("Fighter", 5)]
        assert projected_auras(character) == []
        base = compute_derived_stats(character).fortitude
        character.marshal_auras = []
        assert compute_derived_stats(character).fortitude == base

    def test_first_level_marshal_projects_no_major(self) -> None:
        character = _marshal(level=1, auras=("Motivate Care", "Demand Fortitude"))
        assert [a.name for a in projected_auras(character)] == ["Demand Fortitude"]


class TestAurasFeedDerivedStats:
    """Active auras reach compute_derived_stats without the UI model."""

    def test_major_aura_raises_armor_class(self) -> None:
        before = compute_derived_stats(_marshal(level=10))
        after = compute_derived_stats(_marshal(level=10, auras=("Motivate Care",)))
        assert after.armor_class - before.armor_class == 2

    def test_first_level_marshal_has_no_major_aura_bonus(self) -> None:
        before = compute_derived_stats(_marshal(level=1))
        after = compute_derived_stats(_marshal(level=1, auras=("Resilient Troops",)))
        assert after.fortitude == before.fortitude
        assert after.will == before.will

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

    def test_stamina_raises_fortitude(self) -> None:
        # Tables!O352: "+X on Constitution checks and Fortitude saves."
        before = compute_derived_stats(_marshal(level=7))
        after = compute_derived_stats(_marshal(level=7, auras=("Stamina (Draconic)",)))
        assert after.fortitude - before.fortitude == 2
        assert after.reflex == before.reflex

    def test_senses_raises_initiative(self) -> None:
        # Tables!O351: "+X on Listen checks, Spot checks, and initiative checks."
        before = compute_derived_stats(_marshal(level=14))
        after = compute_derived_stats(_marshal(level=14, auras=("Senses (Draconic)",)))
        assert after.initiative - before.initiative == 3

    def test_motivate_dexterity_raises_initiative(self) -> None:
        # Tables!O330: "+ChaMod on ... initiative checks."
        before = compute_derived_stats(_marshal(cha=14))
        after = compute_derived_stats(_marshal(cha=14, auras=("Motivate Dexterity",)))
        assert after.initiative - before.initiative == 2


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


def _check(tab: object, names: tuple[str, ...]) -> None:
    """Check *names* in the tab's known-aura lists."""
    from PyQt6.QtCore import Qt

    for lst in (tab._minor_list, tab._major_list):  # type: ignore[attr-defined]
        for i in range(lst.count()):
            item = lst.item(i)
            if item is not None and item.text() in names:
                item.setCheckState(Qt.CheckState.Checked)


def _project(combo: object, name: str) -> None:
    combo.setCurrentIndex(combo.findText(name))  # type: ignore[attr-defined]


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

    def test_checking_records_a_known_aura(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 1)]
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Force of Will",))

        assert model.character.marshal_auras == [
            {"aura_name": "Force of Will", "aura_type": "Minor", "active": False}
        ]

    def test_known_auras_are_capped_by_marshal_level(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 1)]  # 1 minor, 0 major known
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Demand Fortitude", "Force of Will", "Motivate Care"))

        names = [e["aura_name"] for e in model.character.marshal_auras]
        assert names == ["Demand Fortitude"]
        assert not tab._major.projecting.isEnabled()

    def test_no_marshal_levels_knows_no_auras(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        _check(tab, ("Demand Fortitude",))
        assert model.character.marshal_auras == []

    def test_cap_rises_with_class_levels(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        tab = MarshalAurasTab(model=model)
        model.character.classes = [("Marshal", 3)]  # 2 minor, 1 major known
        model.class_levels_changed.emit()
        _check(tab, ("Demand Fortitude", "Force of Will", "Watchful Eye"))
        assert len(model.character.marshal_auras) == 2
        assert tab._major.projecting.isEnabled()

    def test_projecting_is_one_aura_per_type(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 10)]
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Demand Fortitude", "Force of Will", "Motivate Care"))
        _project(tab._minor.projecting, "Demand Fortitude")
        _project(tab._minor.projecting, "Force of Will")
        _project(tab._major.projecting, "Motivate Care")

        active = [e["aura_name"] for e in model.character.marshal_auras if e["active"]]
        assert active == ["Force of Will", "Motivate Care"]

    def test_unchecking_a_projected_aura_stops_it(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 2)]
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Motivate Care",))
        _project(tab._major.projecting, "Motivate Care")
        item = tab._major_list.findItems("Motivate Care", Qt.MatchFlag.MatchExactly)[0]
        item.setCheckState(Qt.CheckState.Unchecked)

        assert model.character.marshal_auras == []
        assert tab._major.projecting.currentText() == "(none)"

    def test_sync_from_model_restores_known_and_projected(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 10)]
        model.character.marshal_auras = [
            {"aura_name": "Motivate Care", "aura_type": "Major", "active": False},
            {"aura_name": "Resilient Troops", "aura_type": "Major", "active": True},
        ]
        tab = MarshalAurasTab(model=model)
        checked = [
            tab._major_list.item(i).text()
            for i in range(tab._major_list.count())
            if tab._major_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        assert sorted(checked) == ["Motivate Care", "Resilient Troops"]
        assert tab._major.projecting.currentText() == "Resilient Troops"

    def test_projected_auras_modify_derived_saves(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 6)]
        model.character.ability_scores["CHA"] = 16  # +3 modifier

        before = model.derived_stats()

        tab = MarshalAurasTab(model=model)
        _check(tab, ("Demand Fortitude", "Resilient Troops"))
        # Knowing an aura changes nothing until it is projected.
        assert model.derived_stats().fortitude == before.fortitude
        _project(tab._minor.projecting, "Demand Fortitude")
        _project(tab._major.projecting, "Resilient Troops")

        after = model.derived_stats()
        # Demand Fortitude (minor, Cha +3) and Resilient Troops (major, +1).
        assert after.fortitude - before.fortitude == 4
        assert after.reflex - before.reflex == 1
        assert after.will - before.will == 1

    def test_switching_major_aura_moves_the_bonus(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 8)]  # major value +2

        before = model.derived_stats()

        tab = MarshalAurasTab(model=model)
        _check(tab, ("Motivate Care", "Motivate Attack"))
        _project(tab._major.projecting, "Motivate Care")
        care = model.derived_stats()
        assert care.armor_class - before.armor_class == 2
        assert care.melee_attack == before.melee_attack

        _project(tab._major.projecting, "Motivate Attack")
        attack = model.derived_stats()
        assert attack.armor_class == before.armor_class
        assert attack.melee_attack - before.melee_attack == 2

    def test_projecting_emits_derived_stats_changed(self, model: object) -> None:
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 2)]
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Motivate Care",))
        fired: list[int] = []
        model.derived_stats_changed.connect(lambda: fired.append(1))
        _project(tab._major.projecting, "Motivate Care")
        assert fired  # at least one recompute was requested

    def test_round_trips_through_persistence(
        self, model: object, tmp_path: Path
    ) -> None:
        from heroforge.db.character_repo import load_character, save_character
        from heroforge.db.schema import initialize_character_database
        from heroforge.ui.tabs.marshal_auras import MarshalAurasTab

        model.character.classes = [("Marshal", 4)]
        tab = MarshalAurasTab(model=model)
        _check(tab, ("Demand Fortitude", "Watchful Eye", "Motivate Care"))
        _project(tab._minor.projecting, "Watchful Eye")

        conn = initialize_character_database(tmp_path / "chars.hfc")
        try:
            cid = save_character(conn, model.character)
            loaded = load_character(conn, cid)
        finally:
            conn.close()

        assert loaded.marshal_auras == model.character.marshal_auras
        assert [e["aura_name"] for e in loaded.marshal_auras if e["active"]] == [
            "Watchful Eye"
        ]
