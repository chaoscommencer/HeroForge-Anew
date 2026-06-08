"""Tests for the read-only game data-access layer (heroforge.db.data_access)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from heroforge.db.data_access import GameDataRepository
from heroforge.db.schema import get_connection, initialize_database


@pytest.fixture()
def seeded_repo(tmp_path: Path) -> GameDataRepository:
    """A repository over a small, hand-seeded game database."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.execute(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            ("PHB", "Player's Handbook"),
        )
        conn.execute(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            ("CAr", "Complete Arcane"),
        )
        conn.executemany(
            "INSERT INTO feats (name, type, description, benefit, source) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("Power Attack", "General", "Trade accuracy for damage.", "", "PHB"),
                ("Empower Spell", "Metamagic", "Boost spell effect.", "", "CAr"),
                ("Toughness", "General", "+3 hit points.", "", None),
            ],
        )
        conn.executemany(
            "INSERT INTO races (name, source) VALUES (?, ?)",
            [("Human", "PHB"), ("Elf", "PHB")],
        )
        conn.executemany(
            "INSERT INTO templates (name, source) VALUES (?, ?)",
            [("Celestial", "PHB"), ("Fiendish", "PHB")],
        )
        conn.executemany(
            "INSERT INTO spells_per_day (class_name, caster_level, spell_level, slots) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Wizard", 1, 0, 3),
                ("Wizard", 1, 1, 1),
                ("Cleric", 1, 0, 3),
            ],
        )
        conn.executemany(
            "INSERT INTO spells_known (class_name, caster_level, spell_level, count) "
            "VALUES (?, ?, ?, ?)",
            [("Sorcerer", 1, 0, 4), ("Sorcerer", 1, 1, 2)],
        )
        conn.commit()
    finally:
        conn.close()
    return GameDataRepository(db_path)


class TestAvailability:
    def test_missing_db_is_unavailable(self, tmp_path: Path) -> None:
        repo = GameDataRepository(tmp_path / "does_not_exist.db")
        assert repo.available is False
        assert repo.list_feats() == []
        assert repo.list_sources() == []

    def test_none_db_is_unavailable(self) -> None:
        repo = GameDataRepository(None)
        assert repo.available is False
        assert repo.list_caster_classes() == []


class TestSources:
    def test_list_sources(self, seeded_repo: GameDataRepository) -> None:
        sources = seeded_repo.list_sources()
        assert [s.abbreviation for s in sources] == ["CAr", "PHB"]
        assert sources[1].label == "PHB – Player's Handbook"


class TestFeats:
    def test_list_all_feats(self, seeded_repo: GameDataRepository) -> None:
        names = [f.name for f in seeded_repo.list_feats()]
        assert names == ["Empower Spell", "Power Attack", "Toughness"]

    def test_source_filter_includes_unsourced(
        self, seeded_repo: GameDataRepository
    ) -> None:
        # Filtering to PHB keeps PHB feats and the NULL-source feat, but drops CAr.
        names = [f.name for f in seeded_repo.list_feats(sources=["PHB"])]
        assert names == ["Power Attack", "Toughness"]

    def test_empty_source_filter_returns_all(
        self, seeded_repo: GameDataRepository
    ) -> None:
        assert len(seeded_repo.list_feats(sources=[])) == 3


class TestRacesTemplates:
    def test_list_races(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_races() == ["Elf", "Human"]

    def test_list_templates(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_templates() == ["Celestial", "Fiendish"]


class TestSpells:
    def test_caster_classes_union(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_caster_classes() == ["Cleric", "Sorcerer", "Wizard"]

    def test_spells_per_day(self, seeded_repo: GameDataRepository) -> None:
        slots = seeded_repo.spells_per_day("Wizard")
        assert [(s.spell_level, s.count) for s in slots] == [(0, 3), (1, 1)]

    def test_spells_known(self, seeded_repo: GameDataRepository) -> None:
        known = seeded_repo.spells_known("Sorcerer")
        assert [(s.spell_level, s.count) for s in known] == [(0, 4), (1, 2)]


def test_repository_is_read_only(
    seeded_repo: GameDataRepository, tmp_path: Path
) -> None:
    """Listing data must never mutate the backing database."""
    assert seeded_repo.db_path is not None
    conn = get_connection(seeded_repo.db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM feats").fetchone()[0]
    finally:
        conn.close()
    seeded_repo.list_feats()
    seeded_repo.list_races()
    conn = get_connection(seeded_repo.db_path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM feats").fetchone()[0]
    finally:
        conn.close()
    assert before == after == 3


def test_query_tolerates_missing_table(tmp_path: Path) -> None:
    """A database file without the expected tables yields empty results."""
    db_path = tmp_path / "bare.db"
    sqlite3.connect(db_path).close()  # empty file, no schema
    repo = GameDataRepository(db_path)
    assert repo.list_feats() == []
    assert repo.list_caster_classes() == []
