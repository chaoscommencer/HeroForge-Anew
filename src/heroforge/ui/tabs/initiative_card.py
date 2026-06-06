"""Initiative Card tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class InitiativeCardTab(QWidget):
    """Combat initiative tracker for all participants."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(
            QLabel("<b>Initiative Tracker</b> – Add all combatants and sort.")
        )

        headers = ["Name", "Initiative", "HP", "AC", "Status", "Remove"]
        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Combatant")
        sort_btn = QPushButton("Sort by Initiative")
        clear_btn = QPushButton("Clear All")
        add_btn.clicked.connect(self._add_row)
        sort_btn.clicked.connect(self._sort)
        clear_btn.clicked.connect(self._table.clearContents)
        clear_btn.clicked.connect(lambda: self._table.setRowCount(0))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(sort_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem("Combatant"))
        init_spin = QSpinBox()
        init_spin.setRange(-10, 50)
        self._table.setCellWidget(row, 1, init_spin)
        hp_spin = QSpinBox()
        hp_spin.setRange(0, 9999)
        self._table.setCellWidget(row, 2, hp_spin)
        ac_spin = QSpinBox()
        ac_spin.setRange(0, 60)
        self._table.setCellWidget(row, 3, ac_spin)
        self._table.setItem(row, 4, QTableWidgetItem("Active"))
        rm_btn = QPushButton("×")
        rm_btn.clicked.connect(lambda _, b=rm_btn: self._remove_row(b))
        self._table.setCellWidget(row, 5, rm_btn)

    def _remove_row(self, button: QPushButton) -> None:
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 5) is button:
                self._table.removeRow(row)
                return

    def _sort(self) -> None:
        rows = self._table.rowCount()
        data = []
        for r in range(rows):
            name_item = self._table.item(r, 0)
            init_widget = self._table.cellWidget(r, 1)
            name = name_item.text() if name_item else ""
            init = init_widget.value() if init_widget else 0
            data.append((init, name, r))
        data.sort(key=lambda x: (-x[0], x[1]))
        # Rebuild order (simplified: just re-label for now)
        for new_pos, (init_val, name, _) in enumerate(data):
            item = self._table.item(new_pos, 0)
            if item:
                item.setText(name)
