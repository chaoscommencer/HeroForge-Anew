"""Application bootstrap for HeroForge Anew.

Provides :func:`main`, the single entry point used by ``python -m heroforge``,
the ``heroforge`` console script, and the container runtime entrypoint.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from heroforge.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    """Launch the HeroForge Anew application.

    :param argv: Command-line arguments (defaults to :data:`sys.argv`).
    :returns: The Qt application exit code.
    """
    args = list(sys.argv if argv is None else argv)

    app = QApplication(args)
    app.setApplicationName("HeroForge Anew")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":  # pragma: no cover - executed via the entry point
    raise SystemExit(main())
