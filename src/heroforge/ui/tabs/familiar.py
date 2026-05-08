"""Familiar tab for HeroForge-Anew.

Reference: PHB p52 (Wizard class feature).
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QLabel, QLineEdit,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class FamiliarTab(QWidget):
    """Familiar statistics and bonuses granted to master."""

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

        id_box = QGroupBox("Familiar Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        self._kind_edit = QLineEdit()
        id_form.addRow("Name:", self._name_edit)
        id_form.addRow("Kind:", self._kind_edit)
        inner_layout.addWidget(id_box)

        stats_box = QGroupBox("Familiar Statistics")
        stats_form = QFormLayout(stats_box)
        self._hp_spin = QSpinBox(); self._hp_spin.setRange(0, 999)
        self._int_spin = QSpinBox(); self._int_spin.setRange(1, 30)
        self._nat_armor_spin = QSpinBox(); self._nat_armor_spin.setRange(0, 20)
        stats_form.addRow("HP:", self._hp_spin)
        stats_form.addRow("Intelligence:", self._int_spin)
        stats_form.addRow("Natural Armor Bonus:", self._nat_armor_spin)
        inner_layout.addWidget(stats_box)

        bonuses_box = QGroupBox("Bonuses Granted to Master")
        bonuses_layout = QVBoxLayout(bonuses_box)
        bonuses_layout.addWidget(QLabel("(Based on familiar type – see PHB p52.)"))
        inner_layout.addWidget(bonuses_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
