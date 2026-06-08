"""Grafts tab for HeroForge-Anew.

Reference: Fiend Folio, Libris Mortis, Arms & Equipment Guide.  Grafts are
loaded from the seeded ``grafts`` catalogue (each carrying a body slot) and
applied grafts are persisted to :attr:`Character.grafts`.
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
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class GraftsTab(QWidget):
    """Graft selection and management backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Map of graft name -> default body slot from the catalogue.
        self._slots: dict[str, str] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(
            QLabel(
                "<b>Grafts</b> are body modifications that grant special abilities. "
                "Each graft occupies a body slot."
            )
        )

        taken_box = QGroupBox("Applied Grafts")
        taken_layout = QVBoxLayout(taken_box)
        self._graft_list = QListWidget()
        taken_layout.addWidget(self._graft_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Graft…")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add)
        self._rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        layout.addWidget(taken_box)
        layout.addStretch()

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for i in range(self._graft_list.count()):
            item = self._graft_list.item(i)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            result.append(
                {
                    "graft_name": data.get("graft_name", item.text()),
                    "body_slot": data.get("body_slot", ""),
                    "notes": data.get("notes", ""),
                }
            )
        return result

    def _occupied_slots(self) -> set[str]:
        return {e["body_slot"] for e in self._entries() if e["body_slot"]}

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.grafts = self._entries()

    def _make_item(self, name: str, slot: str, notes: str = "") -> QListWidgetItem:
        label = f"{name} ({slot})" if slot else name
        item = QListWidgetItem(label)
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"graft_name": name, "body_slot": slot, "notes": notes},
        )
        return item

    def add_graft(self, name: str, slot: str = "") -> bool:
        """Add graft *name* occupying *slot*; rejects slot conflicts. Returns OK."""
        name = name.strip()
        if not name:
            return False
        if slot and slot in self._occupied_slots():
            return False
        self._graft_list.addItem(self._make_item(name, slot))
        self._sync_to_model()
        return True

    def _add(self) -> None:
        grafts = self._model.game_data().list_grafts() if self._model else []
        self._slots = {g.name: g.body_slot for g in grafts}
        options = [g.name for g in grafts]
        name = pick_from_catalog(self, "Add Graft", "Graft:", options)
        if not name:
            return
        slot = self._slots.get(name, "")
        if not self.add_graft(name, slot):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Add Graft",
                f"The {slot} body slot is already occupied.",
            )

    def _remove(self) -> None:
        for item in self._graft_list.selectedItems():
            self._graft_list.takeItem(self._graft_list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._graft_list.clear()
        if self._model is not None:
            for entry in self._model.character.grafts:
                self._graft_list.addItem(
                    self._make_item(
                        entry.get("graft_name", ""),
                        entry.get("body_slot", ""),
                        entry.get("notes", ""),
                    )
                )
