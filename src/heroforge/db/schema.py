"""SQLite schema engine for HeroForge-Anew.

The DDL itself lives in two dedicated modules so that read-only game data and
volatile, user-owned character data never share a definition (nor a database
file):

* :data:`GAME_SCHEMA_SQL` (from :mod:`heroforge.db.game_schema`) defines the
  source-of-truth game data tables.  It is applied to ``heroforge.db`` by
  :func:`initialize_database`.  Think of this database as ROM: it is only ever
  rewritten when the original Excel workbook is re-imported.
* :data:`CHARACTER_SCHEMA_SQL` (from :mod:`heroforge.db.character_schema`)
  defines the per-character save tables.  It is applied to a standalone ``.hfc``
  save file by :func:`initialize_character_database`.  Think of these files as
  RAM: each one holds a single user's volatile character data.

This module provides only the shared connection/initialisation plumbing and
re-exports the two schemas for backwards compatibility.  Keeping the two DDL
halves apart protects the application's source data from being mutated by
ordinary character edits.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from heroforge.db.character_schema import CHARACTER_SCHEMA_SQL, CHARACTER_TABLES
from heroforge.db.game_schema import GAME_INDEXES, GAME_SCHEMA_SQL, GAME_TABLES

# Backwards-compatible aliases: ``heroforge.db`` (the source of truth) only ever
# carries the game data schema, and historical imports expect these names here.
SCHEMA_SQL: str = GAME_SCHEMA_SQL
_GAME_TABLES: frozenset[str] = GAME_TABLES
_GAME_INDEXES: frozenset[str] = GAME_INDEXES
_CHARACTER_TABLES: frozenset[str] = CHARACTER_TABLES

__all__ = [
    "CHARACTER_SCHEMA_SQL",
    "GAME_SCHEMA_SQL",
    "SCHEMA_SQL",
    "get_connection",
    "initialize_character_database",
    "initialize_database",
]


def get_connection(db_path: str | Path = "heroforge.db") -> sqlite3.Connection:
    """Return a SQLite connection with foreign keys enabled and row_factory set.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def _apply_schema_if_needed(
    conn: sqlite3.Connection,
    schema_sql: str,
    expected_tables: frozenset[str],
    expected_indexes: frozenset[str],
) -> None:
    """Apply *schema_sql* to *conn* unless every expected object already exists.

    Every ``CREATE`` statement uses ``IF NOT EXISTS`` so existing tables and
    their data are never affected.
    """
    existing_tables: frozenset[str] = frozenset(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    existing_indexes: frozenset[str] = frozenset(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    if expected_tables.issubset(existing_tables) and expected_indexes.issubset(
        existing_indexes
    ):
        return

    conn.executescript(schema_sql)
    conn.commit()


def initialize_database(db_path: str | Path = "heroforge.db") -> sqlite3.Connection:
    """Create the game database file (if absent) and apply the game schema.

    This is the application's source-of-truth database (``heroforge.db``).  It
    holds **only** game data tables; volatile character data is stored
    separately in ``.hfc`` files (see :func:`initialize_character_database`).

    If the database file already exists and contains all expected game tables,
    this function returns the open connection without re-applying the schema.
    If the file exists but is missing any expected tables (e.g. due to an
    interrupted initialization or corruption), the schema is applied so all
    missing tables are created.  Existing tables and their data are never
    affected because every ``CREATE TABLE`` statement uses ``IF NOT EXISTS``.

    Args:
        db_path: Path where the SQLite file will be created/opened.

    Returns:
        An open :class:`sqlite3.Connection` to the initialised database.
    """
    conn = get_connection(Path(db_path))
    _apply_schema_if_needed(conn, GAME_SCHEMA_SQL, _GAME_TABLES, _GAME_INDEXES)
    return conn


def initialize_character_database(
    db_path: str | Path,
) -> sqlite3.Connection:
    """Create a character save database file (if absent) and apply its schema.

    Character databases (``.hfc`` files) are independent of the source-of-truth
    game database: each one holds a single user's volatile character data and
    carries **only** the ``character_*`` save tables.

    Args:
        db_path: Path where the SQLite save file will be created/opened.

    Returns:
        An open :class:`sqlite3.Connection` to the initialised save database.
    """
    conn = get_connection(Path(db_path))
    # Character save databases define no indexes, so none are validated here.
    _apply_schema_if_needed(conn, CHARACTER_SCHEMA_SQL, _CHARACTER_TABLES, frozenset())
    return conn
