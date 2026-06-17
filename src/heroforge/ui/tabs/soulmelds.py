"""Soulmelds tab for HeroForge-Anew.

Reference: Magic of Incarnum.  Soulmelds are loaded from the seeded
``soulmelds`` catalogue (each with a chakra and an essentia capacity) and the
character's shaped soulmelds persist to :attr:`Character.soulmelds` (each entry
``{"soulmeld_name", "chakra_bound", "essentia_invested"}``; ``chakra_bound`` is
the chakra name when the soulmeld is bound, or ``""`` when merely shaped).

The essentia pool, meldshaper level, per-soulmeld essentia capacity and the
number of available chakra binds are auto-calculated from the character's
meldshaping class levels via :func:`heroforge.logic.incarnum.compute_incarnum`.
The total essentia pool is stored as the ``essentia_pool`` build option, with
``essentia_pool_auto`` recording whether the auto-calculated value is in use.
Chakra-bind limits are enforced in the UI: at most
:attr:`IncarnumSummary.chakra_binds_available` soulmelds may be bound at once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.incarnum import IncarnumSummary, compute_incarnum
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from collections.abc import Mapping

    from heroforge.logic.incarnum import IncarnumProgression
    from heroforge.ui.main_window import CharacterModel

_OPTION_KEY = "essentia_pool"
_AUTO_KEY = "essentia_pool_auto"

#: Incarnum feat that grants bonus essentia (MoI p41); the workbook adds +2 to
#: the pool when more than one soulmeld is shaped, otherwise +1.
_BONUS_ESSENTIA_FEAT = "Bonus Essentia"

# Shaped-soulmeld table columns.
_COL_NAME = 0
_COL_CHAKRA = 1
_COL_BOUND = 2
_COL_ESSENTIA = 3


class SoulmeldsTab(QWidget):
    """Soulmeld shaping and essentia management backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Catalogue lookups: name -> chakra, name -> essentia capacity.
        self._chakra: dict[str, str] = {}
        self._capacity: dict[str, int] = {}
        self._progressions: Mapping[str, IncarnumProgression] | None = None
        self._summary = IncarnumSummary(0, 0, 0, 0, 0)
        self._loading = False
        self._auto_apply = False
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.derived_stats_changed.connect(self._recalculate)
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        pool_box = QGroupBox("Essentia Pool")
        pool_form = QFormLayout(pool_box)
        self._meldshaper_lbl = QLabel("0")
        self._auto_chk = QCheckBox("Auto-calculate from class levels")
        self._auto_chk.setChecked(True)
        self._total_spin = QSpinBox()
        self._total_spin.setRange(0, 99)
        self._invested_lbl = QLabel("0")
        self._remaining_lbl = QLabel("0")
        self._capacity_lbl = QLabel("0")
        self._binds_lbl = QLabel("0 / 0")
        self._auto_chk.toggled.connect(self._on_auto_toggled)
        self._total_spin.valueChanged.connect(self._on_total_changed)
        pool_form.addRow("Meldshaper Level:", self._meldshaper_lbl)
        pool_form.addRow("", self._auto_chk)
        pool_form.addRow("Total Essentia:", self._total_spin)
        pool_form.addRow("Invested:", self._invested_lbl)
        pool_form.addRow("Remaining:", self._remaining_lbl)
        pool_form.addRow("Essentia Capacity:", self._capacity_lbl)
        pool_form.addRow("Chakra Binds:", self._binds_lbl)
        inner_layout.addWidget(pool_box)

        melds_box = QGroupBox("Shaped Soulmelds")
        melds_layout = QVBoxLayout(melds_box)
        self._melds_table = QTableWidget(0, 4)
        self._melds_table.setHorizontalHeaderLabels(
            ["Soulmeld", "Chakra", "Bound", "Essentia"]
        )
        header = self._melds_table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)
        melds_layout.addWidget(self._melds_table)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Shape Soulmeld…")
        self._rm_btn = QPushButton("Remove")
        self._add_btn.clicked.connect(self._add)
        self._rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        melds_layout.addLayout(btn_row)
        inner_layout.addWidget(melds_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Auto-calculation
    # ------------------------------------------------------------------

    def _progression_catalogue(self) -> Mapping[str, IncarnumProgression]:
        """Return the seeded meldshaping-class catalogue, fetched once."""
        if self._progressions is None and self._model is not None:
            self._progressions = self._model.game_data().incarnum_progressions()
        return self._progressions or {}

    def _feat_essentia_bonus(self) -> int:
        """Return bonus essentia from feats (MoI p41 Bonus Essentia)."""
        if self._model is None:
            return 0
        feats = self._model.character.feats
        if _BONUS_ESSENTIA_FEAT not in feats:
            return 0
        return 2 if self._row_count() > 1 else 1

    def _compute_summary(self) -> IncarnumSummary:
        """Return the auto-calculated incarnum totals for the character."""
        if self._model is None:
            return IncarnumSummary(0, 0, 0, 0, 0)
        character = self._model.character
        catalogue = self._progression_catalogue()
        return compute_incarnum(
            character.classes,
            character.total_level,
            self._feat_essentia_bonus(),
            catalogue or None,
        )

    def _recalculate(self) -> None:
        """Refresh derived incarnum values from the current class levels.

        Connected to :attr:`CharacterModel.derived_stats_changed` so changes to
        class levels or feats flow straight into the display, including the
        essentia pool when auto-calculation is enabled.
        """
        self._summary = self._compute_summary()
        self._meldshaper_lbl.setText(str(self._summary.meldshaper_level))
        self._capacity_lbl.setText(str(self._summary.soulmeld_capacity))
        self._apply_essentia_capacity()
        if self._auto_chk.isChecked():
            self._set_total_auto(self._summary.essentia_pool)
        self._refresh_pool()
        self._refresh_binds()

    def _set_total_auto(self, value: int) -> None:
        """Set the total-essentia spin box from a computed value, keeping auto."""
        self._auto_apply = True
        try:
            self._total_spin.setValue(value)
        finally:
            self._auto_apply = False
        if not self._loading and self._model is not None:
            self._model.character.options[_OPTION_KEY] = str(self._total_spin.value())

    def _on_auto_toggled(self, checked: bool) -> None:
        self._total_spin.setEnabled(not checked)
        if self._loading:
            return
        if self._model is not None:
            self._model.character.options[_AUTO_KEY] = "true" if checked else "false"
        if checked:
            self._recalculate()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _row_count(self) -> int:
        return self._melds_table.rowCount()

    def _invested_total(self) -> int:
        total = 0
        for row in range(self._row_count()):
            spin = self._melds_table.cellWidget(row, _COL_ESSENTIA)
            if isinstance(spin, QSpinBox):
                total += spin.value()
        return total

    def _bound_count(self) -> int:
        total = 0
        for row in range(self._row_count()):
            if self._is_bound(row):
                total += 1
        return total

    def _is_bound(self, row: int) -> bool:
        chk = self._bound_checkbox(row)
        return chk is not None and chk.isChecked()

    def _bound_checkbox(self, row: int) -> QCheckBox | None:
        holder = self._melds_table.cellWidget(row, _COL_BOUND)
        if holder is None:
            return None
        return holder.findChild(QCheckBox)

    def _refresh_pool(self) -> None:
        invested = self._invested_total()
        total = self._total_spin.value()
        self._invested_lbl.setText(str(invested))
        self._remaining_lbl.setText(str(max(0, total - invested)))

    def _refresh_binds(self) -> None:
        available = self._summary.chakra_binds_available
        self._binds_lbl.setText(f"{self._bound_count()} / {available}")

    def _row_capacity(self, name: str) -> int:
        """Return the essentia cap for *name*: the lesser of the soulmeld's own
        capacity and the character-level capacity."""
        meld_cap = self._capacity.get(name, 0)
        level_cap = self._summary.soulmeld_capacity
        caps = [c for c in (meld_cap, level_cap) if c > 0]
        return min(caps) if caps else 0

    def _apply_essentia_capacity(self) -> None:
        """Clamp every row's essentia spin box to the current capacity."""
        for row in range(self._row_count()):
            name_item = self._melds_table.item(row, _COL_NAME)
            spin = self._melds_table.cellWidget(row, _COL_ESSENTIA)
            if name_item is None or not isinstance(spin, QSpinBox):
                continue
            cap = self._row_capacity(name_item.text())
            spin.setMaximum(cap)

    def _on_total_changed(self, value: int) -> None:
        self._refresh_pool()
        if self._loading or self._auto_apply:
            return
        # A genuine user edit is a manual override: drop auto mode so the typed
        # value is preserved instead of being recomputed.
        if self._auto_chk.isChecked():
            self._auto_chk.setChecked(False)
        if self._model is not None:
            self._model.character.options[_OPTION_KEY] = str(value)

    def _add_row(
        self, name: str, chakra: str, essentia: int, bound: bool = False
    ) -> None:
        row = self._row_count()
        self._melds_table.insertRow(row)
        self._melds_table.setItem(row, _COL_NAME, QTableWidgetItem(name))
        self._melds_table.setItem(row, _COL_CHAKRA, QTableWidgetItem(chakra))

        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox = QCheckBox()
        checkbox.setChecked(bound)
        checkbox.toggled.connect(self._on_bound_toggled)
        holder_layout.addWidget(checkbox)
        self._melds_table.setCellWidget(row, _COL_BOUND, holder)

        spin = QSpinBox()
        spin.setRange(0, self._row_capacity(name) or 0)
        spin.setValue(min(essentia, spin.maximum()))
        spin.valueChanged.connect(self._on_essentia_changed)
        self._melds_table.setCellWidget(row, _COL_ESSENTIA, spin)

    def _on_bound_toggled(self, checked: bool) -> None:
        # Enforce the chakra-bind limit: refuse to bind more soulmelds than the
        # character has open chakras.
        if (
            checked
            and not self._loading
            and self._bound_count() > self._summary.chakra_binds_available
        ):
            sender = self.sender()
            if isinstance(sender, QCheckBox):
                sender.blockSignals(True)
                sender.setChecked(False)
                sender.blockSignals(False)
        self._refresh_binds()
        self._sync_to_model()

    def _on_essentia_changed(self, _value: int) -> None:
        # Clamp total invested to the pool: revert the offending change.
        if self._invested_total() > self._total_spin.value():
            sender = self.sender()
            if isinstance(sender, QSpinBox):
                over = self._invested_total() - self._total_spin.value()
                sender.blockSignals(True)
                sender.setValue(max(0, sender.value() - over))
                sender.blockSignals(False)
        self._refresh_pool()
        self._sync_to_model()

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for row in range(self._row_count()):
            name_item = self._melds_table.item(row, _COL_NAME)
            chakra_item = self._melds_table.item(row, _COL_CHAKRA)
            spin = self._melds_table.cellWidget(row, _COL_ESSENTIA)
            if name_item is None:
                continue
            chakra = chakra_item.text() if chakra_item else ""
            result.append(
                {
                    "soulmeld_name": name_item.text(),
                    # Persist the bound chakra only when actually bound.
                    "chakra_bound": chakra if self._is_bound(row) else "",
                    "essentia_invested": (
                        spin.value() if isinstance(spin, QSpinBox) else 0
                    ),
                }
            )
        return result

    def _names(self) -> set[str]:
        return {e["soulmeld_name"] for e in self._entries()}

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.soulmelds = self._entries()

    def shape_soulmeld(
        self, name: str, chakra: str = "", essentia: int = 0, bound: bool = False
    ) -> bool:
        """Shape soulmeld *name*; rejects duplicates. Returns acceptance."""
        name = name.strip()
        if not name or name in self._names():
            return False
        self._add_row(name, chakra, essentia, bound)
        self._refresh_pool()
        self._refresh_binds()
        self._sync_to_model()
        return True

    def _add(self) -> None:
        melds = self._model.game_data().list_soulmelds() if self._model else []
        self._chakra = {m.name: m.chakra for m in melds}
        self._capacity = {m.name: m.essentia_capacity for m in melds}
        options = [m.name for m in melds if m.name not in self._names()]
        name = pick_from_catalog(self, "Shape Soulmeld", "Soulmeld:", options)
        if name:
            self.shape_soulmeld(name, self._chakra.get(name, ""))

    def _remove(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._melds_table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self._melds_table.removeRow(row)
        self._refresh_pool()
        self._refresh_binds()
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        self._melds_table.setRowCount(0)
        if self._model is not None:
            melds = self._model.game_data().list_soulmelds()
            self._chakra = {m.name: m.chakra for m in melds}
            self._capacity = {m.name: m.essentia_capacity for m in melds}
            self._summary = self._compute_summary()
            self._meldshaper_lbl.setText(str(self._summary.meldshaper_level))
            self._capacity_lbl.setText(str(self._summary.soulmeld_capacity))

            opts = self._model.character.options
            auto_raw = opts.get(_AUTO_KEY)
            try:
                stored_total = int(opts.get(_OPTION_KEY, "0"))
            except (TypeError, ValueError):
                stored_total = 0
            if auto_raw is None:
                # Legacy saves predate the auto flag: treat a stored total that
                # differs from the computed value as a manual override.
                auto = not (
                    _OPTION_KEY in opts and stored_total != self._summary.essentia_pool
                )
            else:
                auto = auto_raw != "false"
            total = self._summary.essentia_pool if auto else stored_total
            self._auto_chk.setChecked(auto)
            self._total_spin.setEnabled(not auto)
            self._total_spin.setValue(total)

            for entry in self._model.character.soulmelds:
                name = entry.get("soulmeld_name", "")
                stored_chakra = entry.get("chakra_bound", "") or ""
                # Display the soulmeld's home chakra; a non-empty stored chakra
                # means it was bound.
                chakra = self._chakra.get(name) or stored_chakra
                self._add_row(
                    name,
                    chakra,
                    int(entry.get("essentia_invested", 0) or 0),
                    bool(stored_chakra),
                )
        else:
            self._auto_chk.setChecked(True)
            self._total_spin.setEnabled(False)
            self._total_spin.setValue(0)
        self._loading = False
        self._apply_essentia_capacity()
        self._refresh_pool()
        self._refresh_binds()
