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
            "con_score, int_score, wis_score, cha_score, armor_class, source) VALUES "
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
