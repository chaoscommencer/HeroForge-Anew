"""Animal Companion tab for HeroForge-Anew.

Reference: PHB p35 (Druid class feature), p52 (Ranger).  The companion's species
can be chosen from the seeded ``creatures`` catalogue (auto-filling its ability
scores), and all fields are persisted to :attr:`Character.companions` as a
single ``companion_type == "animal"`` entry (detailed stats are serialised into
the ``notes`` column as JSON so they round-trip through save/load).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_COMPANION_TYPE = "animal"
_ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


class AnimalCompanionTab(QWidget):
    """Animal companion statistics and management backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._loading = False
        self._ability_spins: dict[str, QSpinBox] = {}
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

        id_box = QGroupBox("Animal Companion Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        self._species_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_changed)
        self._species_edit.editingFinished.connect(self._on_changed)
        species_row = QHBoxLayout()
        species_row.addWidget(self._species_edit)
        select_btn = QPushButton("Select…")
        select_btn.clicked.connect(self._select_species)
        species_row.addWidget(select_btn)
        id_form.addRow("Name:", self._name_edit)
        id_form.addRow("Species:", species_row)
        inner_layout.addWidget(id_box)

        stats_box = QGroupBox("Companion Statistics")
        stats_form = QFormLayout(stats_box)
        for ability in _ABILITIES:
            spin = QSpinBox()
            spin.setRange(1, 50)
            spin.setValue(10)
            spin.valueChanged.connect(self._on_changed)
            self._ability_spins[ability] = spin
            stats_form.addRow(f"{ability}:", spin)
        self._hp_spin = QSpinBox()
        self._hp_spin.setRange(0, 9999)
        self._hp_spin.valueChanged.connect(self._on_changed)
        self._hd_edit = QLineEdit()
        self._hd_edit.editingFinished.connect(self._on_changed)
        stats_form.addRow("HP:", self._hp_spin)
        stats_form.addRow("Hit Dice:", self._hd_edit)
        inner_layout.addWidget(stats_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _entry(self) -> dict | None:  # type: ignore[type-arg]
        name = self._name_edit.text().strip()
        species = self._species_edit.text().strip()
        notes = {
            "scores": {a: self._ability_spins[a].value() for a in _ABILITIES},
            "hp": self._hp_spin.value(),
            "hd": self._hd_edit.text().strip(),
        }
        # Only persist when there's meaningful data to store.
        if not name and not species and not notes["hd"] and notes["hp"] == 0:
            return None
        return {
            "companion_type": _COMPANION_TYPE,
            "name": name,
            "creature": species,
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

    def _on_changed(self, *_args: object) -> None:
        if not self._loading:
            self._sync_to_model()

    def _select_species(self) -> None:
        creatures = self._model.game_data().list_creatures() if self._model else []
        by_name = {c.name: c for c in creatures}
        name = pick_from_catalog(self, "Select Species", "Creature:", list(by_name))
        if name is None:
            return
        self._species_edit.setText(name)
        creature = by_name.get(name)
        if creature is not None:
            self._loading = True
            for ability, score in creature.ability_scores.items():
                if ability in self._ability_spins:
                    self._ability_spins[ability].setValue(score)
            self._hd_edit.setText(creature.hit_dice)
            self._loading = False
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        self._name_edit.clear()
        self._species_edit.clear()
        for spin in self._ability_spins.values():
            spin.setValue(10)
        self._hp_spin.setValue(0)
        self._hd_edit.clear()
        if self._model is not None:
            for entry in self._model.character.companions:
                if entry.get("companion_type") != _COMPANION_TYPE:
                    continue
                self._name_edit.setText(entry.get("name", ""))
                self._species_edit.setText(entry.get("creature", ""))
                notes = entry.get("notes", "")
                try:
                    data = json.loads(notes) if notes else {}
                except (TypeError, ValueError):
                    data = {}
                for ability, score in (data.get("scores") or {}).items():
                    if ability in self._ability_spins:
                        self._ability_spins[ability].setValue(int(score))
                self._hp_spin.setValue(int(data.get("hp", 0) or 0))
                self._hd_edit.setText(str(data.get("hd", "")))
                break
        self._loading = False
