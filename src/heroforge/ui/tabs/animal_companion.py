"""Animal Companion tab for HeroForge-Anew.

Reference: PHB p35 (Druid class feature), p52 (Ranger).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class AnimalCompanionTab(QWidget):
    """Animal companion statistics and management."""

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

        id_box = QGroupBox("Animal Companion Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        self._species_edit = QLineEdit()
        id_form.addRow("Name:", self._name_edit)
        id_form.addRow("Species:", self._species_edit)
        inner_layout.addWidget(id_box)

        stats_box = QGroupBox("Companion Statistics")
        stats_form = QFormLayout(stats_box)
        for ability in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(10)
            stats_form.addRow(f"{ability}:", spin)
        self._hp_spin = QSpinBox()
        self._hp_spin.setRange(0, 9999)
        self._hd_edit = QLineEdit()
        stats_form.addRow("HP:", self._hp_spin)
        stats_form.addRow("Hit Dice:", self._hd_edit)
        inner_layout.addWidget(stats_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
