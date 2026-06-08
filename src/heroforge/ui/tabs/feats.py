"""Feats tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.feats import check_prerequisites

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class FeatsTab(QWidget):
    """Feat selection and management."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._descriptions: dict[str, str] = {}
        self._prerequisites: dict[str, list[str]] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)
            model.derived_stats_changed.connect(self._apply_prereq_status)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        avail_box = QGroupBox("Available Feats")
        avail_layout = QVBoxLayout(avail_box)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search feats…")
        self._search_edit.textChanged.connect(self._filter)
        avail_layout.addWidget(self._search_edit)
        self._avail_list = QListWidget()
        self._avail_list.currentTextChanged.connect(self._show_description)
        avail_layout.addWidget(self._avail_list)
        inner_layout.addWidget(avail_box)

        taken_box = QGroupBox("Selected Feats")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_list = QListWidget()
        taken_layout.addWidget(self._taken_list)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Feat")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add_feat)
        self._rm_btn.clicked.connect(self._remove_feat)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        info_box = QGroupBox("Feat Description")
        info_layout = QVBoxLayout(info_box)
        self._desc_text = QTextEdit()
        self._desc_text.setReadOnly(True)
        self._desc_text.setMaximumHeight(120)
        info_layout.addWidget(self._desc_text)
        inner_layout.addWidget(info_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._load_feats()

    def _load_feats(self) -> None:
        """Populate the available-feats list from the seeded database."""
        self._avail_list.clear()
        self._desc_text.clear()
        self._descriptions = {}
        self._prerequisites = {}
        if self._model is None:
            return
        self._prerequisites = self._model.game_data().feat_prerequisites()
        for feat in self._model.game_data().list_feats():
            self._avail_list.addItem(feat.name)
            self._descriptions[feat.name] = feat.description or feat.benefit
        self._apply_prereq_status()

    def _apply_prereq_status(self) -> None:
        """Enable/disable available feats by prerequisite satisfaction (§8.6).

        Feats whose prerequisites are not met are shown disabled with an
        explanatory tooltip, recomputed in real time as ability scores, BAB,
        skills, and feats change.  Validation uses
        :func:`heroforge.logic.feats.check_prerequisites`.
        """
        if self._model is None:
            return
        stats = self._model.derived_stats()
        char = self._model.character
        for i in range(self._avail_list.count()):
            item = self._avail_list.item(i)
            if item is None:
                continue
            prereqs = self._prerequisites.get(item.text(), [])
            met = check_prerequisites(
                prereqs,
                stats.base_attack_bonus,
                char.ability_scores,
                char.skills,
                char.feats,
                char.total_level,
            )
            flags = item.flags()
            if met or not prereqs:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("")
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("Prerequisites not met: " + ", ".join(prereqs))

    def _show_description(self, name: str) -> None:
        self._desc_text.setPlainText(self._descriptions.get(name, ""))

    def _filter(self, text: str) -> None:
        for i in range(self._avail_list.count()):
            item = self._avail_list.item(i)
            if item:
                item.setHidden(text.lower() not in item.text().lower())

    def _sync_feats_to_character(self) -> None:
        """Write the current taken-feats list back into the character model."""
        if self._model is None:
            return
        self._model.character.feats = [
            item.text()
            for i in range(self._taken_list.count())
            if (item := self._taken_list.item(i)) is not None
        ]
        self._apply_prereq_status()

    def _add_feat(self) -> None:
        for item in self._avail_list.selectedItems():
            self._taken_list.addItem(item.text())
        self._sync_feats_to_character()

    def _remove_feat(self) -> None:
        for item in self._taken_list.selectedItems():
            self._taken_list.takeItem(self._taken_list.row(item))
        self._sync_feats_to_character()

    def _reset(self) -> None:
        self._taken_list.clear()
