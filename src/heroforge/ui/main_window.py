"""Main application window for HeroForge Anew.

The full application (see ``docs/conversion-plan.md`` §8) hosts one
``QWidget`` per Excel worksheet inside a ``QTabWidget``. Until those tabs are
implemented this module provides a minimal, fully functional placeholder
window so the application can be launched and visually verified inside the
isolated container runtime used for QA user-in-the-loop testing.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from heroforge import __version__

WINDOW_TITLE = "HeroForge Anew"
PLACEHOLDER_TAB_TITLE = "Welcome"
PLACEHOLDER_HEADING = "HeroForge Anew"
PLACEHOLDER_MESSAGE = (
    "The Python edition of the D&D 3.5 character builder is under "
    "construction.\n\n"
    "This window confirms the application has launched successfully inside "
    "the isolated runtime environment and is ready for QA testing."
)


class WelcomeTab(QWidget):
    """Temporary landing tab shown while the real tabs are being built."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = QLabel(PLACEHOLDER_HEADING, self)
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_font = heading.font()
        heading_font.setPointSize(heading_font.pointSize() + 12)
        heading_font.setBold(True)
        heading.setFont(heading_font)

        message = QLabel(PLACEHOLDER_MESSAGE, self)
        message.setObjectName("message")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)

        version = QLabel(f"Version {__version__}", self)
        version.setObjectName("version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addWidget(message)
        layout.addWidget(version)


class MainWindow(QMainWindow):
    """Top-level application window hosting the tab widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(960, 640)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(WelcomeTab(self), PLACEHOLDER_TAB_TITLE)
        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage("Ready")
