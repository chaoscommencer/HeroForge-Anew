"""Binder Vestiges tab for HeroForge-Anew (Excel tab 8d).

Reference: *Tome of Magic* (Pact Magic).  A binder forms pacts with vestiges and
gains their granted abilities while bound.  The bindable vestige catalogue is
loaded from the seeded ``vestiges`` table via
:meth:`heroforge.db.data_access.GameDataRepository.list_vestiges`, and the
character's bindings persist to :attr:`Character.vestiges` (each entry
``{"vestige_name", "level", "bound"}`` where ``level`` is the vestige's own
level and ``bound`` marks an active – as opposed to suppressed – pact).

Binder level limits (the highest bindable vestige level and the number of
vestiges that can be held at once) are enforced via
:mod:`heroforge.logic.vestiges`, and a vestige's always-on granted-ability
bonuses feed the derived-stats pipeline through the same module.
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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic import vestiges
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Stored on each list item so removal/effect application can resolve a vestige's
# level without re-querying the catalogue.
_LEVEL_ROLE = Qt.ItemDataRole.UserRole


class BinderVestigesTab(QWidget):
    """Bind and suppress Tome of Magic vestiges, backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
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
                "<b>Binder Vestiges</b> (Tome of Magic) – bind vestiges to gain "
                "their granted abilities. Uncheck a vestige to suppress its pact."
            )
        )
        self._limit_label = QLabel()
        layout.addWidget(self._limit_label)

        box = QGroupBox("Bound Vestiges")
        box_layout = QVBoxLayout(box)
        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_item_changed)
        box_layout.addWidget(self._list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Bind Vestige…")
        rm_btn = QPushButton("Remove Selected")
        add_btn.clicked.connect(self._add)
        rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        box_layout.addLayout(btn_row)
        layout.addWidget(box)
        layout.addStretch()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _binder_level(self) -> int:
        if self._model is None:
            return 0
        return vestiges.binder_level(self._model.character)

    def _make_item(self, name: str, level: int | None, bound: bool) -> QListWidgetItem:
        label = name if level is None else f"{name}  (level {level})"
        item = QListWidgetItem(label)
        item.setData(_LEVEL_ROLE, level)
        item.setData(Qt.ItemDataRole.UserRole + 1, name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if bound else Qt.CheckState.Unchecked)
        return item

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            result.append(
                {
                    "vestige_name": item.data(Qt.ItemDataRole.UserRole + 1),
                    "level": item.data(_LEVEL_ROLE),
                    "bound": item.checkState() == Qt.CheckState.Checked,
                }
            )
        return result

    def _names(self) -> set[str]:
        return {e["vestige_name"] for e in self._entries()}

    def _bound_count(self) -> int:
        return sum(1 for e in self._entries() if e["bound"])

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.vestiges = self._entries()
            self._model.derived_stats_changed.emit()
        self._update_limit_label()

    def _update_limit_label(self) -> None:
        level = self._binder_level()
        if level < 1:
            self._limit_label.setText(
                "No binder level (take Binder levels or the Bind Vestige feat to "
                "bind vestiges)."
            )
            return
        self._limit_label.setText(
            f"Binder level {level}: may bind vestiges up to level "
            f"{vestiges.max_vestige_level(level)}, "
            f"up to {vestiges.max_vestiges_bound(level)} at once "
            f"({self._bound_count()} currently bound)."
        )

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._sync_to_model()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def bind_vestige(self, name: str, level: int | None) -> bool:
        """Bind a vestige named *name*; rejects duplicates. Returns OK."""
        name = name.strip()
        if not name or name in self._names():
            return False
        self._list.addItem(self._make_item(name, level, True))
        self._sync_to_model()
        return True

    def _add(self) -> None:
        if self._model is None:
            return
        level = self._binder_level()
        if level < 1:
            QMessageBox.information(
                self,
                "Cannot Bind Vestige",
                "This character has no binder level. Take levels in the Binder "
                "class or the Bind Vestige feat first.",
            )
            return
        if self._bound_count() >= vestiges.max_vestiges_bound(level):
            QMessageBox.information(
                self,
                "Vestige Limit Reached",
                "You are already binding the maximum number of vestiges for your "
                "binder level. Suppress or remove one first.",
            )
            return
        catalogue = self._model.game_data().list_vestiges()
        levels = {v.name: v.vestige_level for v in catalogue}
        existing = self._names()
        options = [
            v.name
            for v in catalogue
            if v.name not in existing and vestiges.can_bind(v.vestige_level, level)
        ]
        name = pick_from_catalog(self, "Bind Vestige", "Vestige:", options)
        if name:
            self.bind_vestige(name, levels.get(name))

    def _remove(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._model is not None:
            catalogue = (
                {
                    v.name: v.vestige_level
                    for v in self._model.game_data().list_vestiges()
                }
                if self._model.game_data().available
                else {}
            )
            for entry in self._model.character.vestiges:
                name = str(entry.get("vestige_name", "")).strip()
                if not name:
                    continue
                level = entry.get("level")
                if level is None:
                    level = catalogue.get(name)
                bound = bool(entry.get("bound", True))
                self._list.addItem(self._make_item(name, level, bound))
        self._list.blockSignals(False)
        self._update_limit_label()
