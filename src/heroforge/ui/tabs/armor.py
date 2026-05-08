"""Armor tab for HeroForge-Anew."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QLabel, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class ArmorTab(QWidget):
    """Armor and shield selection with AC calculation."""

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

        for section in ("Body Armor", "Shield"):
            box = QGroupBox(section)
            form = QFormLayout(box)
            name_lbl = QLabel("(none)")
            ac_spin = QSpinBox()
            ac_spin.setRange(0, 20)
            acp_spin = QSpinBox()
            acp_spin.setRange(-20, 0)
            asf_spin = QSpinBox()
            asf_spin.setRange(0, 100)
            asf_spin.setSuffix("%")
            max_dex = QSpinBox()
            max_dex.setRange(0, 10)
            max_dex.setValue(10)
            form.addRow("Equipped:", name_lbl)
            form.addRow("AC Bonus:", ac_spin)
            form.addRow("Check Penalty:", acp_spin)
            form.addRow("Arcane Spell Failure:", asf_spin)
            form.addRow("Max Dex Bonus:", max_dex)
            inner_layout.addWidget(box)

        # Summary
        summary_box = QGroupBox("AC Summary")
        summary_form = QFormLayout(summary_box)
        self._total_ac_lbl = QLabel("10")
        self._touch_ac_lbl = QLabel("10")
        self._ff_ac_lbl = QLabel("10")
        summary_form.addRow("Total AC:", self._total_ac_lbl)
        summary_form.addRow("Touch AC:", self._touch_ac_lbl)
        summary_form.addRow("Flat-Footed AC:", self._ff_ac_lbl)
        inner_layout.addWidget(summary_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
