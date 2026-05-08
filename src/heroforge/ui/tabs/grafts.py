"""Grafts tab for HeroForge-Anew.

Reference: Fiend Folio, Libris Mortis, Arms & Equipment Guide.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class GraftsTab(QWidget):
    """Graft selection and management."""

    def __init__(self, model: "CharacterModel | None" = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QLabel(
            "<b>Grafts</b> are body modifications that grant special abilities. "
            "Each graft occupies a body slot."
        ))

        taken_box = QGroupBox("Applied Grafts")
        taken_layout = QVBoxLayout(taken_box)
        self._graft_list = QListWidget()
        taken_layout.addWidget(self._graft_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Graft…")
        self._rm_btn = QPushButton("Remove Selected")
        self._rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        layout.addWidget(taken_box)
        layout.addStretch()

    def _remove(self) -> None:
        for item in self._graft_list.selectedItems():
            self._graft_list.takeItem(self._graft_list.row(item))
