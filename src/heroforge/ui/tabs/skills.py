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
from heroforge.logic.skills import skill_modifier

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

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
        self._build_ui()
        if model:
            model.character_reset.connect(self._reset)
            model.ability_score_changed.connect(self._on_ability_score_changed)
            model.character_loaded.connect(lambda _id: self._refresh_familiar_bonuses())
            model.derived_stats_changed.connect(self._refresh_familiar_bonuses)
            self._update_ability_mods()
            self._refresh_familiar_bonuses()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Points tracker
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

    def _recalculate(self) -> None:
        for row in range(self._table.rowCount()):
            class_item = self._table.item(row, 2)
            is_class = (
                class_item is not None
                and class_item.checkState() == Qt.CheckState.Checked
            )
            rank_widget = self._table.cellWidget(row, 3)
            ranks = rank_widget.value() if rank_widget else 0.0
            ability_item = self._table.item(row, 4)
            ability_mod = int(ability_item.text()) if ability_item else 0
            misc_widget = self._table.cellWidget(row, 5)
            misc = misc_widget.value() if misc_widget else 0
            name_item = self._table.item(row, 0)
            familiar = (
                self._familiar_skill_bonuses.get(name_item.text(), 0)
                if name_item
                else 0
            )
            total = skill_modifier(ranks, ability_mod, is_class, misc + familiar)
            total_item = self._table.item(row, 6)
            if total_item:
                total_item.setText(str(total))
                total_item.setToolTip(
                    f"Includes +{familiar} granted by your familiar (Alertness-equivalent via Natural Link)."
                    if familiar
                    else ""
                )

    def _reset(self) -> None:
        for spin in self._rank_spinboxes:
            spin.setValue(0.0)
        self._update_ability_mods()
        self._refresh_familiar_bonuses()
