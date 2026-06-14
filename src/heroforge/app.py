"""HeroForge-Anew application launch logic.

This module holds the single source of truth for starting the Qt application.
It is invoked from three places that all call :func:`main`:

* ``heroforge`` console script  → ``main:main`` (see ``src/main.py`` shim)
* ``python -m heroforge``        → ``heroforge/__main__.py``
* ``python src/main.py``         → ``src/main.py`` shim
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from heroforge.env_paths import dir_from_env
from heroforge.logging_config import configure_logging

logger = logging.getLogger(__name__)

# Project root is the directory that contains src/ (…/src/heroforge/app.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"


def _data_home() -> Path | None:
    """Return the writable directory for user data (the game DB and saves).

    Defaults to the project root for local development, but can be redirected
    via the ``HEROFORGE_DATA_DIR`` environment variable.  The containerised QA
    stack sets it to a dedicated writable volume (``/app/userdata``) so the rest
    of the container filesystem can be mounted read-only without breaking
    first-launch database seeding or character saves.  The directory is created
    if it could be resolved.  Returns ``None`` only if the override resolved to
    nothing usable (the configured default is non-``None``, so in practice this
    always returns a path).
    """
    data_home = dir_from_env("HEROFORGE_DATA_DIR", _PROJECT_ROOT)
    if data_home is not None:
        data_home.mkdir(parents=True, exist_ok=True)
    return data_home


def _data_source_dir() -> Path | None:
    """Return the read-only directory holding the seed source data.

    Defaults to ``<project root>/data`` (the bundled CSV/XLSX game tables), but
    can be redirected via the ``HEROFORGE_DATA_SOURCE_DIR`` environment variable
    to point at an alternate copy of the seed inputs.  Unlike
    :func:`_data_home` this directory is only ever read from, so it is **not**
    created if missing — a bad path simply surfaces as a seeding failure.
    """
    return dir_from_env("HEROFORGE_DATA_SOURCE_DIR", _DATA_DIR)


def _db_path() -> Path | None:
    """Return the path to the seeded game database under :func:`_data_home`.

    Returns ``None`` when no data home could be resolved (see :func:`_data_home`).
    """
    data_home = _data_home()
    return data_home / "heroforge.db" if data_home is not None else None


def _ensure_database() -> None:
    """Create and seed the database on first run if it does not exist."""
    db_path = _db_path()
    # The configured defaults are non-None, so a missing path here would mean a
    # misconfiguration rather than a normal state — fail loudly at the boundary.
    assert db_path is not None, "could not resolve the user data directory"
    if db_path.exists():
        return  # Already seeded; nothing to do.

    logger.info("Database not found – seeding from data/ for the first time…")
    try:
        from heroforge.db.seed import seed_all

        data_source = _data_source_dir()
        assert data_source is not None, "could not resolve the seed source directory"
        seed_all(db_path=db_path, data_dir=data_source)
        logger.info("Database ready at %s", db_path)
    except Exception:
        logger.warning(
            "Could not seed database (data/ files may be missing). "
            "Run 'python -m heroforge.db.seed' manually to populate game data.",
            exc_info=True,
        )


def main() -> None:
    """Launch the HeroForge-Anew Qt application."""
    configure_logging()
    _ensure_database()

    from PyQt6.QtWidgets import QApplication

    from heroforge.signals import install_signal_quit
    from heroforge.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("HeroForge Anew")
    app.setApplicationVersion("8.0.0")
    app.setOrganizationName("HeroForge")

    # Exit cleanly (status 0) on SIGTERM/SIGINT — e.g. when the container stops
    # via `docker compose down` — instead of being killed by the default signal
    # action (status 143). install_signal_quit wires the signals into the Qt
    # event loop via a wakeup-fd socket watched by a QSocketNotifier, so the quit
    # happens immediately with no polling. The returned guard must stay referenced
    # for the app's lifetime or the mechanism is garbage-collected away.
    _signal_guard = install_signal_quit(app)

    # Load stylesheet
    import importlib.resources as pkg_resources

    try:
        qss_path = pkg_resources.files("heroforge.ui.styles").joinpath("default.qss")
        with pkg_resources.as_file(qss_path) as p:
            stylesheet = p.read_text(encoding="utf-8")
        app.setStyleSheet(stylesheet)
    except Exception:
        pass  # Stylesheet is cosmetic – don't crash on load failure

    db_path = _db_path()
    assert db_path is not None, "could not resolve the user data directory"
    window = MainWindow(game_db_path=str(db_path))
    window.show()

    exit_code = app.exec()
    # Keeps _signal_guard referenced until the event loop exits (otherwise it
    # could be garbage-collected mid-run) and restores the prior signal state.
    _signal_guard.uninstall()
    sys.exit(exit_code)
