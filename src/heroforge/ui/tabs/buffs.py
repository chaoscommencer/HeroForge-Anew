"""Buffs tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class BuffsTab(QWidget):
    """Active buff tracking and management."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._next_id: int = 0
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(
            QLabel(
                "<b>Buffs</b> – track active spells, class abilities, "
                "and other bonuses. "
                "Only highest non-stackable bonus of each type applies."
            )
        )

        box = QGroupBox("Active Buffs")
        box_layout = QVBoxLayout(box)
        self._buff_list = QListWidget()
        box_layout.addWidget(self._buff_list)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Buff…")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add_buff)
        self._rm_btn.clicked.connect(self._remove_buff)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        box_layout.addLayout(btn_row)
        layout.addWidget(box)
        layout.addStretch()

    def add_buff(self, name: str) -> None:
        """Add an active buff named *name* and announce it (§8.4).

        Each buff instance is assigned a unique integer ID that is stored in
        the :class:`~PyQt6.QtWidgets.QListWidgetItem` via
        ``Qt.ItemDataRole.UserRole``.  The ID is forwarded through
        :attr:`CharacterModel.buff_toggled` so the model can later remove
        exactly this instance regardless of duplicate names.
        """
        name = name.strip()
        if not name:
            return
        buff_id = self._next_id
        self._next_id += 1
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, buff_id)
        self._buff_list.addItem(item)
        if self._model:
            self._model.buff_toggled.emit(buff_id, name, True)

    def _add_buff(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Buff", "Buff name:")
        if ok:
            self.add_buff(name)

    def _remove_buff(self) -> None:
        for item in self._buff_list.selectedItems():
            buff_id: int = item.data(Qt.ItemDataRole.UserRole)
            name = item.text()
            self._buff_list.takeItem(self._buff_list.row(item))
            if self._model:
                self._model.buff_toggled.emit(buff_id, name, False)

    def _reset(self) -> None:
        self._buff_list.clear()
        self._next_id = 0
