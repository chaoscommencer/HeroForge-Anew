"""Attacks tab for HeroForge-Anew.

Combat statistics (BAB, melee/ranged attack, grapple) are computed from the
character's derived stats and refresh in real time.  Weapons are loaded from the
seeded ``weapons`` catalogue and persisted to :attr:`Character.attacks`; each
weapon's attack bonus is recomputed from BAB and the relevant ability modifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.db.data_access import WeaponItem
    from heroforge.ui.main_window import CharacterModel


def _signed(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


class AttacksTab(QWidget):
    """Weapon attack and damage configuration backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.derived_stats_changed.connect(self._refresh_combat_stats)
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._refresh_combat_stats()
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        combat_box = QGroupBox("Combat Statistics")
        combat_form = QFormLayout(combat_box)
        self._bab_lbl = QLabel("0")
        self._melee_lbl = QLabel("0")
        self._ranged_lbl = QLabel("0")
        self._grapple_lbl = QLabel("0")
        combat_form.addRow("Base Attack Bonus:", self._bab_lbl)
        combat_form.addRow("Melee Attack:", self._melee_lbl)
        combat_form.addRow("Ranged Attack:", self._ranged_lbl)
        combat_form.addRow("Grapple:", self._grapple_lbl)
        inner_layout.addWidget(combat_box)

        weapons_box = QGroupBox("Equipped Weapons")
        weapons_layout = QVBoxLayout(weapons_box)
        self._headers = ["Weapon", "Attack Bonus", "Damage", "Crit", "Range", "Type"]
        self._weapons_table = QTableWidget(0, len(self._headers))
        self._weapons_table.setHorizontalHeaderLabels(self._headers)
        header = self._weapons_table.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        weapons_layout.addWidget(self._weapons_table)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Weapon")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add_weapon)
        self._rm_btn.clicked.connect(self._remove_weapon)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._rm_btn)
        btn_row.addStretch()
        weapons_layout.addLayout(btn_row)
        inner_layout.addWidget(weapons_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Combat statistics
    # ------------------------------------------------------------------

    def _refresh_combat_stats(self) -> None:
        """Display BAB/melee/ranged/grapple computed from the active character."""
        if not self._model:
            return
        stats = self._model.derived_stats()
        self._bab_lbl.setText(_signed(stats.base_attack_bonus))
        self._melee_lbl.setText(_signed(stats.melee_attack))
        self._ranged_lbl.setText(_signed(stats.ranged_attack))
        self._grapple_lbl.setText(_signed(stats.grapple))
        self._recompute_attack_bonuses()

    def _attack_bonus_for(self, ranged: bool) -> str:
        if self._model is None:
            return "+0"
        stats = self._model.derived_stats()
        return _signed(stats.ranged_attack if ranged else stats.melee_attack)

    def _recompute_attack_bonuses(self) -> None:
        """Recompute each weapon's attack-bonus cell from current derived stats."""
        for row in range(self._weapons_table.rowCount()):
            range_item = self._weapons_table.item(row, 4)
            text = range_item.text().strip() if range_item else ""
            try:
                ranged = int(text) > 0
            except ValueError:
                ranged = text not in ("", "—")
            bonus = self._attack_bonus_for(ranged)
            self._weapons_table.setItem(row, 1, QTableWidgetItem(bonus))
        self._sync_to_model()

    # ------------------------------------------------------------------
    # Weapon rows
    # ------------------------------------------------------------------

    def _row_values(self, row: int) -> list[str]:
        values = []
        for col in range(len(self._headers)):
            item = self._weapons_table.item(row, col)
            values.append(item.text() if item else "")
        return values

    def _weapon_names(self) -> list[str]:
        return [
            self._row_values(row)[0] for row in range(self._weapons_table.rowCount())
        ]

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for row in range(self._weapons_table.rowCount()):
            name, bonus, damage, crit, rng, dtype = self._row_values(row)
            if not name:
                continue
            result.append(
                {
                    "weapon_name": name,
                    "attack_bonus": bonus,
                    "damage": damage,
                    "critical": crit,
                    "range_increment": rng,
                    "damage_type": dtype,
                    "ammunition": "",
                    "notes": "",
                }
            )
        return result

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.attacks = self._entries()

    def _append_row(self, values: list[str]) -> None:
        row = self._weapons_table.rowCount()
        self._weapons_table.insertRow(row)
        for col, value in enumerate(values):
            self._weapons_table.setItem(row, col, QTableWidgetItem(value))

    def add_weapon(self, weapon: WeaponItem | None = None, name: str = "") -> None:
        """Add a weapon row from a catalogue *weapon* or a bare *name*."""
        if weapon is not None:
            ranged = weapon.range_increment > 0
            values = [
                weapon.name,
                self._attack_bonus_for(ranged),
                weapon.damage,
                weapon.critical,
                str(weapon.range_increment) if weapon.range_increment else "—",
                weapon.damage_type,
            ]
        else:
            values = [
                name or "New Weapon",
                self._attack_bonus_for(False),
                "",
                "",
                "—",
                "",
            ]
        self._append_row(values)
        self._sync_to_model()

    def _add_weapon(self) -> None:
        weapons = self._model.game_data().list_weapons() if self._model else []
        catalog = {w.name: w for w in weapons}
        name = pick_from_catalog(self, "Add Weapon", "Weapon:", list(catalog.keys()))
        if name is None:
            return
        self.add_weapon(catalog.get(name), name=name)

    def _remove_weapon(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._weapons_table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self._weapons_table.removeRow(row)
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._weapons_table.setRowCount(0)
        if self._model is not None:
            for entry in self._model.character.attacks:
                self._append_row(
                    [
                        entry.get("weapon_name", ""),
                        entry.get("attack_bonus", ""),
                        entry.get("damage", ""),
                        entry.get("critical", ""),
                        entry.get("range_increment", ""),
                        entry.get("damage_type", ""),
                    ]
                )
        self._recompute_attack_bonuses()
