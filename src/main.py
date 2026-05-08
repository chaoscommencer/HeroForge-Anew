"""HeroForge-Anew application entry point.

Run with: python -m heroforge  (or: python src/main.py)
"""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the HeroForge-Anew Qt application."""
    from PyQt6.QtWidgets import QApplication
    from heroforge.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("HeroForge Anew")
    app.setApplicationVersion("8.0.0")
    app.setOrganizationName("HeroForge")

    # Load stylesheet
    import importlib.resources as pkg_resources
    try:
        qss_path = (
            pkg_resources.files("heroforge.ui.styles")
            .joinpath("default.qss")
        )
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
