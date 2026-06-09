"""Enhancements tab for HeroForge-Anew.

Magic weapon and armor enhancement selection.  Enhancements are loaded from the
seeded ``magic_enhancements`` catalogue (with their effective bonus value) and
persisted to :attr:`Character.enhancements` (each entry
``{"target", "bonus_type", "value", "notes"}`` where *target* is ``"Weapon"``
or ``"Armor"`` and *bonus_type* is the enhancement name).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
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


class EnhancementsTab(QWidget):
    """Magic weapon and armor enhancement configuration backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Catalogue lookup: name -> bonus_equivalent value.
        self._values: dict[str, int] = {}
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

        for target, label in (
            ("Weapon", "Weapon Enhancements"),
            ("Armor", "Armor Enhancements"),
        ):
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            lst = QListWidget()
            box_layout.addWidget(lst)
            btn_row = QHBoxLayout()
            add_btn = QPushButton("Add Enhancement…")
            rm_btn = QPushButton("Remove")
            add_btn.clicked.connect(lambda _, t=target: self._add(t))
            rm_btn.clicked.connect(lambda _, t=target: self._remove(t))
            btn_row.addWidget(add_btn)
            btn_row.addWidget(rm_btn)
            btn_row.addStretch()
            box_layout.addLayout(btn_row)
            inner_layout.addWidget(box)
            setattr(self, f"_{target.lower()}_list", lst)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _list(self, target: str) -> QListWidget:
        return getattr(self, f"_{target.lower()}_list")  # type: ignore[no-any-return]

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for target in ("Weapon", "Armor"):
            lst = self._list(target)
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                value = item.data(Qt.ItemDataRole.UserRole)
                result.append(
                    {
                        "target": target,
                        "bonus_type": item.text(),
                        "value": int(value or 0),
                        "notes": "",
                    }
                )
        return result

    def _names(self, target: str) -> list[str]:
        lst = self._list(target)
        return [
            item.text() for i in range(lst.count()) if (item := lst.item(i)) is not None
        ]

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.enhancements = self._entries()

    def add_enhancement(self, target: str, name: str, value: int = 0) -> bool:
        """Add enhancement *name* to *target*; rejects duplicates. Returns OK."""
        name = name.strip()
        if not name or name in self._names(target):
            return False
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, int(value))
        self._list(target).addItem(item)
        self._sync_to_model()
        return True

    def _add(self, target: str) -> None:
        if self._model is not None:
            enh = self._model.game_data().list_magic_enhancements()
            self._values = {e.name: e.bonus_equivalent for e in enh}
            options = [e.name for e in enh if e.name not in self._names(target)]
        else:
            options = []
        name = pick_from_catalog(self, "Add Enhancement", "Enhancement:", options)
        if name:
            self.add_enhancement(target, name, self._values.get(name, 0))

    def _remove(self, target: str) -> None:
        lst = self._list(target)
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._list("Weapon").clear()
        self._list("Armor").clear()
        if self._model is not None:
            for entry in self._model.character.enhancements:
                target = entry.get("target", "Weapon")
                if target not in ("Weapon", "Armor"):
                    continue
                item = QListWidgetItem(entry.get("bonus_type", ""))
                item.setData(Qt.ItemDataRole.UserRole, int(entry.get("value", 0) or 0))
                self._list(target).addItem(item)
