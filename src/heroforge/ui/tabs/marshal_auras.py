"""Marshal Auras tab for HeroForge-Anew (Excel tab 8e).

Reference: *Miniatures Handbook* p11–12.  The selectable minor and major auras
are loaded from the seeded ``marshal_auras`` catalogue via the data-access layer
(:meth:`heroforge.db.data_access.GameDataRepository.list_marshal_auras`).  The
character's *active* auras persist to :attr:`Character.marshal_auras` (each entry
``{"aura_name", "aura_type", "active"}``) and their bonuses flow into the
derived-stats pipeline (see
:meth:`heroforge.ui.main_window.CharacterModel.derived_stats`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.marshal import MAJOR, MINOR, get_aura

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class MarshalAurasTab(QWidget):
    """Select and activate marshal auras; active auras feed derived stats."""

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
                "<b>Marshal Auras</b> – check an aura to project it. A minor "
                "aura grants its bonus equal to your Charisma modifier; a major "
                "aura grants half your marshal level (minimum +1)."
            )
        )

        sub_tabs = QTabWidget()
        self._minor_list = self._make_list_page(sub_tabs, MINOR, "Minor Auras")
        self._major_list = self._make_list_page(sub_tabs, MAJOR, "Major Auras")
        layout.addWidget(sub_tabs)

    def _make_list_page(
        self, sub_tabs: QTabWidget, aura_type: str, title: str
    ) -> QListWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        list_widget = QListWidget()
        list_widget.itemChanged.connect(self._on_item_changed)
        box_layout.addWidget(list_widget)
        page_layout.addWidget(box)
        sub_tabs.addTab(page, title)
        return list_widget

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _make_item(self, name: str, active: bool) -> QListWidgetItem:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if active else Qt.CheckState.Unchecked)
        aura = get_aura(name)
        if aura is not None and aura.description:
            item.setToolTip(aura.description)
        return item

    def _populate(self) -> None:
        """Fill both lists from the data-access catalogue (unchecked)."""
        for aura_type, lst in (
            (MINOR, self._minor_list),
            (MAJOR, self._major_list),
        ):
            lst.blockSignals(True)
            lst.clear()
            if self._model is not None:
                for aura in self._model.game_data().list_marshal_auras(
                    aura_type=aura_type
                ):
                    lst.addItem(self._make_item(aura.name, False))
            lst.blockSignals(False)

    def _active_entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for aura_type, lst in (
            (MINOR, self._minor_list),
            (MAJOR, self._major_list),
        ):
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                if item.checkState() == Qt.CheckState.Checked:
                    result.append(
                        {
                            "aura_name": item.text(),
                            "aura_type": aura_type,
                            "active": True,
                        }
                    )
        return result

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.marshal_auras = self._active_entries()
            self._model.marshal_auras_changed.emit()

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        """Rebuild both lists from the catalogue and re-check active auras."""
        self._populate()
        if self._model is None:
            return
        active = {
            entry.get("aura_name", "")
            for entry in self._model.character.marshal_auras
            if entry.get("active")
        }
        for lst in (self._minor_list, self._major_list):
            lst.blockSignals(True)
            for i in range(lst.count()):
                item = lst.item(i)
                if item is None:
                    continue
                if item.text() in active:
                    item.setCheckState(Qt.CheckState.Checked)
            lst.blockSignals(False)
