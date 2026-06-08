"""Stats & Character Details tab for HeroForge-Anew.

Provides fields for character identity and the six core ability scores.
Reference: PHB p8 (ability scores), PHB p2 (character sheet overview).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.ability_scores import ability_modifier
from heroforge.logic.experience import xp_for_level

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Ability display order
_ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
_ABILITY_NAMES = {
    "STR": "Strength",
    "DEX": "Dexterity",
    "CON": "Constitution",
    "INT": "Intelligence",
    "WIS": "Wisdom",
    "CHA": "Charisma",
}

# Standard alignment options
_ALIGNMENTS = [
    "Lawful Good",
    "Neutral Good",
    "Chaotic Good",
    "Lawful Neutral",
    "True Neutral",
    "Chaotic Neutral",
    "Lawful Evil",
    "Neutral Evil",
    "Chaotic Evil",
]


class StatsAndCharacterDetailsTab(QWidget):
    """Character identity fields plus ability scores."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._ability_spinboxes: dict[str, QSpinBox] = {}
        self._modifier_labels: dict[str, QLabel] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)
            model.ability_score_changed.connect(self._on_ability_score_changed)
            model.derived_stats_changed.connect(self._refresh_derived)
            self._refresh_derived()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        inner_layout.addWidget(self._build_identity_group())
        inner_layout.addWidget(self._build_ability_group())
        inner_layout.addWidget(self._build_combat_group())
        inner_layout.addWidget(self._build_derived_group())
        inner_layout.addStretch()

        scroll.setWidget(inner)
        main_layout.addWidget(scroll)

    def _build_identity_group(self) -> QGroupBox:
        box = QGroupBox("Character Identity")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self._name_edit = QLineEdit()
        self._player_edit = QLineEdit()
        self._campaign_edit = QLineEdit()
        self._alignment_edit = QLineEdit()
        self._deity_edit = QLineEdit()
        self._homeland_edit = QLineEdit()
        self._race_edit = QLineEdit()
        self._gender_edit = QLineEdit()
        self._age_spin = QSpinBox()
        self._age_spin.setRange(0, 9999)
        self._height_edit = QLineEdit()
        self._weight_edit = QLineEdit()
        self._eyes_edit = QLineEdit()
        self._hair_edit = QLineEdit()
        self._skin_edit = QLineEdit()

        form.addRow("Name:", self._name_edit)
        form.addRow("Player:", self._player_edit)
        form.addRow("Campaign:", self._campaign_edit)
        form.addRow("Alignment:", self._alignment_edit)
        form.addRow("Deity:", self._deity_edit)
        form.addRow("Homeland:", self._homeland_edit)
        form.addRow("Race:", self._race_edit)
        form.addRow("Gender:", self._gender_edit)
        form.addRow("Age:", self._age_spin)
        form.addRow("Height:", self._height_edit)
        form.addRow("Weight:", self._weight_edit)
        form.addRow("Eyes:", self._eyes_edit)
        form.addRow("Hair:", self._hair_edit)
        form.addRow("Skin:", self._skin_edit)
        return box

    def _build_ability_group(self) -> QGroupBox:
        box = QGroupBox("Ability Scores")
        grid_layout = QHBoxLayout(box)

        for ability in _ABILITIES:
            col = QVBoxLayout()
            label = QLabel(
                f"<b>{ability}</b><br/><small>{_ABILITY_NAMES[ability]}</small>"
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            spinbox = QSpinBox()
            spinbox.setRange(1, 100)
            spinbox.setValue(10)
            spinbox.setFixedWidth(60)
            spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

            mod_label = QLabel("+0")
            mod_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mod_label.setObjectName("modifier")

            self._ability_spinboxes[ability] = spinbox
            self._modifier_labels[ability] = mod_label

            spinbox.valueChanged.connect(
                lambda val, ab=ability: self._on_spin_changed(ab, val)
            )

            col.addWidget(label)
            col.addWidget(spinbox)
            col.addWidget(mod_label)
            grid_layout.addLayout(col)

        return box

    def _build_combat_group(self) -> QGroupBox:
        box = QGroupBox("Quick Stats")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._hp_spin = QSpinBox()
        self._hp_spin.setRange(0, 9999)
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(0, 999)
        self._speed_spin.setValue(30)
        self._speed_spin.setSuffix(" ft.")
        self._init_label = QLabel("+0")
        self._xp_spin = QSpinBox()
        self._xp_spin.setRange(0, 10_000_000)
        self._xp_spin.setSingleStep(100)
        self._next_level_label = QLabel("1000")

        form.addRow("Hit Points:", self._hp_spin)
        form.addRow("Base Speed:", self._speed_spin)
        form.addRow("Initiative Mod:", self._init_label)
        form.addRow("Experience:", self._xp_spin)
        form.addRow("XP for Next Level:", self._next_level_label)

        self._xp_spin.valueChanged.connect(self._update_next_level)
        return box

    def _build_derived_group(self) -> QGroupBox:
        box = QGroupBox("Derived Combat & Saves")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._derived_labels: dict[str, QLabel] = {}
        rows = [
            ("bab", "Base Attack Bonus:"),
            ("melee", "Melee Attack:"),
            ("ranged", "Ranged Attack:"),
            ("grapple", "Grapple:"),
            ("ac", "Armor Class:"),
            ("touch", "Touch AC:"),
            ("flat", "Flat-Footed AC:"),
            ("fort", "Fortitude:"),
            ("ref", "Reflex:"),
            ("will", "Will:"),
            ("carry", "Carrying Capacity (L/M/H):"),
        ]
        for key, label in rows:
            value_label = QLabel("—")
            self._derived_labels[key] = value_label
            form.addRow(label, value_label)
        return box

    # ------------------------------------------------------------------
    # Derived-stat rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _signed(value: int) -> str:
        return f"+{value}" if value >= 0 else str(value)

    def _refresh_derived(self) -> None:
        """Recompute and display the derived combat/save readouts."""
        if not self._model:
            return
        stats = self._model.derived_stats()
        self._init_label.setText(self._signed(stats.initiative))
        self._derived_labels["bab"].setText(self._signed(stats.base_attack_bonus))
        self._derived_labels["melee"].setText(self._signed(stats.melee_attack))
        self._derived_labels["ranged"].setText(self._signed(stats.ranged_attack))
        self._derived_labels["grapple"].setText(self._signed(stats.grapple))
        self._derived_labels["ac"].setText(str(stats.armor_class))
        self._derived_labels["touch"].setText(str(stats.touch_ac))
        self._derived_labels["flat"].setText(str(stats.flat_footed_ac))
        self._derived_labels["fort"].setText(self._signed(stats.fortitude))
        self._derived_labels["ref"].setText(self._signed(stats.reflex))
        self._derived_labels["will"].setText(self._signed(stats.will))
        light, medium, heavy = stats.carrying_capacity
        self._derived_labels["carry"].setText(f"{light} / {medium} / {heavy} lb.")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_spin_changed(self, ability: str, value: int) -> None:
        mod = ability_modifier(value)
        sign = "+" if mod >= 0 else ""
        self._modifier_labels[ability].setText(f"{sign}{mod}")
        if self._model:
            self._model.ability_score_changed.emit(ability, value)

    def _on_ability_score_changed(self, ability: str, value: int) -> None:
        if ability in self._ability_spinboxes:
            self._ability_spinboxes[ability].blockSignals(True)
            self._ability_spinboxes[ability].setValue(value)
            self._ability_spinboxes[ability].blockSignals(False)
            mod = ability_modifier(value)
            sign = "+" if mod >= 0 else ""
            self._modifier_labels[ability].setText(f"{sign}{mod}")

    def _update_next_level(self, xp: int) -> None:
        from heroforge.logic.experience import level_for_xp

        current_lvl = level_for_xp(xp)
        next_xp = xp_for_level(current_lvl + 1)
        self._next_level_label.setText(f"{next_xp:,}")

    def _reset(self) -> None:
        self._name_edit.clear()
        self._player_edit.clear()
        self._campaign_edit.clear()
        self._alignment_edit.clear()
        self._deity_edit.clear()
        self._homeland_edit.clear()
        self._race_edit.clear()
        self._gender_edit.clear()
        self._age_spin.setValue(0)
        self._height_edit.clear()
        self._weight_edit.clear()
        self._eyes_edit.clear()
        self._hair_edit.clear()
        self._skin_edit.clear()
        self._xp_spin.setValue(0)
        for ab in _ABILITIES:
            self._ability_spinboxes[ab].setValue(10)
