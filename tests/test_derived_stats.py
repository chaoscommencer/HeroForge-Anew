"""Tests for the aggregated derived-stat layer (heroforge.logic.derived_stats)."""

from __future__ import annotations

from heroforge.logic.derived_stats import (
    ClassProgression,
    compute_derived_stats,
)
from heroforge.models.character import Character


def _character(**scores: int) -> Character:
    char = Character()
    char.ability_scores.update(scores)
    return char


class TestAbilityDrivenValues:
    def test_defaults_are_all_zero_modifiers(self) -> None:
        stats = compute_derived_stats(Character())
        assert stats.base_attack_bonus == 0
        assert stats.melee_attack == 0
        assert stats.ranged_attack == 0
        assert stats.grapple == 0
        assert stats.initiative == 0
        assert stats.fortitude == 0
        assert stats.reflex == 0
        assert stats.will == 0
        assert stats.armor_class == 10

    def test_strength_drives_melee_grapple_and_carry(self) -> None:
        stats = compute_derived_stats(_character(STR=18))
        # +4 STR modifier flows into melee attack and grapple.
        assert stats.melee_attack == 4
        assert stats.grapple == 4
        assert stats.carrying_capacity == (100, 200, 300)

    def test_dexterity_drives_ranged_initiative_ac_and_reflex(self) -> None:
        stats = compute_derived_stats(_character(DEX=16))
        assert stats.ranged_attack == 3
        assert stats.initiative == 3
        assert stats.armor_class == 13
        assert stats.touch_ac == 13
        assert stats.reflex == 3
        # Flat-footed AC ignores Dex.
        assert stats.flat_footed_ac == 10

    def test_constitution_drives_fortitude(self) -> None:
        stats = compute_derived_stats(_character(CON=14))
        assert stats.fortitude == 2

    def test_wisdom_drives_will(self) -> None:
        stats = compute_derived_stats(_character(WIS=12))
        assert stats.will == 1


class TestClassProgressions:
    def test_fighter_bab_and_saves(self) -> None:
        char = _character(CON=14)
        char.classes = [("Fighter", 5)]
        progressions = {"Fighter": ClassProgression("Fighter", bab="fast", fort="good")}
        stats = compute_derived_stats(char, progressions)
        assert stats.base_attack_bonus == 5
        # Good Fortitude at level 5: 2 + 5 // 2 = 4, plus +2 Con.
        assert stats.fortitude == 6
        # Melee adds BAB to the Strength modifier.
        assert stats.melee_attack == 5

    def test_unknown_class_uses_library_defaults(self) -> None:
        char = Character()
        char.classes = [("Homebrew", 8)]
        stats = compute_derived_stats(char)
        # Medium BAB default: 8 * 3 // 4 = 6.
        assert stats.base_attack_bonus == 6
        # Poor save default: 8 // 3 = 2.
        assert stats.fortitude == 2

    def test_multiclass_bab_stacks(self) -> None:
        char = Character()
        char.classes = [("Fighter", 2), ("Wizard", 5)]
        progressions = {
            "Fighter": ClassProgression("Fighter", bab="fast"),
            "Wizard": ClassProgression("Wizard", bab="slow"),
        }
        stats = compute_derived_stats(char, progressions)
        # Fighter fast (2) + Wizard slow (5 // 2 = 2) = 4.
        assert stats.base_attack_bonus == 4


class TestRaceTemplateAdjustments:
    def test_ability_adjustments_applied_to_scores_and_mods(self) -> None:
        char = _character(STR=10, CON=14)
        stats = compute_derived_stats(
            char,
            ability_adjustments={"STR": 8, "CON": 2},
        )
        assert stats.effective_ability_scores["STR"] == 18
        assert stats.effective_ability_scores["CON"] == 16
        # +4 STR modifier now drives melee and grapple.
        assert stats.melee_attack == 4
        assert stats.grapple == 4
        # +3 CON modifier drives Fortitude.
        assert stats.fortitude == 3
        # Carrying capacity reflects the adjusted Strength of 18.
        assert stats.carrying_capacity == (100, 200, 300)

    def test_penalty_floored_at_one(self) -> None:
        char = _character(STR=8)
        stats = compute_derived_stats(char, ability_adjustments={"STR": -20})
        assert stats.effective_ability_scores["STR"] == 1

    def test_level_adjustment_drives_ecl(self) -> None:
        char = Character()
        char.classes = [("Fighter", 5)]
        stats = compute_derived_stats(char, level_adjustment=3)
        assert stats.level_adjustment == 3
        assert stats.effective_character_level == 8

    def test_size_flows_through(self) -> None:
        stats = compute_derived_stats(Character(), size="Small")
        assert stats.size == "Small"
        # Small creatures get +1 size bonus to AC and attack.
        assert stats.armor_class == 11

    def test_defaults_are_neutral(self) -> None:
        stats = compute_derived_stats(_character(STR=12))
        assert stats.size == "Medium"
        assert stats.level_adjustment == 0
        assert stats.effective_character_level == 0
        assert stats.effective_ability_scores["STR"] == 12
