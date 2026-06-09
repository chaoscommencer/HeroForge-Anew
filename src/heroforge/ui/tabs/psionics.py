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

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_TOTAL_KEY = "psionic_total_pp"
_SPENT_KEY = "psionic_spent_pp"


class PsionicsTab(QWidget):
    """Psionic power point tracking and power management backed by the model."""

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

        pp_box = QGroupBox("Power Points")
        pp_form = QFormLayout(pp_box)
        self._total_pp = QSpinBox()
        self._total_pp.setRange(0, 9999)
        self._spent_pp = QSpinBox()
        self._spent_pp.setRange(0, 9999)
        self._remaining_lbl = QLabel("0")
        pp_form.addRow("Total PP/Day:", self._total_pp)
        pp_form.addRow("Spent:", self._spent_pp)
        pp_form.addRow("Remaining:", self._remaining_lbl)
        self._total_pp.valueChanged.connect(self._on_pp_changed)
        self._spent_pp.valueChanged.connect(self._on_pp_changed)
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

    def _on_pp_changed(self, _value: int) -> None:
        self._spent_pp.setMaximum(self._total_pp.value())
        self._update_remaining()
        if not self._loading and self._model is not None:
            self._model.character.options[_TOTAL_KEY] = str(self._total_pp.value())
            self._model.character.options[_SPENT_KEY] = str(self._spent_pp.value())

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
        self._powers_list.clear()
        if self._model is not None:
            opts = self._model.character.options
            try:
                self._total_pp.setValue(int(opts.get(_TOTAL_KEY, "0")))
                self._spent_pp.setValue(int(opts.get(_SPENT_KEY, "0")))
            except (TypeError, ValueError):
                self._total_pp.setValue(0)
                self._spent_pp.setValue(0)
            for entry in self._model.character.psionic_powers:
                name = entry.get("power_name", "")
                if name:
                    self._powers_list.addItem(QListWidgetItem(name))
        self._loading = False
        self._update_remaining()
