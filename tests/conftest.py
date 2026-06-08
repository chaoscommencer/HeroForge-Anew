"""Shared pytest fixtures for HeroForge Anew.

Forces Qt to use the headless ``offscreen`` platform so widget smoke tests run
in CI and inside the isolated container runtime without a real display.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Provide a single ``QApplication`` instance for the whole test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

