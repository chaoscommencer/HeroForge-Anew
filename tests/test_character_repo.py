"""Tests for character save/load persistence (heroforge.db.character_repo)."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from heroforge.db.character_repo import (
    list_characters,
    load_character,
    load_character_from_file,
    save_character,
    save_character_to_file,
)
from heroforge.db.schema import get_connection, initialize_character_database
from heroforge.models.character import Character


def _sample_character() -> Character:
    return Character(
        name="Aedan Brightblade",
        player="Sam",
        campaign="Greyhawk",
        alignment="LG",
        deity="Pelor",
        homeland="Verbobonc",
        race="Human",
        templates=["Half-Celestial", "Fiendish"],
        gender="Male",
        age=27,
        height="6'0\"",
        weight="185 lb",
        eyes="Blue",
        hair="Brown",
        skin="Tan",
        experience=15000,
        notes="A redemption-seeking fighter/wizard.",
        ability_scores={
            "STR": 16,
            "DEX": 14,
            "CON": 13,
            "INT": 12,
            "WIS": 10,
            "CHA": 8,
        },
        classes=[("Fighter", 5), ("Wizard", 2)],
        feats=["Power Attack", "Cleave", "Combat Casting"],
        skills={"Climb": 5.0, "Jump": 3.5, "Spellcraft": 4.0},
        buffs=[
            {"id": str(uuid.uuid4()), "name": "Bless"},
            {"id": str(uuid.uuid4()), "name": "Mage Armor"},
        ],
        equipment=[
            {
                "item_name": "Longsword",
                "quantity": 1,
                "weight": 4.0,
                "equipped": True,
                "slot": "weapon",
                "notes": "Masterwork",
            },
            {
                "item_name": "Backpack",
                "quantity": 1,
                "weight": 2.0,
                "equipped": False,
                "slot": None,
                "notes": "Holds gear",
            },
        ],
        languages=["Common", "Elven", "Celestial"],
        spells_known=[
            {"class_name": "Wizard", "spell_level": 1, "spell_name": "Magic Missile"},
            {"class_name": "Wizard", "spell_level": 0, "spell_name": "Light"},
        ],
        spells_prepared=[
            {"class_name": "Wizard", "spell_level": 1, "spell_name": "Magic Missile"},
        ],
        soulmelds=[
            {
                "soulmeld_name": "Incarnate Avatar",
                "chakra_bound": "Crown",
                "essentia_invested": 2,
            },
        ],
        maneuvers=[
            {"maneuver_name": "Steel Wind", "readied": True},
            {"maneuver_name": "Punishing Stance", "readied": False},
        ],
        grafts=[
            {
                "graft_name": "Fiendish Arm",
                "body_slot": "arms",
                "notes": "Grants a claw attack",
            },
        ],
        traits=[
            {"trait_name": "Aggressive", "is_flaw": False},
            {"trait_name": "Shaky", "is_flaw": True},
        ],
        variants=[
            "Spell Sense",
            {
                "variant_name": "Spiritual Totem",
                "class_name": "Barbarian",
                "notes": "Wolf totem",
            },
        ],
        domains=["Healing", "Sun"],
        vestiges=[
            {"vestige_name": "Naberius", "level": 4, "bound": True},
        ],
        marshal_auras=[
            {"aura_name": "Motivate Dexterity", "aura_type": "major", "active": True},
        ],
        skill_tricks=["Acrobatic Backstab"],
        psionic_powers=[
            {"class_name": "Psion", "power_level": 1, "power_name": "Mind Thrust"},
        ],
        companions=[
            {
                "companion_type": "Animal Companion",
                "name": "Rex",
                "creature": "Wolf",
                "notes": "Loyal scout",
            },
        ],
        options={"Gestalt": "true", "Fractional BAB": "true"},
        wealth={"platinum": 2.0, "gold": 150.0, "silver": 30.0},
        attacks=[
            {
                "weapon_name": "Longsword",
                "attack_bonus": "+8/+3",
                "damage": "1d8+4",
                "critical": "19-20/x2",
                "range_increment": None,
                "damage_type": "slashing",
                "ammunition": None,
                "notes": "Masterwork",
            },
        ],
        enhancements=[
            {
                "target": "Speed",
                "bonus_type": "Circumstance",
                "value": 10,
                "notes": "Boots of Striding",
            },
        ],
        custom_content=[
            {
                "content_type": "race",
                "name": "Half-Dragon (Brass)",
                "definition": '{"size": "Medium"}',
            },
        ],
        custom_armor=[
            {
                "name": "Masterwork Breastplate",
                "type": "Armor",
                "ac_bonus": 5,
                "max_dex_bonus": 3,
                "check_penalty": -3,
                "arcane_spell_failure": 25,
                "weight": 30.0,
            },
        ],
        custom_weapons=[
            {
                "name": "Ancestral Sword",
                "category": "Martial",
                "damage": "1d8",
                "critical": "19-20/x2",
                "range_increment": 0,
                "damage_type": "Slashing",
                "weight": 4.0,
            },
        ],
        custom_items=[
            {
                "name": "Ring of the Archmagi",
                "slot": "Ring",
                "description": "Homebrew ring granting +4 to all saves",
                "weight": 0.0,
            },
        ],
        lg_records=[
            {
                "record_type": "game_log",
                "event_date": "2024-02-02",
                "description": "Defeated bandits",
                "gp_change": 150.0,
                "xp_change": 450.0,
                "notes": "AR for The Bandit Kings",
            },
        ],
        game_log=[
            {"timestamp": "2024-01-01T10:00:00", "content": "Set out from Verbobonc."},
        ],
    )


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "chars.hfc"
    connection = initialize_character_database(db_path)
    yield connection
    connection.close()


class TestSaveLoadRoundTrip:
    def test_save_assigns_id(self, conn: sqlite3.Connection) -> None:
        char = _sample_character()
        assert char.id is None
        cid = save_character(conn, char)
        assert cid >= 1
        assert char.id == cid

    def test_round_trip_identity(self, conn: sqlite3.Connection) -> None:
        char = _sample_character()
        cid = save_character(conn, char)
        loaded = load_character(conn, cid)

        assert loaded.name == char.name
        assert loaded.player == char.player
        assert loaded.campaign == char.campaign
        assert loaded.alignment == char.alignment
        assert loaded.deity == char.deity
        assert loaded.homeland == char.homeland
        assert loaded.race == char.race
        assert loaded.templates == char.templates
        assert loaded.gender == char.gender
        assert loaded.age == char.age
        assert loaded.height == char.height
        assert loaded.weight == char.weight
        assert loaded.eyes == char.eyes
        assert loaded.hair == char.hair
        assert loaded.skin == char.skin
        assert loaded.experience == char.experience
        assert loaded.notes == char.notes
        assert loaded.ability_scores == char.ability_scores
        assert loaded.classes == char.classes
        assert loaded.feats == char.feats
        assert loaded.skills == char.skills
        assert loaded.buffs == char.buffs
        assert loaded.equipment == char.equipment
        assert loaded.languages == char.languages
        assert loaded.spells_known == char.spells_known
        assert loaded.spells_prepared == char.spells_prepared
        assert loaded.soulmelds == char.soulmelds
        assert loaded.maneuvers == char.maneuvers
        assert loaded.grafts == char.grafts
        assert loaded.traits == char.traits
        assert loaded.variants == char.variants
        assert loaded.domains == char.domains
        assert loaded.vestiges == char.vestiges
        assert loaded.marshal_auras == char.marshal_auras
        assert loaded.skill_tricks == char.skill_tricks
        assert loaded.psionic_powers == char.psionic_powers
        assert loaded.companions == char.companions
        assert loaded.options == char.options
        assert loaded.wealth == char.wealth
        assert loaded.attacks == char.attacks
        assert loaded.enhancements == char.enhancements
        assert loaded.custom_content == char.custom_content
        assert loaded.custom_armor == char.custom_armor
        assert loaded.custom_weapons == char.custom_weapons
        assert loaded.custom_items == char.custom_items
        assert loaded.lg_records == char.lg_records
        assert loaded.game_log == char.game_log

    def test_writes_related_rows(self, conn: sqlite3.Connection) -> None:
        char = _sample_character()
        cid = save_character(conn, char)

        counts = {
            "character_ability_scores": 6,
            "character_classes": 2,
            "character_feats": 3,
            "character_skills": 3,
            "character_equipment": 2,
            "character_buffs": 2,
            "character_languages": 3,
            "character_spells_known": 2,
            "character_spells_prepared": 1,
            "character_soulmelds": 1,
            "character_maneuvers": 2,
            "character_grafts": 1,
            "character_traits": 2,
            "character_variants": 2,
            "character_domains": 2,
            "character_vestiges": 1,
            "character_marshal_auras": 1,
            "character_skill_tricks": 1,
            "character_psionic_powers": 1,
            "character_companions": 1,
            "character_options": 2,
            "character_wealth": 3,
            "character_attacks": 1,
            "character_enhancements": 1,
            "character_custom_content": 1,
            "character_custom_armor": 1,
            "character_custom_weapons": 1,
            "character_custom_items": 1,
            "character_lg_records": 1,
            "character_notes": 1,
        }
        for table, expected in counts.items():
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE character_id = ?", (cid,)
            ).fetchone()[0]
            assert n == expected, table

    def test_update_replaces_related_rows(self, conn: sqlite3.Connection) -> None:
        char = _sample_character()
        cid = save_character(conn, char)

        # Mutate and re-save the same character.
        char.name = "Aedan the Redeemed"
        char.feats = ["Dodge"]
        char.classes = [("Paladin", 7)]
        save_character(conn, char)

        loaded = load_character(conn, cid)
        assert loaded.id == cid
        assert loaded.name == "Aedan the Redeemed"
        assert loaded.feats == ["Dodge"]
        assert loaded.classes == [("Paladin", 7)]
        # No duplicate / orphaned rows from the first save.
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM character_feats WHERE character_id = ?",
                (cid,),
            ).fetchone()[0]
            == 1
        )

    def test_load_unknown_raises(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(KeyError):
            load_character(conn, 999)

    def test_list_characters(self, conn: sqlite3.Connection) -> None:
        a = Character(name="A")
        b = Character(name="B")
        save_character(conn, a)
        save_character(conn, b)
        listed = list_characters(conn)
        assert (a.id, "A") in listed
        assert (b.id, "B") in listed


class TestHfcFile:
    def test_save_and_load_file(self, tmp_path: Path) -> None:
        char = _sample_character()
        path = tmp_path / "hero.hfc"
        save_character_to_file(char, path)
        assert path.exists()

        loaded = load_character_from_file(path)
        assert loaded.name == char.name
        assert loaded.classes == char.classes
        assert loaded.skills == char.skills
        assert loaded.equipment == char.equipment
        assert loaded.languages == char.languages

    def test_resave_keeps_single_character(self, tmp_path: Path) -> None:
        char = _sample_character()
        path = tmp_path / "hero.hfc"
        save_character_to_file(char, path)
        char.name = "Renamed"
        save_character_to_file(char, path)

        conn = get_connection(path)
        try:
            n = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        finally:
            conn.close()
        assert n == 1
        assert load_character_from_file(path).name == "Renamed"

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_character_from_file(tmp_path / "nope.hfc")
