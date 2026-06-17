"""Tests for heroforge.logic.combat.

Reference: PHB Chapter 8.
"""

from __future__ import annotations

from heroforge.logic.combat import (
    aggregate_ac_bonuses,
    aggregate_armor_class,
    armor_class,
    base_attack_bonus,
    carrying_capacity,
    damage_bonus,
    flat_footed_ac,
    format_attack_line,
    grapple_modifier,
    initiative,
    iterative_attack_count,
    iterative_attacks,
    melee_attack,
    off_hand_attacks,
    ranged_attack,
    touch_ac,
    two_weapon_penalties,
    weapon_base_dice,
    weapon_damage,
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


class TestAggregateAcBonuses:
    def test_same_type_bonuses_do_not_stack(self) -> None:
        # Two armor bonuses: only the larger applies (PHB p150).
        assert aggregate_ac_bonuses([("armor", 4), ("armor", 8)]) == 8

    def test_dodge_bonuses_stack(self) -> None:
        assert aggregate_ac_bonuses([("dodge", 1), ("dodge", 1)]) == 2

    def test_untyped_and_circumstance_stack(self) -> None:
        assert aggregate_ac_bonuses([("", 1), ("untyped", 2), ("circumstance", 3)]) == 6

    def test_different_types_sum(self) -> None:
        bonuses = [("armor", 8), ("shield", 2), ("natural", 1), ("deflection", 1)]
        assert aggregate_ac_bonuses(bonuses) == 12

    def test_penalties_always_stack(self) -> None:
        # Two armor penalties stack even though same-type bonuses do not.
        assert aggregate_ac_bonuses([("armor", -2), ("armor", -1)]) == -3

    def test_exclude_types_dropped(self) -> None:
        bonuses = [("armor", 8), ("deflection", 1)]
        assert aggregate_ac_bonuses(bonuses, exclude_types={"armor"}) == 1


class TestAggregateArmorClass:
    def test_baseline_is_ten(self) -> None:
        result = aggregate_armor_class(0)
        assert (result.total, result.touch, result.flat_footed) == (10, 10, 10)

    def test_full_aggregation(self) -> None:
        # +8 armor, +2 shield, +1 natural, +1 deflection, +1 dodge, +3 Dex.
        bonuses = [
            ("armor", 8),
            ("shield", 2),
            ("natural", 1),
            ("deflection", 1),
            ("dodge", 1),
        ]
        result = aggregate_armor_class(3, bonuses)
        # Total: 10 + 3 + 8 + 2 + 1 + 1 + 1 = 26.
        assert result.total == 26
        # Touch ignores armor/shield/natural: 10 + 3 + 1 + 1 = 15.
        assert result.touch == 15
        # Flat-footed loses Dex bonus and dodge: 10 + 8 + 2 + 1 + 1 = 22.
        assert result.flat_footed == 22

    def test_max_dex_caps_dexterity(self) -> None:
        result = aggregate_armor_class(5, [("armor", 4)], max_dex=2)
        # Dex capped at +2: 10 + 2 + 4 = 16.
        assert result.total == 16
        assert result.touch == 12

    def test_size_modifier_applied(self) -> None:
        result = aggregate_armor_class(0, size="Small")
        assert result.total == 11
        assert result.touch == 11

    def test_flat_footed_keeps_dex_penalty(self) -> None:
        # A negative Dex modifier still applies when flat-footed.
        result = aggregate_armor_class(-1)
        assert result.flat_footed == 9


class TestIterativeAttacks:
    def test_count_low_bab(self) -> None:
        assert iterative_attack_count(0) == 1
        assert iterative_attack_count(1) == 1
        assert iterative_attack_count(5) == 1

    def test_count_thresholds(self) -> None:
        assert iterative_attack_count(6) == 2
        assert iterative_attack_count(11) == 3
        assert iterative_attack_count(16) == 4
        assert iterative_attack_count(20) == 4

    def test_progression_single_attack(self) -> None:
        assert iterative_attacks(7, 5) == [7]

    def test_progression_two_attacks(self) -> None:
        # BAB +6, +2 STR -> first attack +8, second at -5 = +3.
        assert iterative_attacks(8, 6) == [8, 3]

    def test_progression_four_attacks(self) -> None:
        assert iterative_attacks(16, 16) == [16, 11, 6, 1]

    def test_progression_handles_zero_bab(self) -> None:
        assert iterative_attacks(0, 0) == [0]


class TestTwoWeaponPenalties:
    def test_normal(self) -> None:
        penalties = two_weapon_penalties()
        assert (penalties.primary, penalties.off_hand) == (-6, -10)

    def test_light_off_hand(self) -> None:
        penalties = two_weapon_penalties(off_hand_light=True)
        assert (penalties.primary, penalties.off_hand) == (-4, -8)

    def test_feat_normal_off_hand(self) -> None:
        penalties = two_weapon_penalties(has_two_weapon_fighting=True)
        assert (penalties.primary, penalties.off_hand) == (-4, -4)

    def test_feat_light_off_hand(self) -> None:
        penalties = two_weapon_penalties(
            off_hand_light=True, has_two_weapon_fighting=True
        )
        assert (penalties.primary, penalties.off_hand) == (-2, -2)


class TestOffHandAttacks:
    def test_single_off_hand_attack(self) -> None:
        assert off_hand_attacks(6) == [6]

    def test_improved_two_weapon_fighting(self) -> None:
        assert off_hand_attacks(6, improved=True) == [6, 1]

    def test_greater_two_weapon_fighting(self) -> None:
        assert off_hand_attacks(11, greater=True) == [11, 6, 1]


class TestWeaponDamage:
    def test_base_dice_extraction(self) -> None:
        assert weapon_base_dice("1d8") == "1d8"
        assert weapon_base_dice("1d8+3") == "1d8"
        assert weapon_base_dice("2 D 6") == "2d6"

    def test_positive_modifier(self) -> None:
        assert weapon_damage("1d8", 3) == "1d8+3"

    def test_negative_modifier(self) -> None:
        assert weapon_damage("1d8", -1) == "1d8-1"

    def test_zero_modifier(self) -> None:
        assert weapon_damage("1d8", 0) == "1d8"

    def test_recombines_existing_modifier(self) -> None:
        # An already-modified string is normalised back to dice + new bonus.
        assert weapon_damage("1d8+2", 4) == "1d8+4"

    def test_two_handed_str_damage(self) -> None:
        # 1.5x STR damage applied via damage_bonus then formatted.
        assert weapon_damage("2d6", damage_bonus(4, two_handed=True)) == "2d6+6"


class TestFormatAttackLine:
    def test_positive_chain(self) -> None:
        assert format_attack_line([11, 6, 1]) == "+11/+6/+1"

    def test_includes_negative(self) -> None:
        assert format_attack_line([2, -3]) == "+2/-3"

    def test_single(self) -> None:
        assert format_attack_line([0]) == "+0"
