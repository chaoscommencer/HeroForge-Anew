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

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)

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
        spin.valueChanged.connect(lambda _: self._sync_classes())
        self._taken_table.setCellWidget(row, 1, spin)
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda _, b=rm_btn: self._remove_prestige_row(b))
        self._taken_table.setCellWidget(row, 2, rm_btn)
        self._sync_classes()

    def _remove_prestige_row(self, button: QPushButton) -> None:
        for row in range(self._taken_table.rowCount()):
            if self._taken_table.cellWidget(row, 2) is button:
                self._taken_table.removeRow(row)
                self._sync_classes()
                return

    def _sync_classes(self) -> None:
        """Write taken class levels into the character and announce the change.

        Broadcasts :attr:`CharacterModel.class_levels_changed` (§8.4) so derived
        displays (BAB, saves, attacks, character sheet) recalculate in real time.
        """
        if self._model is None:
            return
        classes: list[tuple[str, int]] = []
        for row in range(self._taken_table.rowCount()):
            name_item = self._taken_table.item(row, 0)
            level_widget = self._taken_table.cellWidget(row, 1)
            if name_item is None or not isinstance(level_widget, QSpinBox):
                continue
            classes.append((name_item.text(), int(level_widget.value())))
        self._model.character.classes = classes
        self._model.class_levels_changed.emit()

    def _reset(self) -> None:
        self._taken_table.setRowCount(0)
        self._sync_classes()
