"""Marshal Auras tab for HeroForge-Anew (Excel tab 8e).

Reference: *Miniatures Handbook* p11–12.  The selectable minor and major auras
are loaded from the seeded ``marshal_auras`` catalogue via the data-access layer
(:meth:`heroforge.db.data_access.GameDataRepository.list_marshal_auras`).

Like the workbook's *Marshal Auras* sheet, each list records the auras the
character **knows**, capped by the marshal level (``TblMarshallAurasKnown``,
:func:`heroforge.logic.marshal.auras_known`).  A *Projecting* selector under
each list picks the one known aura of that type the marshal is projecting
(``Class Abilities!A1641``: one minor and, from 2nd level, one major aura at a
time).  Known auras persist to :attr:`Character.marshal_auras` (each entry
``{"aura_name", "aura_type", "active"}``, ``active`` marking the projected
aura), and the projected auras' bonuses flow into the derived stats (see
:func:`heroforge.logic.marshal.aura_bonus_specs`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.marshal import (
    MAJOR,
    MINOR,
    auras_known,
    get_aura,
    marshal_level,
    max_active_auras,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_NONE = "(none)"


class _AuraPage:
    """The widgets of one aura type's sub-tab: known list and projected aura."""

    def __init__(self, aura_type: str, title: str) -> None:
        self.aura_type = aura_type
        self.title = title
        self.widget = QWidget()
        self.box = QGroupBox(title)
        self.known = QListWidget()
        self.projecting = QComboBox()
        self.projecting.setObjectName(f"{aura_type.lower()}_projecting")

        box_layout = QVBoxLayout(self.box)
        box_layout.addWidget(self.known)
        form = QFormLayout()
        form.addRow("Projecting:", self.projecting)
        layout = QVBoxLayout(self.widget)
        layout.addWidget(self.box)
        layout.addLayout(form)

    def known_names(self) -> list[str]:
        """Names of the checked (known) auras, in list order."""
        names: list[str] = []
        for i in range(self.known.count()):
            item = self.known.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                names.append(item.text())
        return names

    def projected_name(self) -> str:
        """The projected aura's name, or ``""`` for none."""
        text = self.projecting.currentText()
        return "" if text in ("", _NONE) else text


class MarshalAurasTab(QWidget):
    """Pick known and projected marshal auras; projected ones feed stats."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.class_levels_changed.connect(self._refresh_limits)
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(
            QLabel(
                "<b>Marshal Auras</b> – check the auras you know, then pick the "
                "one minor and one major aura you are projecting. A minor aura "
                "grants a bonus equal to your Charisma modifier; a major aura, "
                "from 2nd level, grants +1, rising to +2 at 7th level, +3 at "
                "14th and +4 at 20th."
            )
        )

        sub_tabs = QTabWidget()
        self._minor = _AuraPage(MINOR, "Minor Auras")
        self._major = _AuraPage(MAJOR, "Major Auras")
        for page in (self._minor, self._major):
            page.known.itemChanged.connect(
                lambda item, p=page: self._on_known_changed(p, item)
            )
            page.projecting.currentIndexChanged.connect(
                lambda _index: self._sync_to_model()
            )
            sub_tabs.addTab(page.widget, page.title)
        layout.addWidget(sub_tabs)

        # Kept as attributes for callers that only need the lists.
        self._minor_list = self._minor.known
        self._major_list = self._major.known

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------

    def _marshal_level(self) -> int:
        return marshal_level(self._model.character) if self._model else 0

    def _limits(self, page: _AuraPage) -> tuple[int, int]:
        """Return ``(known cap, projected cap)`` for *page*'s aura type."""
        level = self._marshal_level()
        index = 0 if page.aura_type == MINOR else 1
        return auras_known(level)[index], max_active_auras(level)[index]

    def _refresh_limits(self) -> None:
        """Show the known-aura counts and lock selections at the cap."""
        for page in (self._minor, self._major):
            known_cap, active_cap = self._limits(page)
            count = len(page.known_names())
            page.box.setTitle(f"{page.title} known: {count} of {known_cap}")
            at_cap = count >= known_cap
            page.known.blockSignals(True)
            for i in range(page.known.count()):
                item = page.known.item(i)
                if item is None:
                    continue
                checked = item.checkState() == Qt.CheckState.Checked
                flags = item.flags()
                if at_cap and not checked:
                    flags &= ~Qt.ItemFlag.ItemIsEnabled
                else:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                item.setFlags(flags)
            page.known.blockSignals(False)
            page.projecting.setEnabled(active_cap > 0)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _make_item(self, name: str, known: bool) -> QListWidgetItem:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if known else Qt.CheckState.Unchecked)
        aura = get_aura(name)
        if aura is not None and aura.description:
            item.setToolTip(aura.description)
        return item

    def _populate(self) -> None:
        """Fill both lists from the data-access catalogue (unchecked)."""
        for page in (self._minor, self._major):
            page.known.blockSignals(True)
            page.known.clear()
            if self._model is not None:
                for aura in self._model.game_data().list_marshal_auras(
                    aura_type=page.aura_type
                ):
                    page.known.addItem(self._make_item(aura.name, False))
            page.known.blockSignals(False)

    def _refresh_projecting(self, page: _AuraPage, selected: str) -> None:
        """Offer the known auras in *page*'s selector, keeping *selected*."""
        names = page.known_names()
        combo = page.projecting
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_NONE)
        combo.addItems(names)
        combo.setCurrentIndex(names.index(selected) + 1 if selected in names else 0)
        combo.blockSignals(False)

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        """The known auras, with ``active`` set on each projected aura."""
        result: list[dict] = []  # type: ignore[type-arg]
        for page in (self._minor, self._major):
            projected = page.projected_name()
            for name in page.known_names():
                result.append(
                    {
                        "aura_name": name,
                        "aura_type": page.aura_type,
                        "active": name == projected,
                    }
                )
        return result

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.marshal_auras = self._entries()
            self._model.marshal_auras_changed.emit()

    def _on_known_changed(self, page: _AuraPage, item: QListWidgetItem) -> None:
        known_cap, _active_cap = self._limits(page)
        if (
            item.checkState() == Qt.CheckState.Checked
            and len(page.known_names()) > known_cap
        ):
            # Over the auras-known cap for this marshal level: undo the check.
            page.known.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            page.known.blockSignals(False)
            return
        self._refresh_projecting(page, page.projected_name())
        self._refresh_limits()
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        """Rebuild both lists from the catalogue and the character's auras."""
        self._populate()
        entries = self._model.character.marshal_auras if self._model else []
        known = {str(e.get("aura_name") or "") for e in entries}
        for page in (self._minor, self._major):
            page.known.blockSignals(True)
            for i in range(page.known.count()):
                item = page.known.item(i)
                if item is not None and item.text() in known:
                    item.setCheckState(Qt.CheckState.Checked)
            page.known.blockSignals(False)
            names = set(page.known_names())
            projected = next(
                (
                    str(e.get("aura_name"))
                    for e in entries
                    if e.get("active") and e.get("aura_name") in names
                ),
                "",
            )
            self._refresh_projecting(page, projected)
        self._refresh_limits()
