"""Psionics tab for HeroForge-Anew.

Reference: Expanded Psionics Handbook.  Powers are loaded from the seeded
``psionic_powers`` catalogue and persisted to :attr:`Character.psionic_powers`
(each entry ``{"class_name", "power_level", "power_name"}``).  The daily
power-point pool is stored in the ``psionic_total_pp``/``psionic_spent_pp``
build options.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.psionics import PsionicsSummary, compute_psionics
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_TOTAL_KEY = "psionic_total_pp"
_SPENT_KEY = "psionic_spent_pp"
_AUTO_KEY = "psionic_pp_auto"


class PsionicsTab(QWidget):
    """Psionic power point tracking and power management backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
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

        pp_box = QGroupBox("Power Points")
        pp_form = QFormLayout(pp_box)
        self._manifester_lbl = QLabel("0")
        self._auto_pp = QCheckBox("Auto-calculate from class levels")
        self._auto_pp.setChecked(True)
        self._total_pp = QSpinBox()
        self._total_pp.setRange(0, 9999)
        self._spent_pp = QSpinBox()
        self._spent_pp.setRange(0, 9999)
        self._remaining_lbl = QLabel("0")
        pp_form.addRow("Manifester Level:", self._manifester_lbl)
        pp_form.addRow("", self._auto_pp)
        pp_form.addRow("Total PP/Day:", self._total_pp)
        pp_form.addRow("Spent:", self._spent_pp)
        pp_form.addRow("Remaining:", self._remaining_lbl)
        self._auto_pp.toggled.connect(self._on_auto_toggled)
        self._total_pp.valueChanged.connect(self._on_total_changed)
        self._spent_pp.valueChanged.connect(self._on_spent_changed)
        inner_layout.addWidget(pp_box)

        powers_box = QGroupBox("Known Powers")
        powers_layout = QVBoxLayout(powers_box)
        self._powers_list = QListWidget()
        powers_layout.addWidget(self._powers_list)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Power…")
        self._rm_btn = QPushButton("Remove")
        self._add_btn.clicked.connect(self._add)
        self._rm_btn.clicked.connect(self._remove)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        powers_layout.addLayout(btn_row)
        inner_layout.addWidget(powers_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _update_remaining(self) -> None:
        remaining = max(0, self._total_pp.value() - self._spent_pp.value())
        self._remaining_lbl.setText(str(remaining))

    def _compute_summary(self) -> PsionicsSummary:
        """Return the auto-calculated manifester level and power points."""
        if self._model is None:
            return PsionicsSummary(manifester_level=0, power_points=0)
        character = self._model.character
        return compute_psionics(character.classes, character.ability_scores)

    def _recalculate(self) -> None:
        """Refresh the manifester level and (when auto) the power-point total.

        Connected to :attr:`CharacterModel.derived_stats_changed` so changes to
        class levels or the key ability score flow straight into the display.
        """
        summary = self._compute_summary()
        self._manifester_lbl.setText(str(summary.manifester_level))
        if self._auto_pp.isChecked():
            self._set_total_auto(summary.power_points)

    def _set_total_auto(self, value: int) -> None:
        """Set the total PP spin box from a computed value without unsetting auto."""
        self._auto_apply = True
        try:
            self._total_pp.setValue(value)
        finally:
            self._auto_apply = False
        self._spent_pp.setMaximum(self._total_pp.value())
        self._update_remaining()
        if not self._loading and self._model is not None:
            self._model.character.options[_TOTAL_KEY] = str(value)

    def _on_auto_toggled(self, checked: bool) -> None:
        self._total_pp.setEnabled(not checked)
        if self._loading:
            return
        if self._model is not None:
            self._model.character.options[_AUTO_KEY] = "true" if checked else "false"
        if checked:
            self._recalculate()

    def _on_total_changed(self, value: int) -> None:
        self._spent_pp.setMaximum(value)
        self._update_remaining()
        if self._loading or self._auto_apply:
            return
        # A genuine user edit is treated as a manual override: drop auto mode so
        # the typed value is preserved instead of being recomputed.
        if self._auto_pp.isChecked():
            self._auto_pp.setChecked(False)
        if self._model is not None:
            self._model.character.options[_TOTAL_KEY] = str(value)

    def _on_spent_changed(self, value: int) -> None:
        self._update_remaining()
        if self._loading:
            return
        if self._model is not None:
            self._model.character.options[_SPENT_KEY] = str(value)

    def _power_names(self) -> list[str]:
        return [
            item.text()
            for i in range(self._powers_list.count())
            if (item := self._powers_list.item(i)) is not None
        ]

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.psionic_powers = [
                {"class_name": "", "power_level": 0, "power_name": name}
                for name in self._power_names()
            ]

    def add_power(self, name: str) -> bool:
        """Add known power *name*; rejects duplicates. Returns acceptance."""
        name = name.strip()
        if not name or name in self._power_names():
            return False
        self._powers_list.addItem(QListWidgetItem(name))
        self._sync_to_model()
        return True

    def _add(self) -> None:
        powers = self._model.game_data().list_psionic_powers() if self._model else []
        options = [p.name for p in powers if p.name not in self._power_names()]
        name = pick_from_catalog(self, "Add Power", "Power:", options)
        if name:
            self.add_power(name)

    def _remove(self) -> None:
        for item in self._powers_list.selectedItems():
            self._powers_list.takeItem(self._powers_list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        try:
            self._powers_list.clear()
            summary = self._compute_summary()
            self._manifester_lbl.setText(str(summary.manifester_level))
            if self._model is not None:
                opts = self._model.character.options
                try:
                    total = int(opts.get(_TOTAL_KEY, "0"))
                    spent = int(opts.get(_SPENT_KEY, "0"))
                except (TypeError, ValueError):
                    total = 0
                    spent = 0
                auto_raw = opts.get(_AUTO_KEY)
                if auto_raw is None:
                    # Legacy saves predate the auto flag: treat a stored total
                    # that differs from the computed value as a manual override.
                    auto = not (_TOTAL_KEY in opts and total != summary.power_points)
                else:
                    auto = auto_raw != "false"
                if auto:
                    total = summary.power_points
                self._auto_pp.setChecked(auto)
                self._total_pp.setEnabled(not auto)
                self._total_pp.setValue(total)
                self._spent_pp.setMaximum(total)
                self._spent_pp.setValue(min(spent, total))
                for entry in self._model.character.psionic_powers:
                    name = entry.get("power_name", "")
                    if name:
                        self._powers_list.addItem(QListWidgetItem(name))
            else:
                self._auto_pp.setChecked(True)
                self._total_pp.setEnabled(False)
                self._total_pp.setValue(0)
                self._spent_pp.setMaximum(0)
                self._spent_pp.setValue(0)
        finally:
            self._loading = False
        self._update_remaining()
