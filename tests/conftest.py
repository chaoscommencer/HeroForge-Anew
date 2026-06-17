"""pytest configuration and shared fixtures for HeroForge-Anew tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
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
def db_conn(tmp_db: Path) -> Iterator[sqlite3.Connection]:
    """Return an open connection to the test database."""
    from heroforge.db.schema import get_connection

    conn = get_connection(tmp_db)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    """Provide a single offscreen QApplication for widget tests.

    Skips the whole test if PyQt6 cannot be imported or a Qt platform plugin is
    unavailable (e.g. a headless CI without the required system libraries).
    """
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PyQt6 unavailable: {exc}")

    app = QApplication.instance()
    created = False
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"Cannot start QApplication: {exc}")
        created = True
    try:
        yield app
    finally:
        if created:
            app.quit()
