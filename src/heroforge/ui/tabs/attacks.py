"""Attacks tab for HeroForge-Anew."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class AttacksTab(QWidget):
    """Weapon attack and damage configuration."""

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

        # BAB and combat stats
        combat_box = QGroupBox("Combat Statistics")
        combat_form = QFormLayout(combat_box)
        self._bab_lbl = QLabel("0")
        self._melee_lbl = QLabel("0")
        self._ranged_lbl = QLabel("0")
        self._grapple_lbl = QLabel("0")
        combat_form.addRow("Base Attack Bonus:", self._bab_lbl)
        combat_form.addRow("Melee Attack:", self._melee_lbl)
        combat_form.addRow("Ranged Attack:", self._ranged_lbl)
        combat_form.addRow("Grapple:", self._grapple_lbl)
        inner_layout.addWidget(combat_box)

        # Weapon list
        weapons_box = QGroupBox("Equipped Weapons")
        weapons_layout = QVBoxLayout(weapons_box)
        headers = ["Weapon", "Attack Bonus", "Damage", "Crit", "Range", "Type"]
        self._weapons_table = QTableWidget(0, len(headers))
        self._weapons_table.setHorizontalHeaderLabels(headers)
        self._weapons_table.horizontalHeader().setStretchLastSection(True)
        weapons_layout.addWidget(self._weapons_table)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Weapon")
        rm_btn = QPushButton("Remove Selected")
        add_btn.clicked.connect(self._add_weapon)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        weapons_layout.addLayout(btn_row)
        inner_layout.addWidget(weapons_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _add_weapon(self) -> None:
        row = self._weapons_table.rowCount()
        self._weapons_table.insertRow(row)
        self._weapons_table.setItem(row, 0, QTableWidgetItem("New Weapon"))
