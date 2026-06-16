"""Persistence and rules-integration tests for the character-backed tabs.

These exercise the conversion of the formerly widget-only "mock" tabs into
data-driven, character-backed widgets:

* option lists are loaded from a seeded SQLite catalogue,
* selections are written to the central :class:`CharacterModel`,
* rules/limits are enforced (language slots, trait caps, graft slot conflicts,
  armour-class maths), and
* the resulting character state round-trips through ``save_character`` /
  ``load_character``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database
from heroforge.logic.languages import automatic_languages, bonus_language_slots

# ---------------------------------------------------------------------------
# Pure-logic tests (no Qt required)
# ---------------------------------------------------------------------------


class TestLanguageRules:
    def test_common_always_automatic(self) -> None:
        assert "Common" in automatic_languages("")
        assert "Common" in automatic_languages("Human")

    def test_racial_automatic_language(self) -> None:
        elf = automatic_languages("Elf")
        assert "Common" in elf
        assert "Elven" in elf

    def test_bonus_slots_track_int_modifier(self) -> None:
        # INT 10 -> +0, INT 12 -> +1, INT 16 -> +3, INT 8 -> 0 (never negative).
        assert bonus_language_slots(10) == 0
        assert bonus_language_slots(12) == 1
        assert bonus_language_slots(16) == 3
        assert bonus_language_slots(8) == 0

    def test_subtype_prefix_resolves_to_base_race(self) -> None:
        assert "Dwarven" in automatic_languages("Mountain Dwarf")
        assert "Elven" in automatic_languages("Wood Elf")

    def test_incidental_substring_does_not_match(self) -> None:
        # "elf" appears inside "selfish" but must not grant Elven.
        assert automatic_languages("Selfish Construct") == ["Common"]
        # "half" appears inside "halfling" but Halfling must resolve to Halfling
        # (its own entry), not to the "half-elf"/"half-orc" entries.
        assert automatic_languages("Halfling") == ["Common", "Halfling"]


# ---------------------------------------------------------------------------
# Widget fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def catalog_db(tmp_path: Path) -> Path:
    """Seed a small game database covering the new catalogue tables."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.executemany(
            "INSERT INTO languages (name) VALUES (?)",
            [("Draconic",), ("Goblin",), ("Elven",), ("Dwarven",), ("Orc",)],
        )
        conn.executemany(
            "INSERT INTO traits (name, source) VALUES (?, ?)",
            [("Aggressive", "UA"), ("Cautious", "UA"), ("Brawler", "UA")],
        )
        conn.executemany(
            "INSERT INTO flaws (name, source) VALUES (?, ?)",
            [("Shaky", "UA"), ("Frail", "UA"), ("Noncombatant", "UA")],
        )
        conn.executemany(
            "INSERT INTO skill_tricks (name, cost, prerequisite) VALUES (?, ?, ?)",
            [("Acrobatic Backstab", 2, "Tumble 12"), ("Back on Your Feet", 2, "")],
        )
        conn.executemany(
            "INSERT INTO grafts (name, type, body_slot, source) VALUES (?, ?, ?, ?)",
            [
                ("Fiendish Arm", "Fiendish", "Arms", "FF"),
                ("Fiendish Eye", "Fiendish", "Eyes", "FF"),
                ("Demon Arm", "Fiendish", "Arms", "FF"),
            ],
        )
        conn.executemany(
            "INSERT INTO graft_abilities (graft_name, ability_name, description) "
            "VALUES (?, ?, ?)",
            [
                ("Fiendish Arm", "Claw Attack", "Primary claw dealing 1d6 damage."),
                ("Fiendish Arm", "Strength Boost", "+2 Strength."),
                ("Fiendish Eye", "Darkvision", "Darkvision out to 60 feet."),
            ],
        )
        conn.executemany(
            "INSERT INTO soulmelds (name, chakra, essentia_capacity, source) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Airstep Sandals", "Feet", 3, "MoI"),
                ("Mage's Spectacles", "Brow", 3, "MoI"),
            ],
        )
        conn.executemany(
            "INSERT INTO psionic_powers (name, discipline, power_points, source) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Mind Thrust", "Telepathy", 1, "EPH"),
                ("Energy Ray", "Psychokinesis", 1, "EPH"),
            ],
        )
        conn.executemany(
            "INSERT INTO maneuvers (name, discipline, level, type, source) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("Sapphire Nightmare Blade", "Diamond Mind", 1, "Strike", "ToB"),
                ("Punishing Stance", "Iron Heart", 1, "Stance", "ToB"),
            ],
        )
        conn.executemany(
            "INSERT INTO armor (name, type, ac_bonus, max_dex_bonus, check_penalty, "
            "arcane_spell_failure, weight, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Full Plate", "Heavy", 8, 1, -6, 35, 50.0, "PHB"),
                ("Leather", "Light", 2, 6, 0, 10, 15.0, "PHB"),
                ("Heavy Steel Shield", "Shield", 2, None, -2, 15, 15.0, "PHB"),
            ],
        )
        conn.executemany(
            "INSERT INTO weapons (name, category, damage_medium, critical, "
            "range_increment, damage_type, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("Longsword", "Martial", "1d8", "19-20/x2", 0, "slashing", "PHB"),
                ("Longbow", "Martial", "1d8", "x3", 100, "piercing", "PHB"),
            ],
        )
        conn.executemany(
            "INSERT INTO magic_enhancements (name, type, bonus_equivalent, source) "
            "VALUES (?, ?, ?, ?)",
            [("Flaming", "Weapon", 1, "DMG"), ("Fortification", "Armor", 1, "DMG")],
        )
        conn.executemany(
            "INSERT INTO magic_equipment (name, slot, source) VALUES (?, ?, ?)",
            [
                ("Cloak of Resistance +1", "Shoulders", "DMG"),
                ("Handy Haversack", "Wondrous", "DMG"),
            ],
        )
        conn.executemany(
            "INSERT INTO creatures (name, size, type, hit_dice, str_score, dex_score, "
            "con_score, int_score, wis_score, cha_score, natural_armor, source) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Wolf", "Medium", "Animal", "2d8+4", 13, 15, 15, 2, 12, 6, 14, "MM"),
                ("Hawk", "Tiny", "Animal", "1d8", 6, 17, 10, 2, 14, 6, 17, "MM"),
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
    """Persist *character* to a fresh character DB and reload it."""
    from heroforge.db.character_repo import load_character, save_character
    from heroforge.db.schema import initialize_character_database

    conn = initialize_character_database(tmp_path / "chars.hfc")
    try:
        cid = save_character(conn, character)  # type: ignore[arg-type]
        return load_character(conn, cid)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------


