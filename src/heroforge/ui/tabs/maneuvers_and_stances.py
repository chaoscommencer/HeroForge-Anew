"""Maneuvers & Stances tab for HeroForge-Anew.

Reference: Tome of Battle.  Maneuvers and stances are loaded from the seeded
``maneuvers`` catalogue (which marks stances via the ``type`` column) and the
character's selections persist to :attr:`Character.maneuvers` (each entry
``{"maneuver_name", "readied"}``).  For maneuvers ``readied`` marks a readied
maneuver; for stances it marks the active stance.
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class ManeuversAndStancesTab(QWidget):
    """Tome of Battle maneuver and stance management backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Catalogue lookup: name -> is_stance.
        self._stance_names: set[str] = set()
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        sub_tabs = QTabWidget()

        # Maneuvers sub-tab
        man_widget = QWidget()
        man_layout = QVBoxLayout(man_widget)
        man_layout.addWidget(
            QLabel("Check a maneuver to mark it readied (Tome of Battle).")
        )
        known_box = QGroupBox("Known Maneuvers")
        known_layout = QVBoxLayout(known_box)
        self._known_list = QListWidget()
        self._known_list.itemChanged.connect(self._on_item_changed)
        known_layout.addWidget(self._known_list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Maneuver…")
        rm_btn = QPushButton("Remove Selected")
        add_btn.clicked.connect(lambda: self._add(stance=False))
        rm_btn.clicked.connect(lambda: self._remove(self._known_list))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        known_layout.addLayout(btn_row)
        man_layout.addWidget(known_box)
        sub_tabs.addTab(man_widget, "Maneuvers")

        # Stances sub-tab
        stance_widget = QWidget()
        stance_layout = QVBoxLayout(stance_widget)
        stance_layout.addWidget(QLabel("Check a stance to mark it active."))
        stance_box = QGroupBox("Known Stances")
        stance_box_layout = QVBoxLayout(stance_box)
        self._stance_list = QListWidget()
        self._stance_list.itemChanged.connect(self._on_item_changed)
        stance_box_layout.addWidget(self._stance_list)
        srow = QHBoxLayout()
        sadd_btn = QPushButton("Add Stance…")
        srm_btn = QPushButton("Remove Selected")
        sadd_btn.clicked.connect(lambda: self._add(stance=True))
        srm_btn.clicked.connect(lambda: self._remove(self._stance_list))
        srow.addWidget(sadd_btn)
        srow.addWidget(srm_btn)
        srow.addStretch()
        stance_box_layout.addLayout(srow)
        stance_layout.addWidget(stance_box)
        sub_tabs.addTab(stance_widget, "Stances")

        layout.addWidget(sub_tabs)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _make_item(self, name: str, readied: bool) -> QListWidgetItem:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if readied else Qt.CheckState.Unchecked
        )
        return item

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for lst in (self._known_list, self._stance_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                result.append(
                    {
                        "maneuver_name": item.text(),
                        "readied": item.checkState() == Qt.CheckState.Checked,
                    }
                )
        return result

    def _all_names(self) -> set[str]:
        return {e["maneuver_name"] for e in self._entries()}

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.maneuvers = self._entries()

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._sync_to_model()

    def add_maneuver(self, name: str, *, stance: bool = False) -> bool:
        """Add a known maneuver or stance; rejects duplicates. Returns OK."""
        name = name.strip()
        if not name or name in self._all_names():
            return False
        lst = self._stance_list if stance else self._known_list
        lst.addItem(self._make_item(name, False))
        self._sync_to_model()
        return True

    def _add(self, *, stance: bool) -> None:
        maneuvers = self._model.game_data().list_maneuvers() if self._model else []
        self._stance_names = {m.name for m in maneuvers if m.is_stance}
        options = [m.name for m in maneuvers if m.is_stance == stance]
        options = [o for o in options if o not in self._all_names()]
        title = "Add Stance" if stance else "Add Maneuver"
        name = pick_from_catalog(self, title, "Name:", options)
        if name:
            self.add_maneuver(name, stance=stance)

    def _remove(self, lst: QListWidget) -> None:
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._known_list.blockSignals(True)
        self._stance_list.blockSignals(True)
        self._known_list.clear()
        self._stance_list.clear()
        if self._model is not None:
            maneuvers = self._model.game_data().list_maneuvers()
            self._stance_names = {m.name for m in maneuvers if m.is_stance}
            for entry in self._model.character.maneuvers:
                name = entry.get("maneuver_name", "")
                if not name:
                    continue
                readied = bool(entry.get("readied", False))
                if name in self._stance_names:
                    self._stance_list.addItem(self._make_item(name, readied))
                else:
                    self._known_list.addItem(self._make_item(name, readied))
        self._known_list.blockSignals(False)
        self._stance_list.blockSignals(False)
