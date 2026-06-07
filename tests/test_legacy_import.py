"""Tests for the legacy ``.hfg`` importer and migration to ``.hfc``."""

from __future__ import annotations

from pathlib import Path

from heroforge.db.character_repo import (
    load_character_from_file,
    save_character_to_file,
)
from heroforge.logic.legacy_import import import_hfg, parse_hfg

_FIXTURE = Path(__file__).parent / "fixtures" / "legacy_sample.hfg"


class TestParseHfg:
    def test_top_level_fields(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.id is None
        assert char.name == "Aedan Brightblade"
        assert char.player == "Sam"
        assert char.campaign == "Greyhawk"
        assert char.alignment == "LG"
        assert char.deity == "Pelor"
        assert char.homeland == "Verbobonc"
        assert char.race == "Human"
        assert char.templates == ["Half-Celestial", "Fiendish"]
        assert char.gender == "Male"
        assert char.age == 27
        assert char.height == "6'0\""
        assert char.weight == "185 lb"
        assert char.experience == 15000

    def test_ability_scores(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.ability_scores == {
            "STR": 16,
            "DEX": 14,
            "CON": 13,
            "INT": 12,
            "WIS": 10,
            "CHA": 8,
        }

    def test_ordered_collections(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.classes == [("Fighter", 5), ("Wizard", 2)]
        assert char.feats == ["Power Attack", "Cleave", "Combat Casting"]
        assert char.languages == ["Common", "Elven", "Celestial"]
        assert char.buffs == ["Bless", "Mage Armor"]
        assert char.total_level == 7

    def test_skills_and_equipment(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.skills == {"Climb": 5.0, "Jump": 3.5, "Spellcraft": 4.0}
        assert char.equipment[0] == {
            "item_name": "Longsword",
            "quantity": 1,
            "weight": 4.0,
            "equipped": True,
            "slot": "weapon",
            "notes": "Masterwork",
        }
        assert char.equipment[2]["item_name"] == "Potion of Cure Light Wounds"
        assert char.equipment[2]["quantity"] == 3

    def test_notes_preserved(self) -> None:
        char = import_hfg(_FIXTURE)
        assert "redemption" in char.notes
        assert "spellbook" in char.notes

    def test_spells(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.spells_known == [
            {"class_name": "Wizard", "spell_level": 1, "spell_name": "Magic Missile"},
            {"class_name": "Wizard", "spell_level": 0, "spell_name": "Light"},
        ]
        assert char.spells_prepared == [
            {"class_name": "Wizard", "spell_level": 1, "spell_name": "Magic Missile"},
        ]

    def test_soulmelds(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.soulmelds == [
            {
                "soulmeld_name": "Incarnate Avatar",
                "chakra_bound": "Crown",
                "essentia_invested": 2,
            },
        ]

    def test_maneuvers_and_stances(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.maneuvers == [
            {"maneuver_name": "Steel Wind", "readied": True},
            {"maneuver_name": "Punishing Stance", "readied": True},
        ]

    def test_grafts(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.grafts == [
            {
                "graft_name": "Fiendish Arm",
                "body_slot": "arms",
                "notes": "Grants a claw attack",
            },
        ]

    def test_traits_and_flaws(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.traits == [
            {"trait_name": "Aggressive", "is_flaw": False},
            {"trait_name": "Shaky", "is_flaw": True},
        ]

    def test_game_log(self) -> None:
        char = import_hfg(_FIXTURE)
        assert char.game_log == [
            {"timestamp": "2024-01-01T10:00:00", "content": "Set out from Verbobonc."},
        ]

    def test_empty_input(self) -> None:
        char = parse_hfg("")
        assert char.name == ""
        assert char.classes == []


class TestLegacyMigration:
    def test_import_then_save_and_reload(self, tmp_path: Path) -> None:
        # §9.1 cycle: import legacy save, migrate to new format, reload.
        imported = import_hfg(_FIXTURE)
        path = tmp_path / "migrated.hfc"
        save_character_to_file(imported, path)

        reloaded = load_character_from_file(path)
        assert reloaded.name == imported.name
        assert reloaded.classes == imported.classes
        assert reloaded.feats == imported.feats
        assert reloaded.skills == imported.skills
        assert reloaded.equipment == imported.equipment
        assert reloaded.buffs == imported.buffs
        assert reloaded.languages == imported.languages
        assert reloaded.ability_scores == imported.ability_scores
        assert reloaded.notes == imported.notes
        assert reloaded.spells_known == imported.spells_known
        assert reloaded.spells_prepared == imported.spells_prepared
        assert reloaded.soulmelds == imported.soulmelds
        assert reloaded.maneuvers == imported.maneuvers
        assert reloaded.grafts == imported.grafts
        assert reloaded.traits == imported.traits
        assert reloaded.game_log == imported.game_log
