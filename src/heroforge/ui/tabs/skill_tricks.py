"""Skill Tricks tab for HeroForge-Anew.

Reference: Complete Scoundrel p84.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class SkillTricksTab(QWidget):
    """Skill trick selection and tracking."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
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
        inner_layout.setSpacing(10)

        avail_box = QGroupBox("Available Skill Tricks (2 SP each)")
        avail_layout = QVBoxLayout(avail_box)
        self._avail_list = QListWidget()
        avail_layout.addWidget(self._avail_list)
        inner_layout.addWidget(avail_box)

        taken_box = QGroupBox("Learned Skill Tricks")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_list = QListWidget()
        taken_layout.addWidget(self._taken_list)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Learn Selected")
        self._rm_btn = QPushButton("Forget Selected")
        self._add_btn.clicked.connect(self._learn)
        self._rm_btn.clicked.connect(self._forget)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _learn(self) -> None:
        for item in self._avail_list.selectedItems():
            self._taken_list.addItem(item.text())

    def _forget(self) -> None:
        for item in self._taken_list.selectedItems():
            self._taken_list.takeItem(self._taken_list.row(item))
