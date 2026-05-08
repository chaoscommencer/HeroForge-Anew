"""Prestige Classes tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class PrestigeClassesTab(QWidget):
    """Prestige class selection and level tracking."""

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
        inner_layout.setSpacing(10)

        # Available prestige classes
        avail_box = QGroupBox("Available Prestige Classes")
        avail_layout = QVBoxLayout(avail_box)
        self._avail_list = QListWidget()
        avail_layout.addWidget(QLabel("Classes you currently qualify for:"))
        avail_layout.addWidget(self._avail_list)
        inner_layout.addWidget(avail_box)

        # Taken prestige classes
        taken_box = QGroupBox("Taken Prestige Classes")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_table = QTableWidget(0, 3)
        self._taken_table.setHorizontalHeaderLabels(["Class", "Levels", "Remove"])
        self._taken_table.horizontalHeader().setStretchLastSection(True)
        taken_layout.addWidget(self._taken_table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Selected Class")
        self._add_btn.clicked.connect(self._add_prestige_class)
        btn_row.addWidget(self._add_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _add_prestige_class(self) -> None:
        selected = self._avail_list.selectedItems()
        if not selected:
            return
        name = selected[0].text()
        row = self._taken_table.rowCount()
        self._taken_table.insertRow(row)
        self._taken_table.setItem(row, 0, QTableWidgetItem(name))
        spin = QSpinBox()
        spin.setRange(1, 10)
        self._taken_table.setCellWidget(row, 1, spin)
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda _, r=row: self._taken_table.removeRow(r))
        self._taken_table.setCellWidget(row, 2, rm_btn)
