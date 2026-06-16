"""Tests for heroforge.logic.combat.

Reference: PHB Chapter 8.
"""

from __future__ import annotations

from heroforge.logic.combat import (
    armor_class,
    base_attack_bonus,
    carrying_capacity,
    damage_bonus,
    flat_footed_ac,
    grapple_modifier,
    initiative,
    melee_attack,
    ranged_attack,
    touch_ac,
)


class TestBaseAttackBonus:
    def test_fast_progression(self) -> None:
        # Fighter 5 → BAB +5
        assert base_attack_bonus({"Fighter": 5}, {"Fighter": "fast"}) == 5

    def test_medium_progression(self) -> None:
        # Cleric 4 → 4*3//4 = 3
        assert base_attack_bonus({"Cleric": 4}, {"Cleric": "medium"}) == 3

    def test_slow_progression(self) -> None:
        # Wizard 6 → 6//2 = 3
        assert base_attack_bonus({"Wizard": 6}, {"Wizard": "slow"}) == 3

    def test_multiclass(self) -> None:
        # Fighter 5 (fast=5) + Wizard 5 (slow=2) = 7
        class_levels = {"Fighter": 5, "Wizard": 5}
        progressions = {"Fighter": "fast", "Wizard": "slow"}
        assert base_attack_bonus(class_levels, progressions) == 7

    def test_empty_classes(self) -> None:
        assert base_attack_bonus({}, {}) == 0

    def test_medium_level_1(self) -> None:
        assert base_attack_bonus({"Cleric": 1}, {"Cleric": "medium"}) == 0


class TestArmorClass:
    def test_base_ac(self) -> None:
        assert armor_class(0) == 10

    def test_with_dex(self) -> None:
        assert armor_class(2) == 12

    def test_full_plate(self) -> None:
        # Full plate +8, no dex, medium
        assert armor_class(0, armor=8) == 18

    def test_size_modifier_small(self) -> None:
        assert armor_class(0, size="Small") == 11

    def test_size_modifier_large(self) -> None:
        assert armor_class(0, size="Large") == 9


class TestTouchAC:
    def test_base_touch(self) -> None:
        assert touch_ac(0) == 10

    def test_with_dex(self) -> None:
        assert touch_ac(3) == 13

    def test_size_fine(self) -> None:
        assert touch_ac(0, size="Fine") == 18


class TestFlatFootedAC:
    def test_base(self) -> None:
        assert flat_footed_ac() == 10

    def test_with_armor(self) -> None:
        assert flat_footed_ac(armor=5, shield=2) == 17


class TestGrappleModifier:
    def test_medium_fighter(self) -> None:
        # BAB 5, STR mod +3, Medium = 0
        assert grapple_modifier(5, 3, size="Medium") == 8

    def test_large_creature(self) -> None:
        assert grapple_modifier(3, 2, size="Large") == 9  # 3+2+4

    def test_small_creature(self) -> None:
        assert grapple_modifier(1, 1, size="Small") == -2  # 1+1-4


class TestInitiative:
    def test_dex_only(self) -> None:
        assert initiative(3) == 3

    def test_with_improved_initiative(self) -> None:
        assert initiative(2, feat_bonus=4) == 6

    def test_negative_dex(self) -> None:
        assert initiative(-2) == -2


class TestMeleeAttack:
    def test_standard(self) -> None:
        assert melee_attack(5, 2) == 7

    def test_with_size(self) -> None:
        assert melee_attack(3, 1, size="Small") == 5  # 3+1+1

    def test_with_misc(self) -> None:
        assert melee_attack(5, 2, misc=1) == 8


class TestRangedAttack:
    def test_standard(self) -> None:
        assert ranged_attack(4, 3) == 7

    def test_large_penalty(self) -> None:
        assert ranged_attack(4, 2, size="Large") == 5  # 4+2-1


class TestDamageBonus:
    def test_one_handed(self) -> None:
        assert damage_bonus(3) == 3

    def test_two_handed_positive(self) -> None:
        assert damage_bonus(4, two_handed=True) == 6  # 4*1.5 = 6

    def test_two_handed_negative(self) -> None:
        assert damage_bonus(-2, two_handed=True) == -2

    def test_off_hand_positive(self) -> None:
        assert damage_bonus(4, off_hand=True) == 2  # 4//2

    def test_off_hand_negative(self) -> None:
        assert damage_bonus(-3, off_hand=True) == -3

    def test_no_str_bonus(self) -> None:
        assert damage_bonus(0) == 0


class TestCarryingCapacity:
    def test_str_10(self) -> None:
        light, medium, heavy = carrying_capacity(10)
        assert light == 33
        assert medium == 66
        assert heavy == 100

    def test_str_1(self) -> None:
        light, medium, heavy = carrying_capacity(1)
        assert light == 3

    def test_str_18(self) -> None:
        light, medium, heavy = carrying_capacity(18)
        assert light == 100
        assert heavy == 300

    def test_str_zero_treated_as_one(self) -> None:
        assert carrying_capacity(0) == carrying_capacity(1)
