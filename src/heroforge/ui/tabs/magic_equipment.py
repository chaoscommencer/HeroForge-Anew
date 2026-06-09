"""Magic Equipment tab for HeroForge-Anew.

Item slots and a wondrous-items list are persisted to
:attr:`Character.equipment`.  Each slot row and wondrous entry is stored as an
equipment dict tagged by ``slot``; the Armor tab owns the ``Body Armor`` and
``Shield`` slots, so this tab only manages the magic item slots below plus the
``Wondrous`` catch-all.  Item names can be chosen from the seeded
``magic_equipment`` catalogue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_SLOTS = [
    "Head",
    "Face/Eyes",
    "Throat/Neck",
    "Shoulders",
    "Body",
    "Torso",
    "Arms/Wrists",
    "Hands/Rings (x2)",
    "Waist",
    "Feet",
    "Off-hand",
]
_WONDROUS = "Wondrous"
# Slots owned by this tab (everything except the Armor tab's slots).
_OWNED_SLOTS = set(_SLOTS) | {_WONDROUS}


class MagicEquipmentTab(QWidget):
    """Magic item slots and inventory backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._loading = False
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._sync_from_model()

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
        header = self._slots_table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        vheader = self._slots_table.verticalHeader()
        assert vheader is not None
        vheader.setVisible(False)
        for row, slot in enumerate(_SLOTS):
            slot_item = QTableWidgetItem(slot)
            slot_item.setFlags(slot_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._slots_table.setItem(row, 0, slot_item)
            self._slots_table.setItem(row, 1, QTableWidgetItem(""))
            self._slots_table.setItem(row, 2, QTableWidgetItem(""))
        self._slots_table.itemChanged.connect(self._on_slot_changed)
        slots_layout.addWidget(self._slots_table)
        btn_row = QHBoxLayout()
        assign_btn = QPushButton("Assign Item to Slot…")
        assign_btn.clicked.connect(self._assign_slot)
        btn_row.addWidget(assign_btn)
        btn_row.addStretch()
        slots_layout.addLayout(btn_row)
        inner_layout.addWidget(slots_box)

        wbl_box = QGroupBox("Wondrous Items / Extra Equipment")
        wbl_layout = QVBoxLayout(wbl_box)
        self._extra_list = QListWidget()
        wbl_layout.addWidget(self._extra_list)
        erow = QHBoxLayout()
        add_btn = QPushButton("Add Item…")
        rm = QPushButton("Remove")
        add_btn.clicked.connect(self._add_extra)
        rm.clicked.connect(self._remove_extra)
        erow.addWidget(add_btn)
        erow.addWidget(rm)
        erow.addStretch()
        wbl_layout.addLayout(erow)
        inner_layout.addWidget(wbl_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for row in range(len(_SLOTS)):
            item = self._slots_table.item(row, 1)
            notes = self._slots_table.item(row, 2)
            name = item.text().strip() if item else ""
            if name:
                result.append(
                    {
                        "item_name": name,
                        "quantity": 1,
                        "weight": 0,
                        "equipped": 1,
                        "slot": _SLOTS[row],
                        "notes": notes.text() if notes else "",
                    }
                )
        for i in range(self._extra_list.count()):
            li = self._extra_list.item(i)
            if li is None:
                continue
            result.append(
                {
                    "item_name": li.text(),
                    "quantity": 1,
                    "weight": 0,
                    "equipped": 0,
                    "slot": _WONDROUS,
                    "notes": "",
                }
            )
        return result

    def _sync_to_model(self) -> None:
        if self._model is None:
            return
        others = [
            e
            for e in self._model.character.equipment
            if e.get("slot") not in _OWNED_SLOTS
        ]
        self._model.character.equipment = others + self._entries()

    def _on_slot_changed(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            self._sync_to_model()

    def _merged_item_catalog(self, slot: str | None = None) -> list[str]:
        """Return merged game + character-custom magic item names for *slot*."""
        game_items = self._model.game_data().list_magic_equipment() if self._model else []
        all_names = [m.name for m in game_items]
        if slot:
            slot_names = [m.name for m in game_items if not m.slot or m.slot == slot]
            # Fall back to all game items when nothing matches the requested slot.
            filtered = slot_names if slot_names else all_names
        else:
            filtered = all_names
        names: list[str] = list(filtered)
        if self._model:
            custom_names = {e.get("name", "") for e in self._model.character.custom_items}
            names += [n for n in sorted(custom_names) if n and n not in names]
        return names

    def _assign_slot(self) -> None:
        row = self._slots_table.currentRow()
        if row < 0:
            row = 0
        slot = _SLOTS[row]
        options = self._merged_item_catalog(slot)
        name = pick_from_catalog(self, "Assign Item", f"Item for {slot}:", options)
        if name:
            if self._model and name not in {m.name for m in self._model.game_data().list_magic_equipment()}:
                self._register_custom_item(name, slot)
            self._slots_table.setItem(row, 1, QTableWidgetItem(name))

    def add_extra(self, name: str) -> bool:
        """Add a wondrous/extra item named *name*. Returns acceptance."""
        name = name.strip()
        if not name:
            return False
        self._extra_list.addItem(QListWidgetItem(name))
        self._sync_to_model()
        return True

    def _add_extra(self) -> None:
        options = self._merged_item_catalog()
        name = pick_from_catalog(self, "Add Item", "Item:", options)
        if name:
            if self._model and name not in {m.name for m in self._model.game_data().list_magic_equipment()}:
                self._register_custom_item(name, "")
            self.add_extra(name)

    def _register_custom_item(self, name: str, slot: str) -> None:
        """Add *name* to :attr:`Character.custom_items` if not already present."""
        if self._model is None:
            return
        existing = {e.get("name") for e in self._model.character.custom_items}
        if name not in existing:
            self._model.character.custom_items = list(
                self._model.character.custom_items
            ) + [{"name": name, "slot": slot, "description": "", "weight": 0.0}]

    def _remove_extra(self) -> None:
        for item in self._extra_list.selectedItems():
            self._extra_list.takeItem(self._extra_list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        for row in range(len(_SLOTS)):
            self._slots_table.setItem(row, 1, QTableWidgetItem(""))
            self._slots_table.setItem(row, 2, QTableWidgetItem(""))
        self._extra_list.clear()
        if self._model is not None:
            by_slot = {s: i for i, s in enumerate(_SLOTS)}
            for entry in self._model.character.equipment:
                slot = entry.get("slot", "")
                if slot in by_slot:
                    row = by_slot[slot]
                    self._slots_table.setItem(
                        row, 1, QTableWidgetItem(entry.get("item_name", ""))
                    )
                    self._slots_table.setItem(
                        row, 2, QTableWidgetItem(entry.get("notes", ""))
                    )
                elif slot == _WONDROUS:
                    self._extra_list.addItem(
                        QListWidgetItem(entry.get("item_name", ""))
                    )
        self._loading = False
