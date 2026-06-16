"""Familiar tab for HeroForge-Anew.

Reference: PHB p52 (Wizard class feature).  The familiar's kind can be chosen
from the seeded ``creatures`` catalogue and all fields are persisted to
:attr:`Character.companions` as a single ``companion_type == "familiar"`` entry
(detailed stats serialised into the ``notes`` column as JSON so they round-trip
through save/load).  Standard familiars grant their master a fixed bonus shown
below.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.familiar import (
    STANDARD_FAMILIAR_BONUSES,
    STANDARD_FAMILIAR_MASTER_ABILITIES,
    CustomFamiliar,
    describe_bonus,
    list_custom_familiars,
)
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_COMPANION_TYPE = "familiar"

# Standard familiar bonuses granted to the master (PHB p52–53), generated from
# the single structured source so the fallback text matches the seeded data.
# Used when the game database has not been seeded with ``familiar_bonuses`` rows
# (see ``GameDataRepository.get_familiar_bonuses``).
_FAMILIAR_BONUSES: dict[str, str] = {
    bonus.creature_name.lower(): describe_bonus(bonus)
    for bonus in STANDARD_FAMILIAR_BONUSES
}

# Universal master benefits every familiar grants (Alertness, Scry, Natural
# Link).  Offline fallback for when ``familiar_master_abilities`` has not been
# seeded (see ``GameDataRepository.get_familiar_master_abilities``).
_FAMILIAR_MASTER_ABILITIES = STANDARD_FAMILIAR_MASTER_ABILITIES


class FamiliarTab(QWidget):
    """Familiar statistics and bonuses granted to master, backed by the model."""

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

        id_box = QGroupBox("Familiar Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        self._kind_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_changed)
        self._kind_edit.editingFinished.connect(self._on_kind_changed)
        kind_row = QHBoxLayout()
        kind_row.addWidget(self._kind_edit)
        select_btn = QPushButton("Select…")
        select_btn.clicked.connect(self._select_kind)
        kind_row.addWidget(select_btn)
        id_form.addRow("Name:", self._name_edit)
        id_form.addRow("Kind:", kind_row)
        inner_layout.addWidget(id_box)

        stats_box = QGroupBox("Familiar Statistics")
        stats_form = QFormLayout(stats_box)
        self._hp_spin = QSpinBox()
        self._hp_spin.setRange(0, 999)
        self._int_spin = QSpinBox()
        self._int_spin.setRange(1, 30)
        self._nat_armor_spin = QSpinBox()
        self._nat_armor_spin.setRange(0, 20)
        for spin in (self._hp_spin, self._int_spin, self._nat_armor_spin):
            spin.valueChanged.connect(self._on_changed)
        stats_form.addRow("HP:", self._hp_spin)
        stats_form.addRow("Intelligence:", self._int_spin)
        stats_form.addRow("Natural Armor Bonus:", self._nat_armor_spin)
        inner_layout.addWidget(stats_box)

        bonuses_box = QGroupBox("Bonuses Granted to Master")
        bonuses_layout = QVBoxLayout(bonuses_box)
        self._bonus_lbl = QLabel("(Select a familiar kind – see PHB p52.)")
        self._bonus_lbl.setWordWrap(True)
        bonuses_layout.addWidget(self._bonus_lbl)
        self._master_abilities_lbl = QLabel("")
        self._master_abilities_lbl.setWordWrap(True)
        bonuses_layout.addWidget(self._master_abilities_lbl)
        self._natural_link_check = QCheckBox(
            "Natural Link active (familiar within arm's reach – doubles bonuses)"
        )
        self._natural_link_check.toggled.connect(self._on_changed)
        bonuses_layout.addWidget(self._natural_link_check)
        inner_layout.addWidget(bonuses_box)
        self._refresh_master_abilities()

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _custom_familiars(self) -> list[CustomFamiliar]:
        """Return the homebrew familiars saved on the current character."""
        if self._model is None:
            return []
        return list_custom_familiars(self._model.character.custom_content)

    def _refresh_bonus(self) -> None:
        kind = self._kind_edit.text().strip().lower()
        bonuses = dict(
            (
                self._model.game_data().get_familiar_bonuses()
                if self._model is not None
                else {}
            )
            or _FAMILIAR_BONUSES
        )
        # Homebrew familiars contribute their free-text special bonus, keyed by
        # the familiar's name so selecting it surfaces the description.
        for familiar in self._custom_familiars():
            if familiar.special_bonus:
                bonuses[familiar.name.lower()] = familiar.special_bonus
        self._bonus_lbl.setText(
            bonuses.get(kind, "(Select a standard familiar kind – see PHB p52.)")
        )

    def _refresh_master_abilities(self) -> None:
        """Show the universal benefits every familiar grants its master.

        These are read from the seeded ``familiar_master_abilities`` table (the
        workbook's Special Abilities → Familiar entry), with an offline fallback
        to the canonical constant.
        """
        abilities = (
            self._model.game_data().get_familiar_master_abilities()
            if self._model is not None
            else []
        ) or list(_FAMILIAR_MASTER_ABILITIES)
        lines = "\n".join(f"• {a.name}: {a.description}" for a in abilities)
        self._master_abilities_lbl.setText(
            f"All familiars also grant their master:\n{lines}" if lines else ""
        )

    def _entry(self) -> dict | None:  # type: ignore[type-arg]
        name = self._name_edit.text().strip()
        kind = self._kind_edit.text().strip()
        notes = {
            "hp": self._hp_spin.value(),
            "int": self._int_spin.value(),
            "natural_armor": self._nat_armor_spin.value(),
            "natural_link": self._natural_link_check.isChecked(),
        }
        if not name and not kind and notes["hp"] == 0 and notes["natural_armor"] == 0:
            return None
        return {
            "companion_type": _COMPANION_TYPE,
            "name": name,
            "creature": kind,
            "notes": json.dumps(notes),
        }

    def _sync_to_model(self) -> None:
        if self._model is None:
            return
        others = [
            c
            for c in self._model.character.companions
            if c.get("companion_type") != _COMPANION_TYPE
        ]
        entry = self._entry()
        self._model.character.companions = (
            others + [entry] if entry is not None else others
        )
        # A familiar's master benefit can feed derived saves (e.g. Rat/Weasel),
        # so announce the change to refresh dependent tabs.
        self._model.derived_stats_changed.emit()

    def _on_changed(self, *_args: object) -> None:
        if not self._loading:
            self._sync_to_model()

    def _on_kind_changed(self) -> None:
        self._refresh_bonus()
        self._on_changed()

    def _select_kind(self) -> None:
        creatures = self._model.game_data().list_creatures() if self._model else []
        options = [c.name for c in creatures]
        # Surface homebrew familiars (Excel tab 9c) alongside the catalogue so a
        # saved custom familiar is selectable.  Custom names take precedence and
        # are de-duplicated against the catalogue.
        custom_names = [f.name for f in self._custom_familiars() if f.name]
        existing = {name.casefold() for name in options}
        options = [
            name for name in custom_names if name.casefold() not in existing
        ] + options
        name = pick_from_catalog(self, "Select Familiar", "Kind:", options)
        if name is not None:
            self._kind_edit.setText(name)
            self._refresh_bonus()
            self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        self._name_edit.clear()
        self._kind_edit.clear()
        self._hp_spin.setValue(0)
        self._int_spin.setValue(1)
        self._nat_armor_spin.setValue(0)
        self._natural_link_check.setChecked(False)
        if self._model is not None:
            for entry in self._model.character.companions:
                if entry.get("companion_type") != _COMPANION_TYPE:
                    continue
                self._name_edit.setText(entry.get("name", ""))
                self._kind_edit.setText(entry.get("creature", ""))
                notes = entry.get("notes", "")
                try:
                    data = json.loads(notes) if notes else {}
                except (TypeError, ValueError):
                    data = {}
                self._hp_spin.setValue(int(data.get("hp", 0) or 0))
                self._int_spin.setValue(int(data.get("int", 1) or 1))
                self._nat_armor_spin.setValue(int(data.get("natural_armor", 0) or 0))
                self._natural_link_check.setChecked(
                    bool(data.get("natural_link", False))
                )
                break
        self._loading = False
        self._refresh_bonus()
