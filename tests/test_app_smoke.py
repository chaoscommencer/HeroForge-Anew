"""Smoke tests for the application shell used by the isolated runtime.

These verify that the PyQt application constructs without errors on a headless
``offscreen`` platform, which is exactly how it is launched inside the
container runtime before QA interacts with it over noVNC.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from heroforge.ui.main_window import (
    PLACEHOLDER_TAB_TITLE,
    WINDOW_TITLE,
    MainWindow,
)


def test_main_window_constructs(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.windowTitle() == WINDOW_TITLE
    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == PLACEHOLDER_TAB_TITLE


def test_main_window_has_central_widget(qapp: QApplication) -> None:
    window = MainWindow()
    assert window.centralWidget() is window.tabs
