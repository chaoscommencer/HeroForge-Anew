"""Maneuvers & Stances tab for HeroForge-Anew.

Reference: Tome of Battle.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_DISCIPLINES = ["Devoted Spirit", "Diamond Mind", "Iron Heart", "Setting Sun",
                "Shadow Hand", "Stone Dragon", "Tiger Claw", "White Raven"]


class ManeuversAndStancesTab(QWidget):
    """Tome of Battle maneuver and stance management."""

    def __init__(self, model: "CharacterModel | None" = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        sub_tabs = QTabWidget()

        # Maneuvers tab
        man_widget = QWidget()
        man_layout = QVBoxLayout(man_widget)
        known_box = QGroupBox("Known Maneuvers")
        known_layout = QVBoxLayout(known_box)
        self._known_list = QListWidget()
        known_layout.addWidget(self._known_list)
        man_layout.addWidget(known_box)
        readied_box = QGroupBox("Readied Maneuvers")
        readied_layout = QVBoxLayout(readied_box)
        self._readied_list = QListWidget()
        readied_layout.addWidget(self._readied_list)
        man_layout.addWidget(readied_box)
        sub_tabs.addTab(man_widget, "Maneuvers")

        # Stances tab
        stance_widget = QWidget()
        stance_layout = QVBoxLayout(stance_widget)
        stance_box = QGroupBox("Known Stances")
        stance_box_layout = QVBoxLayout(stance_box)
        self._stance_list = QListWidget()
        stance_box_layout.addWidget(self._stance_list)
        stance_layout.addWidget(stance_box)
        sub_tabs.addTab(stance_widget, "Stances")

        layout.addWidget(sub_tabs)
