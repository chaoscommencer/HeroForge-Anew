"""Soulmelds tab for HeroForge-Anew.

Reference: Magic of Incarnum.
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


class SoulmeldsTab(QWidget):
    """Soulmeld shaping and essentia management."""

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

        # Essentia pool
        pool_box = QGroupBox("Essentia Pool")
        pool_form = QFormLayout(pool_box)
        self._total_spin = QSpinBox()
        self._total_spin.setRange(0, 30)
        self._invested_lbl = QLabel("0")
        self._remaining_lbl = QLabel("0")
        pool_form.addRow("Total Essentia:", self._total_spin)
        pool_form.addRow("Invested:", self._invested_lbl)
        pool_form.addRow("Remaining:", self._remaining_lbl)
        inner_layout.addWidget(pool_box)

        # Shaped soulmelds
        melds_box = QGroupBox("Shaped Soulmelds")
        melds_layout = QVBoxLayout(melds_box)
        self._melds_list = QListWidget()
        melds_layout.addWidget(self._melds_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Shape Soulmeld…"))
        rm = QPushButton("Remove")
        rm.clicked.connect(
            lambda: [
                self._melds_list.takeItem(self._melds_list.row(i))
                for i in self._melds_list.selectedItems()
            ]
        )
        btn_row.addWidget(rm)
        btn_row.addStretch()
        melds_layout.addLayout(btn_row)
        inner_layout.addWidget(melds_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
