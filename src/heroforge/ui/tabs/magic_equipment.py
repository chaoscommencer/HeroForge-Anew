"""Magic Equipment tab for HeroForge-Anew."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_SLOTS = [
    "Head", "Face/Eyes", "Throat/Neck", "Shoulders", "Body", "Torso",
    "Arms/Wrists", "Hands/Rings (x2)", "Waist", "Feet", "Off-hand",
]


class MagicEquipmentTab(QWidget):
    """Magic item slots and inventory."""

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

        slots_box = QGroupBox("Item Slots")
        slots_layout = QVBoxLayout(slots_box)
        headers = ["Slot", "Item", "Notes"]
        self._slots_table = QTableWidget(len(_SLOTS), len(headers))
        self._slots_table.setHorizontalHeaderLabels(headers)
        self._slots_table.horizontalHeader().setStretchLastSection(True)
        self._slots_table.verticalHeader().setVisible(False)
        for row, slot in enumerate(_SLOTS):
            self._slots_table.setItem(row, 0, QTableWidgetItem(slot))
        slots_layout.addWidget(self._slots_table)
        inner_layout.addWidget(slots_box)

        wbl_box = QGroupBox("Wondrous Items / Extra Equipment")
        wbl_layout = QVBoxLayout(wbl_box)
        self._extra_list = QListWidget()
        wbl_layout.addWidget(self._extra_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Add Item…"))
        rm = QPushButton("Remove")
        rm.clicked.connect(lambda: [self._extra_list.takeItem(self._extra_list.row(i))
                                    for i in self._extra_list.selectedItems()])
        btn_row.addWidget(rm)
        btn_row.addStretch()
        wbl_layout.addLayout(btn_row)
        inner_layout.addWidget(wbl_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
