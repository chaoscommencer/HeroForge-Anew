"""Soulmelds tab for HeroForge-Anew.

Reference: Magic of Incarnum.  Soulmelds are loaded from the seeded
``soulmelds`` catalogue (each with a chakra and an essentia capacity) and the
character's shaped soulmelds persist to :attr:`Character.soulmelds` (each entry
``{"soulmeld_name", "chakra_bound", "essentia_invested"}``).  The total
essentia pool is stored as the ``essentia_pool`` build option.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
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

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_OPTION_KEY = "essentia_pool"


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

        pool_box = QGroupBox("Essentia Pool")
        pool_form = QFormLayout(pool_box)
        self._total_spin = QSpinBox()
        self._total_spin.setRange(0, 30)
        self._total_spin.valueChanged.connect(self._on_total_changed)
        self._invested_lbl = QLabel("0")
        self._remaining_lbl = QLabel("0")
        pool_form.addRow("Total Essentia:", self._total_spin)
        pool_form.addRow("Invested:", self._invested_lbl)
        pool_form.addRow("Remaining:", self._remaining_lbl)
        inner_layout.addWidget(pool_box)

        melds_box = QGroupBox("Shaped Soulmelds")
        melds_layout = QVBoxLayout(melds_box)
        self._melds_table = QTableWidget(0, 3)
        self._melds_table.setHorizontalHeaderLabels(["Soulmeld", "Chakra", "Essentia"])
        header = self._melds_table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
    # State helpers
    # ------------------------------------------------------------------

    def _row_count(self) -> int:
        return self._melds_table.rowCount()

    def _invested_total(self) -> int:
        total = 0
        for row in range(self._row_count()):
            spin = self._melds_table.cellWidget(row, 2)
            if isinstance(spin, QSpinBox):
                total += spin.value()
        return total

    def _refresh_pool(self) -> None:
        invested = self._invested_total()
        total = self._total_spin.value()
        self._invested_lbl.setText(str(invested))
        self._remaining_lbl.setText(str(max(0, total - invested)))

    def _on_total_changed(self, _value: int) -> None:
        self._refresh_pool()
        if not self._loading and self._model is not None:
            self._model.character.options[_OPTION_KEY] = str(self._total_spin.value())

    def _add_row(self, name: str, chakra: str, essentia: int) -> None:
        row = self._row_count()
        self._melds_table.insertRow(row)
        self._melds_table.setItem(row, 0, QTableWidgetItem(name))
        self._melds_table.setItem(row, 1, QTableWidgetItem(chakra))
        spin = QSpinBox()
        cap = self._capacity.get(name, 30)
        spin.setRange(0, cap if cap > 0 else 30)
        spin.setValue(min(essentia, spin.maximum()))
        spin.valueChanged.connect(self._on_essentia_changed)
        self._melds_table.setCellWidget(row, 2, spin)

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
            name_item = self._melds_table.item(row, 0)
            chakra_item = self._melds_table.item(row, 1)
            spin = self._melds_table.cellWidget(row, 2)
            if name_item is None:
                continue
            result.append(
                {
                    "soulmeld_name": name_item.text(),
                    "chakra_bound": chakra_item.text() if chakra_item else "",
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

    def shape_soulmeld(self, name: str, chakra: str = "", essentia: int = 0) -> bool:
        """Shape soulmeld *name*; rejects duplicates. Returns acceptance."""
        name = name.strip()
        if not name or name in self._names():
            return False
        self._add_row(name, chakra, essentia)
        self._refresh_pool()
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
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        self._melds_table.setRowCount(0)
        if self._model is not None:
            melds = self._model.game_data().list_soulmelds()
            self._chakra = {m.name: m.chakra for m in melds}
            self._capacity = {m.name: m.essentia_capacity for m in melds}
            total = self._model.character.options.get(_OPTION_KEY, "0")
            try:
                self._total_spin.setValue(int(total))
            except (TypeError, ValueError):
                self._total_spin.setValue(0)
            for entry in self._model.character.soulmelds:
                self._add_row(
                    entry.get("soulmeld_name", ""),
                    entry.get("chakra_bound", ""),
                    int(entry.get("essentia_invested", 0) or 0),
                )
        self._loading = False
        self._refresh_pool()
