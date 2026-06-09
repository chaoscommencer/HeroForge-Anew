"""LG MIL / Item Access Tracking tab for HeroForge-Anew.

The Living Greyhawk (LG) *Magic Item Log* (MIL) — also called Item Access
Tracking — is the campaign logbook of the magic items a character has gained
access to during organised play.  Each row records one item: the date it was
acquired, the item's name, its gold-piece value, and the adventure-record /
access source that granted it (stored as a free-text note).

Rows are persisted to :attr:`Character.lg_records` with
``record_type == "item_access"``; other Living Greyhawk record types (the LG
Game Log, …) sharing that list are preserved untouched.  This mirrors the
:class:`~heroforge.ui.tabs.lg_game_log.LGGameLogTab`, which manages the
``game_log`` record type on the same list.

Living Greyhawk content is legacy: this tab is **deprecated** and retained only
for backwards compatibility (see ``docs/conversion-plan.md`` §§11.1, 14).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

#: ``record_type`` discriminator stored on Item Access rows in ``lg_records``.
RECORD_TYPE = "item_access"

_HEADERS = ["Date", "Item", "GP Value", "Source / AR"]


def _to_float(text: str) -> float:
    try:
        return float(text.strip())
    except (TypeError, ValueError):
        return 0.0


def _fmt_number(value: object) -> str:
    """Render a stored gp value without a redundant trailing ``.0``."""
    number = _to_float(str(value))
    if number == int(number):
        return str(int(number))
    return str(number)


class LGItemAccessTab(QWidget):
    """Living Greyhawk magic-item / item-access log backed by the model.

    .. deprecated::
        Living Greyhawk support is legacy and will be removed in a future
        release.
    """

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Guard so programmatic table population does not echo back to the model.
        self._loading = False
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._sync_from_model()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        banner = QLabel(
            "Deprecated: Living Greyhawk content is retained"
            " for legacy characters only."
        )
        banner.setWordWrap(True)
        banner.setObjectName("lgDeprecationNotice")
        layout.addWidget(banner)

        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        header = self._table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Item")
        rm_btn = QPushButton("Remove Selected")
        add_btn.clicked.connect(lambda: self.add_record())
        rm_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------

    def _append_row(self, values: list[str]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, value in enumerate(values):
            self._table.setItem(row, col, QTableWidgetItem(value))

    def _row_values(self, row: int) -> list[str]:
        result = []
        for col in range(len(_HEADERS)):
            item = self._table.item(row, col)
            result.append(item.text() if item else "")
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_record(
        self,
        event_date: str = "",
        item: str = "",
        gp_value: float = 0.0,
        source: str = "",
    ) -> None:
        """Append an item-access row and persist it to the model."""
        self._loading = True
        self._append_row(
            [
                event_date,
                item,
                _fmt_number(gp_value),
                source,
            ]
        )
        self._loading = False
        self._sync_to_model()

    # ------------------------------------------------------------------
    # Model synchronisation
    # ------------------------------------------------------------------

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for row in range(self._table.rowCount()):
            date, item, gp, source = self._row_values(row)
            result.append(
                {
                    "record_type": RECORD_TYPE,
                    "event_date": date.strip() or None,
                    "description": item.strip() or None,
                    "gp_change": _to_float(gp),
                    "xp_change": 0.0,
                    "notes": source.strip() or None,
                }
            )
        return result

    def _sync_to_model(self) -> None:
        if self._model is None:
            return
        # Replace item_access records in-place so that the relative ordering of
        # other LG record types (Game Log, …) is preserved.  Excess old
        # item_access slots are dropped; extra new entries are appended.
        new_entries = iter(self._entries())
        result: list[dict] = []  # type: ignore[type-arg]
        for r in self._model.character.lg_records:
            if r.get("record_type") == RECORD_TYPE:
                replacement = next(new_entries, None)
                if replacement is not None:
                    result.append(replacement)
                # else: old slot has no corresponding new entry → drop it.
            else:
                result.append(r)
        # Any new entries beyond the original item_access count go at the end.
        result.extend(new_entries)
        self._model.character.lg_records = result

    def _sync_from_model(self) -> None:
        self._loading = True
        self._table.setRowCount(0)
        if self._model is not None:
            for entry in self._model.character.lg_records:
                if entry.get("record_type") != RECORD_TYPE:
                    continue
                self._append_row(
                    [
                        str(entry.get("event_date") or ""),
                        str(entry.get("description") or ""),
                        _fmt_number(entry.get("gp_change", 0)),
                        str(entry.get("notes") or ""),
                    ]
                )
        self._loading = False

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            self._sync_to_model()

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self._table.removeRow(row)
        self._sync_to_model()
