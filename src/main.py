"""HeroForge-Anew application entry point.

Run with: python -m heroforge  (or: python src/main.py)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root is the directory that contains src/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_ROOT / "heroforge.db"
_DATA_DIR = _PROJECT_ROOT / "data"


def _ensure_database() -> None:
    """Create and seed the database on first run if it does not exist."""
    if _DB_PATH.exists():
        return  # Already seeded; nothing to do.

    logger.info("Database not found – seeding from data/ for the first time…")
    try:
        from heroforge.db.seed import seed_all

        seed_all(db_path=_DB_PATH, data_dir=_DATA_DIR)
        logger.info("Database ready at %s", _DB_PATH)
    except Exception:
        logger.warning(
            "Could not seed database (data/ files may be missing). "
            "Run 'python -m heroforge.db.seed' manually to populate game data.",
            exc_info=True,
        )


def main() -> None:
    """Launch the HeroForge-Anew Qt application."""
    logging.basicConfig(level=logging.INFO)
    _ensure_database()

    from PyQt6.QtWidgets import QApplication

    from heroforge.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("HeroForge Anew")
    app.setApplicationVersion("8.0.0")
    app.setOrganizationName("HeroForge")

    # Load stylesheet
    import importlib.resources as pkg_resources

    try:
        qss_path = pkg_resources.files("heroforge.ui.styles").joinpath("default.qss")
        with pkg_resources.as_file(qss_path) as p:
            stylesheet = p.read_text(encoding="utf-8")
        app.setStyleSheet(stylesheet)
    except Exception:
        pass  # Stylesheet is cosmetic – don't crash on load failure

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
