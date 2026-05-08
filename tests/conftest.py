"""pytest configuration and shared fixtures for HeroForge-Anew tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database


@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a path to a freshly initialised SQLite database."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test_heroforge.db"
    initialize_database(db_path)
    return db_path


@pytest.fixture()
def db_conn(tmp_db: Path) -> sqlite3.Connection:
    """Return an open connection to the test database."""
    from heroforge.db.schema import get_connection
    conn = get_connection(tmp_db)
    yield conn  # type: ignore[misc]
    conn.close()