class TestLanguagesTab:
    def test_options_loaded_from_catalogue(self, model: object) -> None:
        assert "Draconic" in model.game_data().list_languages()

    def test_add_persists_and_enforces_int_budget(self, model: object) -> None:
        from heroforge.ui.tabs.languages import LanguagesTab

        model.character.race = "Human"
        model.character.ability_scores["INT"] = 14  # +2 modifier = 2 bonus slots
        tab = LanguagesTab(model=model)
        model.derived_stats_changed.emit()

        assert tab.add_language("Draconic") is True
        assert tab.add_language("Goblin") is True
        # Third language exceeds the two-slot budget.
        assert tab.add_language("Elven") is False
        assert model.character.languages == ["Draconic", "Goblin"]

    def test_rejects_automatic_language(self, model: object) -> None:
        from heroforge.ui.tabs.languages import LanguagesTab

        model.character.race = "Elf"  # Elven is automatic
        model.character.ability_scores["INT"] = 16
        tab = LanguagesTab(model=model)
        model.derived_stats_changed.emit()

        assert tab.add_language("Elven") is False

    def test_syncs_from_model_on_load(self, model: object) -> None:
        from heroforge.ui.tabs.languages import LanguagesTab

        tab = LanguagesTab(model=model)
        model.character.languages = ["Draconic", "Goblin"]
        model.character_loaded.emit(0)
        assert tab._chosen() == ["Draconic", "Goblin"]


# ---------------------------------------------------------------------------
# Traits & Flaws
# ---------------------------------------------------------------------------


