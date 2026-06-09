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


class TestHitPoints:
    def test_default_character_has_zero_hp(self) -> None:
        assert compute_derived_stats(Character()).hit_points == 0

    def test_hp_from_class_hit_dice_and_con(self) -> None:
        char = _character(CON=14)
        char.classes = [("Fighter", 3)]
        stats = compute_derived_stats(char, hit_dice={"Fighter": 10})
        # (10+2) + (6+2) + (6+2) = 28.
        assert stats.hit_points == 28

    def test_manual_override_replaces_computed_hp(self) -> None:
        char = _character(CON=14)
        char.classes = [("Fighter", 3)]
        stats = compute_derived_stats(char, hit_dice={"Fighter": 10}, hp_override=99)
        assert stats.hit_points == 99

    def test_bonus_hp_is_added(self) -> None:
        char = Character()
        char.classes = [("Fighter", 1)]
        stats = compute_derived_stats(char, hit_dice={"Fighter": 10}, bonus_hp=3)
        assert stats.hit_points == 13


class TestEffectiveCharacterLevel:
    def test_ecl_defaults_to_total_level(self) -> None:
        char = Character()
        char.classes = [("Fighter", 5)]
        stats = compute_derived_stats(char)
        assert stats.total_level == 5
        assert stats.ecl == 5

    def test_ecl_includes_level_adjustment(self) -> None:
        char = Character()
        char.classes = [("Fighter", 5)]
        stats = compute_derived_stats(char, level_adjustment=2)
        assert stats.total_level == 5
        assert stats.ecl == 7


class TestArmorClassAggregation:
    def test_typed_bonuses_are_aggregated(self) -> None:
        char = _character(DEX=14)
        stats = compute_derived_stats(
            char,
            ac_bonuses=[("armor", 8), ("shield", 2), ("natural", 1)],
        )
        # 10 + 2 (Dex) + 8 + 2 + 1 = 23.
        assert stats.armor_class == 23
        # Touch ignores armor/shield/natural: 10 + 2 = 12.
        assert stats.touch_ac == 12

    def test_max_dex_caps_dex_for_ac_only(self) -> None:
        char = _character(DEX=18)
        stats = compute_derived_stats(char, ac_bonuses=[("armor", 4)], max_dex=1)
        # AC Dex capped at 1: 10 + 1 + 4 = 15.
        assert stats.armor_class == 15
        # Ranged attack still uses the full +4 Dex modifier.
        assert stats.ranged_attack == 4
        assert stats.initiative == 4
