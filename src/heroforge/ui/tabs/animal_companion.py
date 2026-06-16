"""Animal Companion tab for HeroForge-Anew.

Reference: PHB p35–36 (Druid class feature), p47 (Ranger).  The companion's
species can be chosen from the seeded ``creatures`` catalogue (auto-filling its
ability scores), and all fields are persisted to :attr:`Character.companions` as
a single ``companion_type == "animal"`` entry (detailed stats are serialised
into the ``notes`` column as JSON so they round-trip through save/load).

When a species is chosen from the catalogue its *base* stats are recorded so the
level-based progression (bonus Hit Dice, natural armor, Str/Dex adjustments,
bonus tricks and special qualities – PHB p36) can be applied automatically and
kept in sync as the master's effective druid level changes.  See
:mod:`heroforge.logic.animal_companion` for the progression logic.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
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

from heroforge.logic.animal_companion import (
    apply_progression,
    companion_progression,
    cumulative_special_qualities,
    effective_druid_level,
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
        # The selected species' *base* stats (before progression), recorded when
        # a species is picked from the catalogue so the level-based progression
        # can be re-applied whenever the effective druid level changes.
        self._base: dict[str, object] | None = None
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            # Re-apply the progression when class levels (and hence the
            # effective druid level) change.
            model.class_levels_changed.connect(self._refresh_progression)
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
        self._na_spin = QSpinBox()
        self._na_spin.setRange(0, 99)
        self._na_spin.valueChanged.connect(self._on_changed)
        self._hd_edit = QLineEdit()
        self._hd_edit.editingFinished.connect(self._on_changed)
        stats_form.addRow("HP:", self._hp_spin)
        stats_form.addRow("Natural Armor:", self._na_spin)
        stats_form.addRow("Hit Dice:", self._hd_edit)
        inner_layout.addWidget(stats_box)

        # Read-only summary of the level-based progression (PHB p36), driven by
        # the master's effective druid level.
        prog_box = QGroupBox("Level Progression")
        prog_form = QFormLayout(prog_box)
        self._eff_level_label = QLabel("0")
        self._bonus_hd_label = QLabel("+0")
        self._na_adj_label = QLabel("+0")
        self._ability_adj_label = QLabel("+0")
        self._bonus_tricks_label = QLabel("0")
        self._special_label = QLabel("—")
        self._special_label.setWordWrap(True)
        prog_form.addRow("Effective Druid Level:", self._eff_level_label)
        prog_form.addRow("Bonus HD:", self._bonus_hd_label)
        prog_form.addRow("Natural Armor Adj.:", self._na_adj_label)
        prog_form.addRow("Str/Dex Adj.:", self._ability_adj_label)
        prog_form.addRow("Bonus Tricks:", self._bonus_tricks_label)
        prog_form.addRow("Special:", self._special_label)
        inner_layout.addWidget(prog_box)

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
            "natural_armor": self._na_spin.value(),
            # "hd" stores the Hit Dice string (e.g. "3d8+6") shown in the
            # Hit Dice row; it determines HP-per-level and affects CR.
            "hd": self._hd_edit.text().strip(),
        }
        # Preserve the recorded base species so the progression can be re-applied
        # after a save/load round trip.
        if self._base is not None:
            notes["base"] = self._base
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
            # Record the base species stats so the level-based progression can
            # be applied (and re-applied as the effective druid level changes).
            self._base = {
                "scores": dict(creature.ability_scores),
                "natural_armor": int(creature.natural_armor),
                "hd": creature.hit_dice,
            }
            self._apply_progression()
        else:
            self._base = None
            self._update_progression_labels(self._effective_level())
        self._sync_to_model()

    # ------------------------------------------------------------------
    # Level-based progression (PHB p36)
    # ------------------------------------------------------------------

    def _effective_level(self) -> int:
        """Return the master's effective druid level for the companion."""
        if self._model is None:
            return 0
        character = self._model.character
        return effective_druid_level(
            character.classes, character.feats, character.total_level
        )

    def _refresh_progression(self) -> None:
        """Re-apply the progression after the effective druid level changes."""
        if self._loading:
            return
        self._apply_progression()
        self._sync_to_model()

    def _apply_progression(self) -> None:
        """Apply the level-based progression onto the recorded base species.

        When no base species has been recorded (manual entry) only the
        read-only progression summary is refreshed; the user's manually entered
        stats are left untouched.
        """
        level = self._effective_level()
        self._update_progression_labels(level)
        base = self._base
        if base is None:
            return
        raw_scores = base.get("scores")
        base_scores: dict[str, int] = {}
        if isinstance(raw_scores, dict):
            for ability, value in raw_scores.items():
                if isinstance(value, (int, float)):
                    base_scores[str(ability)] = int(value)
        raw_na = base.get("natural_armor", 0)
        base_na = int(raw_na) if isinstance(raw_na, (int, float)) else 0
        raw_hd = base.get("hd", "")
        base_hd = raw_hd if isinstance(raw_hd, str) else ""
        result = apply_progression(base_scores, base_na, base_hd, level)
        self._loading = True
        for ability, score in result.ability_scores.items():
            if ability in self._ability_spins:
                self._ability_spins[ability].setValue(score)
        self._na_spin.setValue(result.natural_armor)
        self._hd_edit.setText(result.hit_dice)
        self._loading = False

    def _update_progression_labels(self, level: int) -> None:
        """Refresh the read-only progression summary for *level*."""
        self._eff_level_label.setText(str(level))
        tier = companion_progression(level)
        if tier is None:
            self._bonus_hd_label.setText("+0")
            self._na_adj_label.setText("+0")
            self._ability_adj_label.setText("+0")
            self._bonus_tricks_label.setText("0")
            self._special_label.setText("—")
            return
        self._bonus_hd_label.setText(f"+{tier.bonus_hd}")
        self._na_adj_label.setText(f"+{tier.natural_armor}")
        self._ability_adj_label.setText(f"+{tier.ability_adjustment}")
        self._bonus_tricks_label.setText(str(tier.bonus_tricks))
        qualities = cumulative_special_qualities(level)
        self._special_label.setText(", ".join(qualities) if qualities else "—")

    def _sync_from_model(self) -> None:
        self._loading = True
        self._name_edit.clear()
        self._species_edit.clear()
        for spin in self._ability_spins.values():
            spin.setValue(10)
        self._hp_spin.setValue(0)
        self._na_spin.setValue(0)
        self._hd_edit.clear()
        self._base = None
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
                self._na_spin.setValue(int(data.get("natural_armor", 0) or 0))
                self._hd_edit.setText(str(data.get("hd", "")))
                base = data.get("base")
                if isinstance(base, dict):
                    self._base = base
                break
        self._loading = False
        # Re-apply the progression against the recorded base (no-op for manual
        # entries) and refresh the read-only summary for the current level.
        self._apply_progression()