class TestTraitsAndFlawsTab:
    def test_caps_and_persistence(self, model: object) -> None:
        from heroforge.ui.tabs.traits_and_flaws import TraitsAndFlawsTab

        tab = TraitsAndFlawsTab(model=model)
        assert tab.add_trait("Aggressive") is True
        assert tab.add_trait("Cautious") is True
        # A character may take at most two traits.
        assert tab.add_trait("Brawler") is False
        assert tab.add_trait("Shaky", is_flaw=True) is True

        traits = [t for t in model.character.traits if not t["is_flaw"]]
        flaws = [t for t in model.character.traits if t["is_flaw"]]
        assert {t["trait_name"] for t in traits} == {"Aggressive", "Cautious"}
        assert {f["trait_name"] for f in flaws} == {"Shaky"}

    def test_sync_from_model(self, model: object) -> None:
        from heroforge.ui.tabs.traits_and_flaws import TraitsAndFlawsTab

        tab = TraitsAndFlawsTab(model=model)
        model.character.traits = [
            {"trait_name": "Aggressive", "is_flaw": False},
            {"trait_name": "Shaky", "is_flaw": True},
        ]
        model.character_loaded.emit(0)
        assert tab._names("traits") == ["Aggressive"]
        assert tab._names("flaws") == ["Shaky"]


# ---------------------------------------------------------------------------
# Skill tricks
# ---------------------------------------------------------------------------


class TestSkillTricksTab:
    def test_learn_persists_and_dedupes(self, model: object) -> None:
        from heroforge.ui.tabs.skill_tricks import SkillTricksTab

        tab = SkillTricksTab(model=model)
        assert tab.learn("Acrobatic Backstab") is True
        assert tab.learn("Acrobatic Backstab") is False  # duplicate
        assert model.character.skill_tricks == ["Acrobatic Backstab"]


# ---------------------------------------------------------------------------
# Grafts
# ---------------------------------------------------------------------------


class TestGraftsTab:
    def test_slot_conflict_rejected(self, model: object) -> None:
        from heroforge.ui.tabs.grafts import GraftsTab

        tab = GraftsTab(model=model)
        assert tab.add_graft("Fiendish Arm", "Arms") is True
        # A second graft in the same body slot is rejected.
        assert tab.add_graft("Demon Arm", "Arms") is False
        # A different slot is fine.
        assert tab.add_graft("Fiendish Eye", "Eyes") is True
        slots = {g["body_slot"] for g in model.character.grafts}
        assert slots == {"Arms", "Eyes"}

    def test_abilities_displayed_for_selected_graft(self, model: object) -> None:
        from heroforge.ui.tabs.grafts import GraftsTab

        tab = GraftsTab(model=model)
        assert tab.add_graft("Fiendish Arm", "Arms") is True
        tab._graft_list.setCurrentRow(0)
        labels = [
            tab._abilities_list.item(i).text()
            for i in range(tab._abilities_list.count())
        ]
        assert any("Claw Attack" in label for label in labels)
        assert any("Strength Boost" in label for label in labels)


# ---------------------------------------------------------------------------
# Armour (AC maths + equipment partitioning)
# ---------------------------------------------------------------------------


class TestArmorTab:
    def test_ac_computation(self, model: object) -> None:
        from heroforge.ui.tabs.armor import ArmorTab

        model.character.ability_scores["DEX"] = 14  # +2, capped to 1 by Full Plate
        tab = ArmorTab(model=model)

        catalog = {a.name: a for a in model.game_data().list_armor()}
        tab._set_item("Body Armor", catalog["Full Plate"])
        tab._set_item("Shield", catalog["Heavy Steel Shield"])
        tab._sync_to_model()
        tab._refresh_summary()

        # 10 + 8 (plate) + 2 (shield) + 1 (DEX capped) = 21
        assert tab._total_ac_lbl.text() == "21"
        # Touch ignores armour/shield: 10 + 1 = 11
        assert tab._touch_ac_lbl.text() == "11"
        # Flat-footed loses DEX: 10 + 8 + 2 = 20
        assert tab._ff_ac_lbl.text() == "20"
        # ACP: -6 + -2 = -8
        assert tab._acp_lbl.text() == "-8"

    def test_equipment_persisted_with_slots(self, model: object) -> None:
        from heroforge.ui.tabs.armor import ArmorTab

        tab = ArmorTab(model=model)
        catalog = {a.name: a for a in model.game_data().list_armor()}
        tab._set_item("Body Armor", catalog["Leather"])
        tab._sync_to_model()
        slots = {e["slot"]: e["item_name"] for e in model.character.equipment}
        assert slots == {"Body Armor": "Leather"}


