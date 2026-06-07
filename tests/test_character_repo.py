"""Tests for character save/load persistence (heroforge.db.character_repo)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from heroforge.db.character_repo import (
    list_characters,
    load_character,
    load_character_from_file,
    save_character,
    save_character_to_file,
)
from heroforge.db.schema import get_connection, initialize_database
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
        buffs=["Bless", "Mage Armor"],
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
    )


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "chars.db"
    connection = initialize_database(db_path)
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
