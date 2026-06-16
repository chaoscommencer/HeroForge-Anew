"""Stats & Character Details tab for HeroForge-Anew.

Provides fields for character identity and the six core ability scores.
Reference: PHB p8 (ability scores), PHB p2 (character sheet overview).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
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

from heroforge.logic.ability_scores import ability_modifier, point_buy_spent
from heroforge.logic.experience import xp_for_level
from heroforge.models.options import point_buy_budget

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
        self._computed_hp = 0
        self._ability_spinboxes: dict[str, QSpinBox] = {}
        self._modifier_labels: dict[str, QLabel] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.ability_score_changed.connect(self._on_ability_score_changed)
            model.derived_stats_changed.connect(self._refresh_derived)
            model.options_changed.connect(self._refresh_point_buy)
            self._connect_identity_signals()
            self._sync_from_model()
            self._refresh_derived()

    def _connect_identity_signals(self) -> None:
        """Wire identity/detail widgets so edits flow back into the model."""
        self._name_edit.textEdited.connect(self._sync_to_model)
        self._player_edit.textEdited.connect(self._sync_to_model)
        self._campaign_edit.textEdited.connect(self._sync_to_model)
        self._alignment_edit.textEdited.connect(self._sync_to_model)
        self._deity_edit.textEdited.connect(self._sync_to_model)
        self._homeland_edit.textEdited.connect(self._sync_to_model)
        self._gender_edit.textEdited.connect(self._sync_to_model)
        self._height_edit.textEdited.connect(self._sync_to_model)
        self._weight_edit.textEdited.connect(self._sync_to_model)
        self._eyes_edit.textEdited.connect(self._sync_to_model)
        self._hair_edit.textEdited.connect(self._sync_to_model)
        self._skin_edit.textEdited.connect(self._sync_to_model)
        self._age_spin.valueChanged.connect(lambda _: self._sync_to_model())
        self._xp_spin.valueChanged.connect(lambda _: self._sync_to_model())

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
        self._race_edit.setReadOnly(True)
        self._race_edit.setToolTip("Set on the Race & Templates tab.")
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
        outer = QVBoxLayout(box)
        grid_widget = QWidget()
        grid_layout = QHBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)

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

        outer.addWidget(grid_widget)

        # Point-buy summary: reflects the budget configured in the Options
        # dialog (tab 11b) so the player sees points spent against their budget.
        self._point_buy_label = QLabel()
        self._point_buy_label.setObjectName("pointBuy")
        self._point_buy_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addWidget(self._point_buy_label)
        self._refresh_point_buy()

        return box

    def _build_combat_group(self) -> QGroupBox:
        box = QGroupBox("Quick Stats")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Hit Points: auto-computed from class Hit Dice + CON by default, with an
        # opt-in manual override (mirrors the workbook's editable HP cell).
        hp_row = QHBoxLayout()
        self._hp_spin = QSpinBox()
        self._hp_spin.setRange(0, 9999)
        self._hp_auto_check = QCheckBox("Auto")
        self._hp_auto_check.setChecked(True)
        self._hp_auto_check.setToolTip(
            "Auto-calculate HP from class Hit Dice and the Constitution "
            "modifier.  Uncheck to enter a manual value."
        )
        hp_row.addWidget(self._hp_spin)
        hp_row.addWidget(self._hp_auto_check)
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(0, 999)
        self._speed_spin.setValue(30)
        self._speed_spin.setSuffix(" ft.")
        self._init_label = QLabel("+0")
        self._xp_spin = QSpinBox()
        self._xp_spin.setRange(0, 10_000_000)
        self._xp_spin.setSingleStep(100)
        self._next_level_label = QLabel("1000")

        form.addRow("Hit Points:", hp_row)
        form.addRow("Base Speed:", self._speed_spin)
        form.addRow("Initiative Mod:", self._init_label)
        form.addRow("Experience:", self._xp_spin)
        form.addRow("XP for Next Level:", self._next_level_label)

        self._xp_spin.valueChanged.connect(self._update_next_level)
        self._hp_auto_check.toggled.connect(self._on_hp_auto_toggled)
        self._hp_spin.valueChanged.connect(self._on_hp_value_changed)
        self._apply_hp_auto_state()
        return box

    def _build_derived_group(self) -> QGroupBox:
        box = QGroupBox("Derived Combat & Saves")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._derived_labels: dict[str, QLabel] = {}
        rows = [
            ("total_level", "Total Level:"),
            ("ecl", "Effective Character Level:"),
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
        self._computed_hp = stats.hit_points
        self._refresh_hp_display()
        self._init_label.setText(self._signed(stats.initiative))
        self._derived_labels["total_level"].setText(str(stats.total_level))
        self._derived_labels["ecl"].setText(str(stats.effective_character_level))
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
        # Race is owned by the Race & Templates tab; mirror it read-only here.
        self._race_edit.setText(self._model.character.race)

    # ------------------------------------------------------------------
    # Hit points (auto-calculated with optional manual override)
    # ------------------------------------------------------------------

    def _apply_hp_auto_state(self) -> None:
        """Enable/disable manual HP entry based on the Auto checkbox."""
        auto = self._hp_auto_check.isChecked()
        # In auto mode the spinbox shows the computed value read-only.
        self._hp_spin.setReadOnly(auto)
        self._hp_spin.setButtonSymbols(
            QSpinBox.ButtonSymbols.NoButtons
            if auto
            else QSpinBox.ButtonSymbols.UpDownArrows
        )

    def _refresh_hp_display(self) -> None:
        """Show the computed HP (auto) or persisted override (manual)."""
        if self._hp_auto_check.isChecked():
            value = self._computed_hp
        else:
            char = self._model.character if self._model else None
            value = char.hit_points if (char and char.hit_points is not None) else 0
        self._hp_spin.blockSignals(True)
        self._hp_spin.setValue(int(value))
        self._hp_spin.blockSignals(False)

    def _on_hp_auto_toggled(self, _checked: bool) -> None:
        self._apply_hp_auto_state()
        if self._model:
            if self._hp_auto_check.isChecked():
                self._model.character.hit_points = None
            else:
                # Seed the override with the current computed value.
                self._model.character.hit_points = int(self._computed_hp)
        self._refresh_hp_display()

    def _on_hp_value_changed(self, value: int) -> None:
        # Only manual edits matter; auto mode mirrors the computed value.
        if self._model and not self._hp_auto_check.isChecked():
            self._model.character.hit_points = int(value)

    def _refresh_point_buy(self) -> None:
        """Update the point-buy summary against the configured budget.

        The budget comes from the Options dialog (tab 11b) via the model; when
        no model is present (standalone widget) the standard 25-point default is
        shown.  Spending over budget is flagged so the player notices.
        """
        scores = {ab: spin.value() for ab, spin in self._ability_spinboxes.items()}
        spent = point_buy_spent(scores)
        if self._model is not None:
            budget = self._model.point_buy_budget()
        else:
            budget = point_buy_budget({})
        over = " — over budget!" if spent > budget else ""
        self._point_buy_label.setText(f"Point-Buy: {spent} / {budget}{over}")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_spin_changed(self, ability: str, value: int) -> None:
        mod = ability_modifier(value)
        sign = "+" if mod >= 0 else ""
        self._modifier_labels[ability].setText(f"{sign}{mod}")
        self._refresh_point_buy()
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
            self._refresh_point_buy()

    def _update_next_level(self, xp: int) -> None:
        from heroforge.logic.experience import level_for_xp

        current_lvl = level_for_xp(xp)
        next_xp = xp_for_level(current_lvl + 1)
        self._next_level_label.setText(f"{next_xp:,}")

    def _sync_to_model(self) -> None:
        """Write identity and detail fields into the active character.

        Race is intentionally excluded: it is owned by the Race & Templates
        tab and only mirrored read-only here.
        """
        if not self._model:
            return
        char = self._model.character
        char.name = self._name_edit.text()
        char.player = self._player_edit.text()
        char.campaign = self._campaign_edit.text()
        char.alignment = self._alignment_edit.text()
        char.deity = self._deity_edit.text()
        char.homeland = self._homeland_edit.text()
        char.gender = self._gender_edit.text()
        char.age = self._age_spin.value()
        char.height = self._height_edit.text()
        char.weight = self._weight_edit.text()
        char.eyes = self._eyes_edit.text()
        char.hair = self._hair_edit.text()
        char.skin = self._skin_edit.text()
        char.experience = self._xp_spin.value()

    def _sync_from_model(self) -> None:
        """Repopulate every widget from the active character (load/reset)."""
        char = self._model.character if self._model else None
        fields = {
            self._name_edit: char.name if char else "",
            self._player_edit: char.player if char else "",
            self._campaign_edit: char.campaign if char else "",
            self._alignment_edit: char.alignment if char else "",
            self._deity_edit: char.deity if char else "",
            self._homeland_edit: char.homeland if char else "",
            self._race_edit: char.race if char else "",
            self._gender_edit: char.gender if char else "",
            self._height_edit: char.height if char else "",
            self._weight_edit: char.weight if char else "",
            self._eyes_edit: char.eyes if char else "",
            self._hair_edit: char.hair if char else "",
            self._skin_edit: char.skin if char else "",
        }
        for widget, value in fields.items():
            widget.blockSignals(True)
            widget.setText(value)
            widget.blockSignals(False)
        for spin, value in (
            (self._age_spin, char.age if char else 0),
            (self._xp_spin, char.experience if char else 0),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self._update_next_level(self._xp_spin.value())
        scores = char.ability_scores if char else {}
        for ab in _ABILITIES:
            spinbox = self._ability_spinboxes[ab]
            value = int(scores.get(ab, 10))
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
            mod = ability_modifier(value)
            sign = "+" if mod >= 0 else ""
            self._modifier_labels[ab].setText(f"{sign}{mod}")
        self._refresh_point_buy()
        # Restore HP auto/override state: a stored value means manual override.
        override = char.hit_points if char else None
        self._hp_auto_check.blockSignals(True)
        self._hp_auto_check.setChecked(override is None)
        self._hp_auto_check.blockSignals(False)
        self._apply_hp_auto_state()
        self._refresh_hp_display()