# ---------------------------------------------------------------------------
# Armour + magic-equipment slot partitioning
# ---------------------------------------------------------------------------


class TestEquipmentPartitioning:
    def test_armor_and_magic_tabs_do_not_clobber(self, model: object) -> None:
        from heroforge.ui.tabs.armor import ArmorTab
        from heroforge.ui.tabs.magic_equipment import MagicEquipmentTab

        armor = ArmorTab(model=model)
        magic = MagicEquipmentTab(model=model)

        catalog = {a.name: a for a in model.game_data().list_armor()}
        armor._set_item("Body Armor", catalog["Full Plate"])
        armor._sync_to_model()

        magic.add_extra("Handy Haversack")

        slots = {e["slot"] for e in model.character.equipment}
        assert "Body Armor" in slots
        assert "Wondrous" in slots
        # The magic tab writing wondrous items must not drop the armour entry.
        names = {e["item_name"] for e in model.character.equipment}
        assert {"Full Plate", "Handy Haversack"} <= names


# ---------------------------------------------------------------------------
# Attacks (weapon catalogue)
# ---------------------------------------------------------------------------


class TestAttacksTab:
    def test_weapon_from_catalogue_persists(self, model: object) -> None:
        from heroforge.ui.tabs.attacks import AttacksTab

        tab = AttacksTab(model=model)
        weapon = next(
            w for w in model.game_data().list_weapons() if w.name == "Longsword"
        )
        tab.add_weapon(weapon)
        assert any(a["weapon_name"] == "Longsword" for a in model.character.attacks)


# ---------------------------------------------------------------------------
# Soulmelds / Psionics / Maneuvers
# ---------------------------------------------------------------------------


class TestIncarnumPsionicsManeuvers:
    def test_soulmeld_essentia_persists(self, model: object) -> None:
        from heroforge.ui.tabs.soulmelds import SoulmeldsTab

        tab = SoulmeldsTab(model=model)
        tab._total_spin.setValue(5)
        assert tab.shape_soulmeld("Airstep Sandals", "Feet", 2) is True
        meld = model.character.soulmelds[0]
        assert meld["soulmeld_name"] == "Airstep Sandals"
        assert meld["essentia_invested"] == 2
        assert model.character.options["essentia_pool"] == "5"

    def test_psionic_power_and_pp_persist(self, model: object) -> None:
        from heroforge.ui.tabs.psionics import PsionicsTab

        tab = PsionicsTab(model=model)
        tab._total_pp.setValue(11)
        assert tab.add_power("Mind Thrust") is True
        assert any(
            p["power_name"] == "Mind Thrust" for p in model.character.psionic_powers
        )
        assert model.character.options["psionic_total_pp"] == "11"

    def test_maneuver_and_stance_classified(self, model: object) -> None:
        from heroforge.ui.tabs.maneuvers_and_stances import ManeuversAndStancesTab

        tab = ManeuversAndStancesTab(model=model)
        assert tab.add_maneuver("Sapphire Nightmare Blade") is True
        assert tab.add_maneuver("Punishing Stance", stance=True) is True
        names = {m["maneuver_name"] for m in model.character.maneuvers}
        assert names == {"Sapphire Nightmare Blade", "Punishing Stance"}


# ---------------------------------------------------------------------------
# Companions (animal + familiar partition, JSON round-trip)
# ---------------------------------------------------------------------------


class TestCompanions:
    def test_animal_and_familiar_partition(self, model: object) -> None:
        from heroforge.ui.tabs.animal_companion import AnimalCompanionTab
        from heroforge.ui.tabs.familiar import FamiliarTab

        animal = AnimalCompanionTab(model=model)
        familiar = FamiliarTab(model=model)

        animal._name_edit.setText("Rex")
        animal._species_edit.setText("Wolf")
        animal._sync_to_model()

        familiar._sync_from_model()  # ensure familiar refresh keeps the animal entry

        types = {c["companion_type"] for c in model.character.companions}
        assert "animal" in types
        animal_entry = next(
            c for c in model.character.companions if c["companion_type"] == "animal"
        )
        assert animal_entry["name"] == "Rex"
        # Detailed stats are JSON-encoded in the notes column.
        assert json.loads(animal_entry["notes"])["scores"]["STR"] == 10


