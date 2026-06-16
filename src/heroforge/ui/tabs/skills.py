"""Skills tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.ability_scores import ability_modifier
from heroforge.logic.familiar import (
    STANDARD_FAMILIAR_BONUSES,
    familiar_natural_link,
    selected_familiar_kind,
    skill_bonuses,
)
from heroforge.logic.skills import (
    STANDARD_SKILL_SYNERGIES,
    max_ranks,
    qualifying_synergy_skills,
    skill_modifier,
    skill_points_spent,
    skill_synergy_bonus,
    total_skill_points,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Equipment slots whose armor-check penalty affects skill checks (PHB p123).
_ACP_SLOTS = ("Body Armor", "Shield")

# Core skills list with key ability (PHB Chapter 4)
_SKILLS: list[tuple[str, str, bool, bool]] = [
    # (name, ability, trained_only, armor_check_penalty)
    ("Appraise", "INT", False, False),
    ("Balance", "DEX", False, True),
    ("Bluff", "CHA", False, False),
    ("Climb", "STR", False, True),
    ("Concentration", "CON", False, False),
    ("Craft", "INT", False, False),
    ("Decipher Script", "INT", True, False),
    ("Diplomacy", "CHA", False, False),
    ("Disable Device", "INT", True, False),
    ("Disguise", "CHA", False, False),
    ("Escape Artist", "DEX", False, True),
    ("Forgery", "INT", False, False),
    ("Gather Information", "CHA", False, False),
    ("Handle Animal", "CHA", True, False),
    ("Heal", "WIS", False, False),
    ("Hide", "DEX", False, True),
    ("Intimidate", "CHA", False, False),
    ("Jump", "STR", False, True),
    ("Knowledge (Arcana)", "INT", True, False),
    ("Knowledge (Dungeoneering)", "INT", True, False),
    ("Knowledge (Geography)", "INT", True, False),
    ("Knowledge (History)", "INT", True, False),
    ("Knowledge (Local)", "INT", True, False),
    ("Knowledge (Nature)", "INT", True, False),
    ("Knowledge (Nobility)", "INT", True, False),
    ("Knowledge (Planes)", "INT", True, False),
    ("Knowledge (Religion)", "INT", True, False),
    ("Listen", "WIS", False, False),
    ("Move Silently", "DEX", False, True),
    ("Open Lock", "DEX", True, False),
    ("Perform", "CHA", False, False),
    ("Profession", "WIS", True, False),
    ("Ride", "DEX", False, False),
    ("Search", "INT", False, False),
    ("Sense Motive", "WIS", False, False),
    ("Sleight of Hand", "DEX", True, True),
    ("Speak Language", "N/A", True, False),
    ("Spellcraft", "INT", True, False),
    ("Spot", "WIS", False, False),
    ("Survival", "WIS", False, False),
    ("Swim", "STR", False, True),
    ("Tumble", "DEX", True, True),
    ("Use Magic Device", "CHA", True, False),
    ("Use Rope", "DEX", False, False),
]


class SkillsTab(QWidget):
    """Skill rank allocation and modifier display."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._familiar_skill_bonuses: dict[str, int] = {}
        self._class_skills: set[str] = set()
        self._updating = False
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)
            model.ability_score_changed.connect(self._on_ability_score_changed)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.derived_stats_changed.connect(self._refresh_familiar_bonuses)
            model.class_levels_changed.connect(self._refresh_class_skills)
            self._update_ability_mods()
            self._refresh_class_skills()
            self._refresh_familiar_bonuses()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Points tracker: spent / available skill-point budget (PHB p62).
        info_row = QHBoxLayout()
        info_row.addWidget(QLabel("Skill Points Remaining:"))
        self._points_label = QLabel("0")
        info_row.addWidget(self._points_label)
        info_row.addStretch()
        layout.addLayout(info_row)

        # Skills table
        box = QGroupBox("Skills")
        box_layout = QVBoxLayout(box)

        headers = ["Skill", "Key", "Class?", "Ranks", "Ability Mod", "Misc", "Total"]
        self._table = QTableWidget(len(_SKILLS), len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._rank_spinboxes: list[QDoubleSpinBox] = []

        for row, (sname, ability, trained, acp) in enumerate(_SKILLS):
            self._table.setItem(row, 0, QTableWidgetItem(sname))
            self._table.setItem(row, 1, QTableWidgetItem(ability))
            class_item = QTableWidgetItem("")
            class_item.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row, 2, class_item)

            rank_spin = QDoubleSpinBox()
            rank_spin.setRange(0, 50)
            rank_spin.setSingleStep(0.5)
            rank_spin.setDecimals(1)
            self._table.setCellWidget(row, 3, rank_spin)
            self._rank_spinboxes.append(rank_spin)

            ability_mod_item = QTableWidgetItem("0")
            ability_mod_item.setFlags(
                ability_mod_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            self._table.setItem(row, 4, ability_mod_item)

            misc_spin = QSpinBox()
            misc_spin.setRange(-20, 50)
            self._table.setCellWidget(row, 5, misc_spin)

            total_item = QTableWidgetItem("0")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 6, total_item)

            rank_spin.valueChanged.connect(
                lambda value, r=row: self._on_rank_changed(r, value)
            )
            misc_spin.valueChanged.connect(lambda _: self._recalculate())

        box_layout.addWidget(self._table)
        layout.addWidget(box)

        # Toggling a "Class?" checkbox changes max ranks, point cost and totals.
        self._table.itemChanged.connect(self._on_item_changed)

    def _on_rank_changed(self, row: int, value: float) -> None:
        """Announce a skill-rank change so the model and dependent tabs update.

        The rank is broadcast via :attr:`CharacterModel.skill_ranks_changed`
        (``docs/conversion-plan.md`` §8.4); the model records it in the active
        character and re-emits ``derived_stats_changed`` for tabs (e.g. Feats)
        whose displays depend on skill ranks.
        """
        self._recalculate()
        if self._model is not None and 0 <= row < len(_SKILLS):
            self._model.skill_ranks_changed.emit(_SKILLS[row][0], float(value))

    def _on_ability_score_changed(self, ability: str, value: int) -> None:
        """Update each skill's ability modifier when a score changes (§8.6)."""
        mod = ability_modifier(value)
        for row, (_sname, skill_ability, _trained, _acp) in enumerate(_SKILLS):
            if skill_ability == ability:
                item = self._table.item(row, 4)
                if item:
                    item.setText(str(mod))
        self._recalculate()

    def _update_ability_mods(self) -> None:
        """Seed each skill's ability-modifier column from the active character."""
        scores = self._model.character.ability_scores if self._model else {}
        for row, (_sname, skill_ability, _trained, _acp) in enumerate(_SKILLS):
            mod = ability_modifier(int(scores.get(skill_ability, 10)))
            item = self._table.item(row, 4)
            if item:
                item.setText(str(mod))
        self._recalculate()

    def _refresh_familiar_bonuses(self) -> None:
        """Recompute the automatic skill bonuses granted by a familiar.

        Combines a standard familiar's creature-specific skill bonus (e.g. a
        Bat's +3 Listen) with the universal Alertness +2 to Spot & Listen, and
        doubles them when Natural Link is active.  The seeded ``familiar_bonuses``
        data is used when available, falling back to the canonical constant so
        the bonuses still apply offline.
        """
        self._familiar_skill_bonuses = {}
        if self._model is not None:
            companions = self._model.character.companions
            kind = selected_familiar_kind(companions)
            if kind:
                records = self._model.game_data().get_familiar_bonus_records() or list(
                    STANDARD_FAMILIAR_BONUSES
                )
                self._familiar_skill_bonuses = skill_bonuses(
                    kind,
                    records,
                    natural_link=familiar_natural_link(companions),
                )
        self._recalculate()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Recalculate when a user toggles a skill's "Class?" checkbox.

        Programmatic updates (ability mod, total, derived class-skill flags) are
        guarded by :attr:`_updating` so only genuine user edits of column 2
        trigger a recalculation.
        """
        if self._updating or item.column() != 2:
            return
        self._recalculate()

    def _character_level(self) -> int:
        """Return the active character's total level (0 when none)."""
        if self._model is None:
            return 0
        return self._model.character.total_level

    def _is_class_skill(self, row: int) -> bool:
        class_item = self._table.item(row, 2)
        return (
            class_item is not None and class_item.checkState() == Qt.CheckState.Checked
        )

    def _refresh_class_skills(self) -> None:
        """Derive each skill's class-skill flag from the character's classes.

        A skill is a class skill if it is a class skill for *any* class the
        character has levels in (PHB p62).  The ``class_skills`` table is queried
        per class through the game-data repository.  Flags are written under the
        :attr:`_updating` guard so they do not re-enter :meth:`_on_item_changed`.
        """
        self._class_skills = set()
        if self._model is not None and self._model.game_data().available:
            repo = self._model.game_data()
            for class_name, _level in self._model.character.classes:
                self._class_skills.update(repo.class_skills(class_name))
        self._updating = True
        try:
            for row, (sname, *_rest) in enumerate(_SKILLS):
                class_item = self._table.item(row, 2)
                if class_item is None:
                    continue
                checked = sname in self._class_skills
                class_item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        finally:
            self._updating = False
        self._recalculate()

    def _armor_check_penalty(self) -> int:
        """Return the combined armor-check penalty from equipped armor/shield.

        Penalties (stored as ≤ 0 values) are looked up from the seeded ``armor``
        catalogue and the character's custom armor, then summed across the
        equipped Body Armor and Shield slots (PHB p123).  Returns ``0`` when no
        penalising armor is equipped or no game data is available.
        """
        if self._model is None:
            return 0
        penalties: dict[str, int] = {}
        for armor in self._model.game_data().list_armor():
            penalties[armor.name] = armor.check_penalty
        for entry in self._model.character.custom_armor:
            name = entry.get("name")
            if name:
                penalties[name] = int(entry.get("check_penalty", 0) or 0)
        total = 0
        for entry in self._model.character.equipment:
            if entry.get("slot") in _ACP_SLOTS:
                total += penalties.get(entry.get("item_name", ""), 0)
        return total

    def _synergy_bonuses(self) -> dict[str, int]:
        """Return the +2 synergy bonuses earned by the current rank allocation."""
        ranks_by_skill = {
            _SKILLS[row][0]: self._rank_spinboxes[row].value()
            for row in range(len(_SKILLS))
        }
        synergies: list[tuple[str, str]] = []
        if self._model is not None:
            synergies = self._model.game_data().list_skill_synergies()
        if not synergies:
            synergies = list(STANDARD_SKILL_SYNERGIES)
        return skill_synergy_bonus(qualifying_synergy_skills(ranks_by_skill), synergies)

    def _recalculate(self) -> None:
        acp = self._armor_check_penalty()
        synergy = self._synergy_bonuses()
        character_level = self._character_level()
        for row, (sname, _ability, _trained, has_acp) in enumerate(_SKILLS):
            is_class = self._is_class_skill(row)
            rank_widget = self._rank_spinboxes[row]
            self._enforce_max_ranks(rank_widget, character_level, is_class)
            ranks = rank_widget.value()
            ability_item = self._table.item(row, 4)
            ability_mod = int(ability_item.text()) if ability_item else 0
            misc_widget = self._table.cellWidget(row, 5)
            misc = misc_widget.value() if misc_widget else 0
            familiar = self._familiar_skill_bonuses.get(sname, 0)
            synergy_bonus = synergy.get(sname, 0)
            armor_penalty = acp if has_acp else 0
            total = skill_modifier(
                ranks,
                ability_mod,
                is_class,
                misc + familiar + synergy_bonus + armor_penalty,
            )
            total_item = self._table.item(row, 6)
            if total_item:
                total_item.setText(str(total))
                total_item.setToolTip(
                    self._total_tooltip(familiar, synergy_bonus, armor_penalty)
                )
        self._update_budget()

    @staticmethod
    def _enforce_max_ranks(
        rank_widget: QDoubleSpinBox | None, character_level: int, is_class: bool
    ) -> None:
        """Cap a rank spinbox at the maximum ranks allowed (PHB p62).

        The cap is only applied once the character has at least one class level;
        with no levels the generous default range is kept so the control remains
        usable before classes are chosen.
        """
        if rank_widget is None:
            return
        if character_level >= 1:
            rank_widget.setMaximum(max_ranks(character_level, is_class))
        else:
            rank_widget.setMaximum(50)

    @staticmethod
    def _total_tooltip(familiar: int, synergy: int, armor_penalty: int) -> str:
        parts: list[str] = []
        if familiar:
            parts.append(f"+{familiar} familiar")
        if synergy:
            parts.append(f"+{synergy} synergy")
        if armor_penalty:
            parts.append(f"{armor_penalty} armor check penalty")
        return "Includes " + ", ".join(parts) + "." if parts else ""

    def _update_budget(self) -> None:
        """Update the skill-point budget readout (spent vs. available)."""
        if self._model is None:
            self._points_label.setText("0")
            return
        ranks_by_skill = {
            _SKILLS[row][0]: self._rank_spinboxes[row].value()
            for row in range(len(_SKILLS))
        }
        spent = skill_points_spent(ranks_by_skill, self._class_skills)
        base_points = {
            info.name: info.skill_points_per_level
            for info in self._model.game_data().list_classes(include_prestige=True)
        }
        int_mod = ability_modifier(
            int(self._model.character.ability_scores.get("INT", 10))
        )
        is_human = self._model.character.race.strip().lower() == "human"
        available = total_skill_points(
            self._model.character.classes, base_points, int_mod, is_human
        )
        remaining = available - spent
        self._points_label.setText(f"{self._format_points(remaining)} / {available}")

    @staticmethod
    def _format_points(value: float) -> str:
        """Format a (possibly fractional) skill-point count for display."""
        return str(int(value)) if float(value).is_integer() else f"{value:g}"

    def _reset(self) -> None:
        for spin in self._rank_spinboxes:
            spin.setValue(0.0)
        self._update_ability_mods()
        self._refresh_class_skills()
        self._refresh_familiar_bonuses()

    def _sync_from_model(self) -> None:
        """Restore skill ranks from the loaded character (§8.4)."""
        saved = self._model.character.skills if self._model else {}
        for row, (sname, *_rest) in enumerate(_SKILLS):
            spin = self._rank_spinboxes[row]
            spin.blockSignals(True)
            spin.setValue(float(saved.get(sname, 0.0)))
            spin.blockSignals(False)
        self._update_ability_mods()
        self._refresh_class_skills()
        self._refresh_familiar_bonuses()
