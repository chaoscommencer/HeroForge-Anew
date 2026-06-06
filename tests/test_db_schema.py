"""Tests for heroforge.db.schema.

Verifies that initialize_database creates all required tables.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from heroforge.db.schema import SCHEMA_SQL, initialize_database

# All table names that must exist after initialization
_EXPECTED_TABLES = [
    # Game data tables
    "races",
    "templates",
    "classes",
    "class_skills",
    "class_abilities",
    "class_weapons_armor",
    "prestige_class_prerequisites",
    "feats",
    "feat_prerequisites",
    "skills",
    "skill_synergies",
    "skill_tricks",
    "spells",
    "spells_per_day",
    "spells_known",
    "psionic_powers",
    "soulmelds",
    "soulmeld_abilities",
    "incarnum_abilities",
    "variants",
    "vestiges",
    "marshal_auras",
    "deities",
    "domains",
    "grafts",
    "racial_abilities",
    "graft_abilities",
    "maneuvers",
    "weapons",
    "armor",
    "magic_enhancements",
    "magic_equipment",
    "creatures",
    "tables",
    "languages",
    "traits",
    "flaws",
    "sources",
    # Character save tables
    "characters",
    "character_ability_scores",
    "character_classes",
    "character_feats",
    "character_skills",
    "character_spells_prepared",
    "character_spells_known",
    "character_soulmelds",
    "character_equipment",
    "character_buffs",
    "character_languages",
    "character_traits",
    "character_maneuvers",
    "character_notes",
]

_EXPECTED_INDEXES = [
    "idx_races_name",
    "idx_classes_name",
    "idx_feats_name",
    "idx_skills_name",
    "idx_spells_name",
    "idx_spells_class",
    "idx_weapons_name",
    "idx_creatures_name",
    "idx_soulmelds_name",
]


class TestSchemaSQL:
    def test_schema_sql_is_string(self) -> None:
        assert isinstance(SCHEMA_SQL, str)
        assert len(SCHEMA_SQL) > 100


class TestInitializeDatabase:
    def test_creates_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        assert not db_path.exists()
        conn = initialize_database(db_path)
        conn.close()
        assert db_path.exists()

    def test_returns_connection(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = initialize_database(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn1 = initialize_database(db_path)
        conn1.close()
        # Should not raise on second call
        conn2 = initialize_database(db_path)
        conn2.close()

    def test_existing_db_not_modified(self, tmp_path: Path) -> None:
        db_path = tmp_path / "existing.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE custom_table (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO custom_table (v) VALUES ('x')")
        conn.commit()
        conn.close()

        conn2 = initialize_database(db_path)

        # Existing data must be preserved regardless of schema state.
        count = conn2.execute("SELECT COUNT(*) FROM custom_table").fetchone()
        assert count is not None
        assert count[0] == 1

        # The DB was missing schema tables, so they should now have been added
        # (all CREATE TABLE statements use IF NOT EXISTS – no data is harmed).
        schema_table = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='races'"
        ).fetchone()
        assert schema_table is not None
        conn2.close()

    def test_partial_schema_completed(self, tmp_path: Path) -> None:
        """A DB that was only partially initialized gets all missing tables added."""
        db_path = tmp_path / "partial.db"
        # Simulate an interrupted initialization: only 'races' was created.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE races (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)"
        )
        conn.commit()
        conn.close()

        conn2 = initialize_database(db_path)

        # All expected tables must now exist.
        rows = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        existing = {row[0] for row in rows}
        assert frozenset(_EXPECTED_TABLES).issubset(existing)
        conn2.close()


class TestAllTablesExist:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        db_path = tmp_path / "schema_test.db"
        conn = initialize_database(db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        self._tables = {row[0] for row in rows}
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        self._indexes = {row[0] for row in idx_rows}
        conn.close()

    @pytest.mark.parametrize("table_name", _EXPECTED_TABLES)
    def test_table_exists(self, table_name: str) -> None:
        assert table_name in self._tables, f"Missing table: {table_name}"

    @pytest.mark.parametrize("index_name", _EXPECTED_INDEXES)
    def test_index_exists(self, index_name: str) -> None:
        assert index_name in self._indexes, f"Missing index: {index_name}"


class TestGetConnection:
    def test_row_factory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = initialize_database(db_path)
        # Insert a row and verify row_factory gives Row objects
        conn.execute(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            ("PHB", "Player's Handbook"),
        )
        conn.commit()
        row = conn.execute("SELECT abbreviation, full_name FROM sources").fetchone()
        assert row is not None
        assert row["abbreviation"] == "PHB"
        conn.close()

    def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = initialize_database(db_path)
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result is not None
        assert result[0] == 1
        conn.close()
