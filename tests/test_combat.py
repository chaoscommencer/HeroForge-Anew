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
    two_weapon_feats,
    two_weapon_penalties,
    weapon_base_dice,
    weapon_damage,
    weapon_strength_damage,
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

    def test_count_capped_at_epic_bab(self) -> None:
        # Epic attack bonus (BAB above +20) grants no extra iterative attacks.
        assert iterative_attack_count(21) == 4
        assert iterative_attack_count(26) == 4
        assert iterative_attacks(25, 21) == [25, 20, 15, 10]

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


class TestTwoWeaponFeats:
    def test_no_feats(self) -> None:
        feats = two_weapon_feats(["Power Attack", "Dodge"])
        assert (feats.two_weapon_fighting, feats.improved, feats.greater) == (
            False,
            False,
            False,
        )

    def test_detects_feat_chain_case_insensitively(self) -> None:
        feats = two_weapon_feats(
            [
                "Two-Weapon Fighting",
                "improved two-weapon fighting",
                " Greater Two-Weapon Fighting ",
            ]
        )
        assert feats.two_weapon_fighting and feats.improved and feats.greater

    def test_improved_alone(self) -> None:
        feats = two_weapon_feats(["Improved Two-Weapon Fighting"])
        assert not feats.two_weapon_fighting
        assert feats.improved and not feats.greater


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

    def test_base_dice_without_dice_is_empty(self) -> None:
        assert weapon_base_dice("ref:UnarmedStrikeDamage") == ""
        assert weapon_base_dice("2") == ""
        assert weapon_base_dice("") == ""

    def test_damage_without_dice_is_unchanged(self) -> None:
        # Text with no NdM dice cannot be recombined, so it is left as-is
        # rather than gaining another modifier on every refresh.
        assert weapon_damage("ref:GrappleDamage", 4) == "ref:GrappleDamage"
        assert weapon_damage("2", 4) == "2"
        assert weapon_damage(weapon_damage("2", 4), 4) == "2"

    def test_two_handed_str_damage(self) -> None:
        # 1.5x STR damage applied via damage_bonus then formatted.
        assert weapon_damage("2d6", damage_bonus(4, two_handed=True)) == "2d6+6"


class TestWeaponStrengthDamage:
    def test_one_handed_melee_gets_full_strength(self) -> None:
        assert weapon_strength_damage(4, "O") == 4
        assert weapon_strength_damage(4, "L") == 4

    def test_two_handed_melee_gets_one_and_a_half_strength(self) -> None:
        # PHB p113: two-handed weapons add 1.5x STR bonus (round down).
        assert weapon_strength_damage(4, "T") == 6
        assert weapon_strength_damage(3, "T") == 4

    def test_two_handed_strength_penalty_is_not_multiplied(self) -> None:
        assert weapon_strength_damage(-2, "T") == -2

    def test_unknown_handedness_gets_full_strength(self) -> None:
        assert weapon_strength_damage(4, "") == 4

    def test_thrown_weapon_gets_full_strength(self) -> None:
        # PHB p134: Strength applies to thrown-weapon damage.
        assert weapon_strength_damage(4, "R", special="T", ranged=True) == 4
        assert weapon_strength_damage(-1, "R", special="U,T", ranged=True) == -1

    def test_melee_weapon_with_range_increment_gets_full_strength(self) -> None:
        # A dagger keeps its Strength bonus whether stabbed or thrown.
        assert weapon_strength_damage(4, "L", name="Dagger", ranged=True) == 4

    def test_sling_gets_full_strength(self) -> None:
        assert weapon_strength_damage(3, "R", name="Sling", ranged=True) == 3
        assert weapon_strength_damage(-2, "R", name="Sling, War", ranged=True) == -2

    def test_bow_applies_only_a_strength_penalty(self) -> None:
        # PHB p113-114: bows apply a Strength penalty but not a bonus (a
        # composite bow's mighty rating is not modelled, so it adds +0).
        assert weapon_strength_damage(4, "R", name="Longbow", ranged=True) == 0
        assert weapon_strength_damage(-2, "R", name="Longbow", ranged=True) == -2
        assert (
            weapon_strength_damage(
                -1, "R", special="M", name="Shortbow, Composite", ranged=True
            )
            == -1
        )

    def test_crossbow_and_other_projectiles_get_no_strength(self) -> None:
        assert weapon_strength_damage(4, "R", name="Crossbow, Light", ranged=True) == 0
        assert weapon_strength_damage(-2, "R", name="Crossbow, Heavy", ranged=True) == 0
        assert weapon_strength_damage(4, "R", name="Blowgun", ranged=True) == 0

    def test_unknown_ranged_weapon_gets_no_strength(self) -> None:
        assert weapon_strength_damage(4, "", name="Custom Gun", ranged=True) == 0


class TestFormatAttackLine:
    def test_positive_chain(self) -> None:
        assert format_attack_line([11, 6, 1]) == "+11/+6/+1"

    def test_includes_negative(self) -> None:
        assert format_attack_line([2, -3]) == "+2/-3"

    def test_single(self) -> None:
        assert format_attack_line([0]) == "+0"
