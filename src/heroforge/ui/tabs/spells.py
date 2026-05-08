"""Spells tab for HeroForge-Anew."""
from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class SpellsTab(QWidget):
    """Spell slot tracking and prepared/known spell management."""

    def __init__(self, model: "CharacterModel | None" = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Caster class selector
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Spellcasting Class:"))
        self._class_combo = QComboBox()
        self._class_combo.addItems(["Wizard", "Sorcerer", "Cleric", "Druid", "Bard", "Paladin", "Ranger"])
        top_row.addWidget(self._class_combo)
        top_row.addStretch()
        layout.addLayout(top_row)

        sub_tabs = QTabWidget()

        # Spells per day
        spd_widget = QWidget()
        spd_layout = QVBoxLayout(spd_widget)
        spd_box = QGroupBox("Spell Slots per Day")
        spd_box_layout = QVBoxLayout(spd_box)
        for lvl in range(10):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Level {lvl}:"))
            used = QSpinBox(); used.setRange(0, 20); used.setPrefix("Used: ")
            total = QSpinBox(); total.setRange(0, 20); total.setPrefix("Total: ")
            row.addWidget(used); row.addWidget(total); row.addStretch()
            spd_box_layout.addLayout(row)
        spd_layout.addWidget(spd_box)
        sub_tabs.addTab(spd_widget, "Spell Slots")

        # Prepared/known spells
        prep_widget = QWidget()
        prep_layout = QVBoxLayout(prep_widget)
        self._prepared_list = QListWidget()
        prep_layout.addWidget(QLabel("Prepared / Known Spells:"))
        prep_layout.addWidget(self._prepared_list)
        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Add Spell…"))
        rm = QPushButton("Remove")
        rm.clicked.connect(lambda: [self._prepared_list.takeItem(self._prepared_list.row(i))
                                    for i in self._prepared_list.selectedItems()])
        btn_row.addWidget(rm)
        btn_row.addStretch()
        prep_layout.addLayout(btn_row)
        sub_tabs.addTab(prep_widget, "Prepared/Known")

        layout.addWidget(sub_tabs)