# ---------------------------------------------------------------------------
# LG Game Log (Living Greyhawk; deprecated)
# ---------------------------------------------------------------------------


class TestLGGameLogTab:
    def test_add_record_persists_as_game_log(self, model: object) -> None:
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        tab = LGGameLogTab(model=model)
        tab.add_record("2024-02-02", "Defeated bandits", 150, 450, "AR note")

        records = [
            r for r in model.character.lg_records if r["record_type"] == "game_log"
        ]
        assert len(records) == 1
        rec = records[0]
        assert rec["event_date"] == "2024-02-02"
        assert rec["description"] == "Defeated bandits"
        assert rec["gp_change"] == 150.0
        assert rec["xp_change"] == 450.0
        assert rec["notes"] == "AR note"

    def test_other_lg_record_types_preserved(self, model: object) -> None:
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        model.character.lg_records = [
            {"record_type": "item_access", "description": "Boots of Speed"}
        ]
        tab = LGGameLogTab(model=model)
        tab.add_record(description="A new adventure")

        types = [r["record_type"] for r in model.character.lg_records]
        assert "item_access" in types
        assert "game_log" in types

    def test_sync_preserves_interleaved_ordering(self, model: object) -> None:
        """game_log records replaced in-place; sibling record positions unchanged."""
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        # Start with interleaved records: item_access / game_log / mil
        model.character.lg_records = [
            {"record_type": "item_access", "description": "Ring"},
            {
                "record_type": "game_log",
                "event_date": "2024-01-01",
                "description": "Old session",
                "gp_change": 0.0,
                "xp_change": 0.0,
                "notes": None,
            },
            {"record_type": "mil", "description": "Promotion"},
        ]
        tab = LGGameLogTab(model=model)
        # Edit the existing game_log row via the table
        tab._table.item(0, 1).setText("Updated session")

        records = model.character.lg_records
        # Ordering must still be: item_access, game_log, mil
        assert [r["record_type"] for r in records] == [
            "item_access",
            "game_log",
            "mil",
        ]
        assert records[1]["description"] == "Updated session"

    def test_cell_edit_syncs_to_model(self, model: object) -> None:
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        tab = LGGameLogTab(model=model)
        tab.add_record(description="Original")
        tab._table.item(0, 1).setText("Edited")

        record = next(
            r for r in model.character.lg_records if r["record_type"] == "game_log"
        )
        assert record["description"] == "Edited"

    def test_sync_from_model_shows_only_game_log_rows(self, model: object) -> None:
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        model.character.lg_records = [
            {"record_type": "item_access", "description": "Wand"},
            {
                "record_type": "game_log",
                "event_date": "2024-01-01",
                "description": "Session 1",
                "gp_change": 10.0,
                "xp_change": 20.0,
                "notes": "",
            },
        ]
        tab = LGGameLogTab(model=model)
        assert tab._table.rowCount() == 1
        assert tab._table.item(0, 1).text() == "Session 1"

    def test_records_round_trip(self, model: object, tmp_path: Path) -> None:
        from heroforge.ui.tabs.lg_game_log import LGGameLogTab

        tab = LGGameLogTab(model=model)
        tab.add_record("2024-03-03", "Slew the dragon", 500, 1000, "Big haul")

        loaded = _round_trip(model.character, tmp_path)
        records = [r for r in loaded.lg_records if r["record_type"] == "game_log"]
        assert len(records) == 1
        assert records[0]["description"] == "Slew the dragon"
        assert records[0]["gp_change"] == 500.0


