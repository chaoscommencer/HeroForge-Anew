"""Skill Tricks tab for HeroForge-Anew.

Reference: Complete Scoundrel p84.  Available tricks are loaded from the seeded
``skill_tricks`` catalogue (with their skill-point cost and prerequisites) and
learned tricks are persisted to :attr:`Character.skill_tricks`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class SkillTricksTab(QWidget):
    """Skill trick selection and tracking backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Map of trick name -> skill-point cost (defaults to 2 SP, CSco p84).
        self._costs: dict[str, int] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._load_catalog()
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        avail_box = QGroupBox("Available Skill Tricks (2 SP each)")
        avail_layout = QVBoxLayout(avail_box)
        self._avail_list = QListWidget()
        avail_layout.addWidget(self._avail_list)
        inner_layout.addWidget(avail_box)

        taken_box = QGroupBox("Learned Skill Tricks")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_list = QListWidget()
        taken_layout.addWidget(self._taken_list)
        self._cost_lbl = QLabel("Skill points spent on tricks: 0")
        taken_layout.addWidget(self._cost_lbl)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Learn Selected")
        self._rm_btn = QPushButton("Forget Selected")
        self._add_btn.clicked.connect(self._learn)
        self._rm_btn.clicked.connect(self._forget)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _load_catalog(self) -> None:
        """Populate the available-tricks list from the seeded database."""
        self._avail_list.clear()
        self._costs = {}
        if self._model is None:
            return
        for trick in self._model.game_data().list_skill_tricks():
            self._costs[trick.name] = trick.cost
            item = QListWidgetItem(trick.name)
            if trick.prerequisite:
                item.setToolTip(f"Prerequisite: {trick.prerequisite}")
            self._avail_list.addItem(item)

    def _learned(self) -> list[str]:
        return [
            item.text()
            for i in range(self._taken_list.count())
            if (item := self._taken_list.item(i)) is not None
        ]

    def _refresh_cost(self) -> None:
        total = sum(self._costs.get(name, 2) for name in self._learned())
        self._cost_lbl.setText(f"Skill points spent on tricks: {total}")

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.skill_tricks = self._learned()
        self._refresh_cost()

    def learn(self, name: str) -> bool:
        """Learn skill trick *name*; rejects duplicates. Returns acceptance."""
        name = name.strip()
        if not name or name in self._learned():
            return False
        self._taken_list.addItem(name)
        self._sync_to_model()
        return True

    def _learn(self) -> None:
        selected = self._avail_list.selectedItems()
        if selected:
            for item in selected:
                self.learn(item.text())
        else:
            options = [
                self._avail_list.item(i).text()
                for i in range(self._avail_list.count())
            ]
            name = pick_from_catalog(self, "Add Skill Trick", "Skill trick:", options)
            if name:
                self.learn(name)

    def _forget(self) -> None:
        for item in self._taken_list.selectedItems():
            self._taken_list.takeItem(self._taken_list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._taken_list.clear()
        if self._model is not None:
            for name in self._model.character.skill_tricks:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self._taken_list.addItem(item)
        self._refresh_cost()
