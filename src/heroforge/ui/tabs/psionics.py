"""Psionics tab for HeroForge-Anew.

Reference: Expanded Psionics Handbook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class PsionicsTab(QWidget):
    """Psionic power point tracking and power management."""

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

        pp_box = QGroupBox("Power Points")
        pp_form = QFormLayout(pp_box)
        self._total_pp = QSpinBox()
        self._total_pp.setRange(0, 9999)
        self._spent_pp = QSpinBox()
        self._spent_pp.setRange(0, 9999)
        self._remaining_lbl = QLabel("0")
        pp_form.addRow("Total PP/Day:", self._total_pp)
        pp_form.addRow("Spent:", self._spent_pp)
        pp_form.addRow("Remaining:", self._remaining_lbl)
        self._total_pp.valueChanged.connect(self._update_remaining)
        self._spent_pp.valueChanged.connect(self._update_remaining)
        inner_layout.addWidget(pp_box)

        powers_box = QGroupBox("Known Powers")
        powers_layout = QVBoxLayout(powers_box)
        self._powers_list = QListWidget()
        powers_layout.addWidget(self._powers_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Add Power…"))
        rm = QPushButton("Remove")
        rm.clicked.connect(
            lambda: [
                self._powers_list.takeItem(self._powers_list.row(i))
                for i in self._powers_list.selectedItems()
            ]
        )
        btn_row.addWidget(rm)
        btn_row.addStretch()
        powers_layout.addLayout(btn_row)
        inner_layout.addWidget(powers_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _update_remaining(self) -> None:
        remaining = max(0, self._total_pp.value() - self._spent_pp.value())
        self._remaining_lbl.setText(str(remaining))