class TestLGItemAccessTab:
    def test_add_record_persists_as_item_access(self, model: object) -> None:
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        tab = LGItemAccessTab(model=model)
        tab.add_record("2024-02-02", "Boots of Speed", 12000, "AR 1234")

        records = [
            r for r in model.character.lg_records if r["record_type"] == "item_access"
        ]
        assert len(records) == 1
        rec = records[0]
        assert rec["event_date"] == "2024-02-02"
        assert rec["description"] == "Boots of Speed"
        assert rec["gp_change"] == 12000.0
        assert rec["xp_change"] == 0.0
        assert rec["notes"] == "AR 1234"

    def test_other_lg_record_types_preserved(self, model: object) -> None:
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        model.character.lg_records = [
            {"record_type": "game_log", "description": "An old session"}
        ]
        tab = LGItemAccessTab(model=model)
        tab.add_record(item="Ring of Protection")

        types = [r["record_type"] for r in model.character.lg_records]
        assert "game_log" in types
        assert "item_access" in types

    def test_sync_preserves_interleaved_ordering(self, model: object) -> None:
        """item_access records replaced in-place; sibling positions unchanged."""
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        # Start with interleaved records: game_log / item_access / mil
        model.character.lg_records = [
            {"record_type": "game_log", "description": "Session"},
            {
                "record_type": "item_access",
                "event_date": "2024-01-01",
                "description": "Old wand",
                "gp_change": 0.0,
                "xp_change": 0.0,
                "notes": None,
            },
            {"record_type": "mil", "description": "Promotion"},
        ]
        tab = LGItemAccessTab(model=model)
        # Edit the existing item_access row via the table
        tab._table.item(0, 1).setText("Updated wand")

        records = model.character.lg_records
        # Ordering must still be: game_log, item_access, mil
        assert [r["record_type"] for r in records] == [
            "game_log",
            "item_access",
            "mil",
        ]
        assert records[1]["description"] == "Updated wand"

    def test_cell_edit_syncs_to_model(self, model: object) -> None:
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        tab = LGItemAccessTab(model=model)
        tab.add_record(item="Original")
        tab._table.item(0, 1).setText("Edited")

        record = next(
            r for r in model.character.lg_records if r["record_type"] == "item_access"
        )
        assert record["description"] == "Edited"

    def test_sync_from_model_shows_only_item_access_rows(self, model: object) -> None:
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        model.character.lg_records = [
            {"record_type": "game_log", "description": "Session 1"},
            {
                "record_type": "item_access",
                "event_date": "2024-01-01",
                "description": "Cloak of Resistance",
                "gp_change": 1000.0,
                "xp_change": 0.0,
                "notes": "",
            },
        ]
        tab = LGItemAccessTab(model=model)
        assert tab._table.rowCount() == 1
        assert tab._table.item(0, 1).text() == "Cloak of Resistance"

    def test_records_round_trip(self, model: object, tmp_path: Path) -> None:
        from heroforge.ui.tabs.lg_item_access import LGItemAccessTab

        tab = LGItemAccessTab(model=model)
        tab.add_record("2024-03-03", "Staff of Power", 200000, "AR 5678")

        loaded = _round_trip(model.character, tmp_path)
        records = [r for r in loaded.lg_records if r["record_type"] == "item_access"]
        assert len(records) == 1
        assert records[0]["description"] == "Staff of Power"
        assert records[0]["gp_change"] == 200000.0
        assert records[0]["notes"] == "AR 5678"


# ---------------------------------------------------------------------------
# Full save/load round-trip across several tabs
# ---------------------------------------------------------------------------


class TestSaveLoadRoundTrip:
    def test_multiple_tabs_round_trip(self, model: object, tmp_path: Path) -> None:
        from heroforge.ui.tabs.grafts import GraftsTab
        from heroforge.ui.tabs.languages import LanguagesTab
        from heroforge.ui.tabs.skill_tricks import SkillTricksTab
        from heroforge.ui.tabs.traits_and_flaws import TraitsAndFlawsTab

        model.character.name = "Round Trip"
        model.character.race = "Human"
        model.character.ability_scores["INT"] = 16

        lang = LanguagesTab(model=model)
        model.derived_stats_changed.emit()
        lang.add_language("Draconic")

        SkillTricksTab(model=model).learn("Acrobatic Backstab")
        TraitsAndFlawsTab(model=model).add_trait("Aggressive")
        GraftsTab(model=model).add_graft("Fiendish Arm", "Arms")

        loaded = _round_trip(model.character, tmp_path)
        assert loaded.languages == ["Draconic"]
        assert loaded.skill_tricks == ["Acrobatic Backstab"]
        assert any(t["trait_name"] == "Aggressive" for t in loaded.traits)
        assert any(g["graft_name"] == "Fiendish Arm" for g in loaded.grafts)


# ---------------------------------------------------------------------------
# Stats & Character Details (identity + ability scores)
# ---------------------------------------------------------------------------


