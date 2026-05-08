"""Enhancements tab for HeroForge-Anew.

Magic weapon and armor enhancement selection.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class EnhancementsTab(QWidget):
    """Magic weapon and armor enhancement configuration."""

    def __init__(self, model: "CharacterModel | None" = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        for item_type in ("Weapon Enhancements", "Armor Enhancements"):
            box = QGroupBox(item_type)
            box_layout = QVBoxLayout(box)
            lst = QListWidget()
            box_layout.addWidget(lst)
            btn_row = QHBoxLayout()
            btn_row.addWidget(QPushButton("Add Enhancement…"))
            rm = QPushButton("Remove")
            rm.clicked.connect(lambda _, l=lst: [l.takeItem(l.row(i)) for i in l.selectedItems()])
            btn_row.addWidget(rm)
            btn_row.addStretch()
            box_layout.addLayout(btn_row)
            inner_layout.addWidget(box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