class TestStatsAndCharacterDetailsTab:
    def test_identity_edits_persist_and_restore(
        self, model: object, tmp_path: Path
    ) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        tab = StatsAndCharacterDetailsTab(model=model)
        tab._name_edit.setText("Mialee")
        tab._player_edit.setText("Jess")
        tab._deity_edit.setText("Boccob")
        tab._age_spin.setValue(27)
        tab._xp_spin.setValue(3000)
        tab._ability_spinboxes["INT"].setValue(16)
        tab._sync_to_model()

        assert model.character.name == "Mialee"
        assert model.character.player == "Jess"
        assert model.character.deity == "Boccob"
        assert model.character.age == 27
        assert model.character.experience == 3000
        assert model.character.ability_scores["INT"] == 16

        loaded = _round_trip(model.character, tmp_path)
        model.character = loaded
        model.character_loaded.emit(loaded.id or 0)

        assert tab._name_edit.text() == "Mialee"
        assert tab._player_edit.text() == "Jess"
        assert tab._deity_edit.text() == "Boccob"
        assert tab._age_spin.value() == 27
        assert tab._xp_spin.value() == 3000
        assert tab._ability_spinboxes["INT"].value() == 16

    def test_race_is_read_only_mirror(self, model: object) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        tab = StatsAndCharacterDetailsTab(model=model)
        assert tab._race_edit.isReadOnly()

        # The Race tab owns the value; this tab only mirrors it on refresh.
        model.character.race = "Elf"
        model.derived_stats_changed.emit()
        assert tab._race_edit.text() == "Elf"

    def test_reset_clears_fields(self, model: object) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        tab = StatsAndCharacterDetailsTab(model=model)
        tab._name_edit.setText("Temp")
        tab._sync_to_model()
        model.new_character()
        assert tab._name_edit.text() == ""
        assert tab._ability_spinboxes["STR"].value() == 10


# ---------------------------------------------------------------------------
# Race & Templates
# ---------------------------------------------------------------------------


class TestRaceAndTemplatesTab:
    def test_race_selection_persists_to_model(self, model: object) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=model)
        tab._race_combo.setCurrentText("Half-Orc")
        assert model.character.race == "Half-Orc"

    def test_templates_round_trip(self, model: object, tmp_path: Path) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=model)
        tab._available_templates = ["Celestial", "Fiendish"]
        tab._add_template()
        tab._add_template()
        assert model.character.templates == ["Celestial", "Fiendish"]

        loaded = _round_trip(model.character, tmp_path)
        model.character = loaded
        model.character_loaded.emit(loaded.id or 0)

        assert tab._race_combo.currentText() == loaded.race
        restored = [
            tab._template_list.item(i).text() for i in range(tab._template_list.count())
        ]
        assert restored == ["Celestial", "Fiendish"]


# ---------------------------------------------------------------------------
# Feats / Prestige / Skills restore-on-load
# ---------------------------------------------------------------------------


class TestCharacterBackedTabRestore:
    def test_feats_restore_on_load(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        model.character.feats = ["Power Attack", "Cleave"]
        model.character_loaded.emit(0)

        taken = [tab._taken_list.item(i).text() for i in range(tab._taken_list.count())]
        assert taken == ["Power Attack", "Cleave"]

    def test_prestige_classes_restore_on_load(self, model: object) -> None:
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        model.character.classes = [("Fighter", 4), ("Arcane Archer", 2)]
        model.character_loaded.emit(0)

        assert tab._taken_table.rowCount() == 2
        assert tab._taken_table.item(0, 0).text() == "Fighter"
        assert tab._taken_table.cellWidget(0, 1).value() == 4
        assert tab._taken_table.item(1, 0).text() == "Arcane Archer"
        assert tab._taken_table.cellWidget(1, 1).value() == 2

    def test_skills_restore_on_load(self, model: object) -> None:
        from heroforge.ui.tabs.skills import SkillsTab

        tab = SkillsTab(model=model)
        model.character.skills = {"Spot": 5.0, "Listen": 3.5}
        model.character_loaded.emit(0)

        by_name = {}
        for row, spin in enumerate(tab._rank_spinboxes):
            name = tab._table.item(row, 0).text()
            by_name[name] = spin.value()
        assert by_name["Spot"] == 5.0
        assert by_name["Listen"] == 3.5
