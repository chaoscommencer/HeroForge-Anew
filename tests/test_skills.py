"""Tests for heroforge.logic.skills.

Reference: PHB Chapter 4.
"""

from __future__ import annotations

from heroforge.logic.skills import (
    STANDARD_SKILL_SYNERGIES,
    cross_class_rank_cost,
    max_ranks,
    qualifying_synergy_skills,
    skill_modifier,
    skill_points_per_level,
    skill_points_spent,
    skill_synergy_bonus,
    total_skill_points,
)


class TestMaxRanks:
    def test_class_skill_level_1(self) -> None:
        assert max_ranks(1, is_class_skill=True) == 4.0

    def test_class_skill_level_10(self) -> None:
        assert max_ranks(10, is_class_skill=True) == 13.0

    def test_cross_class_level_1(self) -> None:
        assert max_ranks(1, is_class_skill=False) == 2.0

    def test_cross_class_level_10(self) -> None:
        assert max_ranks(10, is_class_skill=False) == 6.5


class TestSkillModifier:
    def test_class_skill_with_ranks(self) -> None:
        # 4 ranks, +2 ability: 4+2 = 6
        assert skill_modifier(4.0, 2, is_class_skill=True) == 6

    def test_cross_class_skill(self) -> None:
        # 2 ranks, +1 ability, not class skill: 2+1 = 3
        assert skill_modifier(2.0, 1, is_class_skill=False) == 3

    def test_no_ranks_class_skill_no_bonus(self) -> None:
        # 0 ranks, +3 ability
        assert skill_modifier(0.0, 3, is_class_skill=True) == 3

    def test_with_misc(self) -> None:
        assert skill_modifier(4.0, 2, is_class_skill=True, misc=2) == 8

    def test_negative_ability(self) -> None:
        assert skill_modifier(2.0, -1, is_class_skill=True) == 1  # 2-1


class TestCrossClassRankCost:
    def test_always_two(self) -> None:
        assert cross_class_rank_cost() == 2


class TestSkillSynergyBonus:
    def test_single_synergy(self) -> None:
        qualifying = ["Tumble"]
        synergies = [("Tumble", "Balance")]
        result = skill_synergy_bonus(qualifying, synergies)
        assert result == {"Balance": 2}

    def test_no_qualifying(self) -> None:
        qualifying: list[str] = []
        synergies = [("Tumble", "Balance")]
        result = skill_synergy_bonus(qualifying, synergies)
        assert result == {}

    def test_multiple_synergies_same_target(self) -> None:
        qualifying = ["Tumble", "Perform"]
        synergies = [("Tumble", "Balance"), ("Perform", "Balance")]
        result = skill_synergy_bonus(qualifying, synergies)
        assert result["Balance"] == 4

    def test_multiple_targets(self) -> None:
        qualifying = ["Spellcraft", "Knowledge (Arcana)"]
        synergies = [
            ("Spellcraft", "Use Magic Device"),
            ("Knowledge (Arcana)", "Spellcraft"),
        ]
        result = skill_synergy_bonus(qualifying, synergies)
        assert "Use Magic Device" in result
        assert "Spellcraft" in result


class TestSkillPointsPerLevel:
    def test_first_level_quadrupled(self) -> None:
        # 4 base, +2 INT → 6 per level, ×4 at first = 24
        assert skill_points_per_level(4, 2, is_first_level=True) == 24

    def test_normal_level(self) -> None:
        assert skill_points_per_level(4, 2, is_first_level=False) == 6

    def test_human_bonus(self) -> None:
        assert skill_points_per_level(4, 0, is_first_level=False, is_human=True) == 5

    def test_minimum_one(self) -> None:
        # base=2, INT mod=-3 → would be -1, clamped to 1
        assert skill_points_per_level(2, -3, is_first_level=False) == 1

    def test_minimum_one_quadrupled_at_first(self) -> None:
        assert skill_points_per_level(2, -5, is_first_level=True) == 4

    def test_human_first_level(self) -> None:
        # 2 base, 0 INT → 2+1=3, ×4=12
        assert skill_points_per_level(2, 0, is_first_level=True, is_human=True) == 12


class TestQualifyingSynergySkills:
    def test_threshold_is_five_ranks(self) -> None:
        ranks = {"Tumble": 5.0, "Jump": 4.5, "Bluff": 6.0}
        assert qualifying_synergy_skills(ranks) == ["Tumble", "Bluff"]

    def test_none_qualify(self) -> None:
        assert qualifying_synergy_skills({"Tumble": 4.0}) == []

    def test_empty_input(self) -> None:
        assert qualifying_synergy_skills({}) == []


class TestStandardSynergyTable:
    def test_unconditional_pairs_apply_with_five_ranks(self) -> None:
        # 5 ranks of Tumble grants +2 Balance and +2 Jump (PHB p65).
        bonuses = skill_synergy_bonus(
            qualifying_synergy_skills({"Tumble": 5.0}),
            list(STANDARD_SKILL_SYNERGIES),
        )
        assert bonuses["Balance"] == 2
        assert bonuses["Jump"] == 2

    def test_table_pairs_are_unique(self) -> None:
        assert len(STANDARD_SKILL_SYNERGIES) == len(set(STANDARD_SKILL_SYNERGIES))


class TestSkillPointsSpent:
    def test_class_skill_costs_one_per_rank(self) -> None:
        assert skill_points_spent({"Climb": 4.0}, {"Climb"}) == 4.0

    def test_cross_class_costs_two_per_rank(self) -> None:
        assert skill_points_spent({"Climb": 3.0}, set()) == 6.0

    def test_cross_class_half_rank(self) -> None:
        # 2.5 cross-class ranks cost 5 points.
        assert skill_points_spent({"Hide": 2.5}, set()) == 5.0

    def test_mixed_allocation(self) -> None:
        ranks = {"Climb": 4.0, "Hide": 2.0}
        # Climb is a class skill (4), Hide cross-class (2 × 2 = 4).
        assert skill_points_spent(ranks, {"Climb"}) == 8.0

    def test_no_ranks(self) -> None:
        assert skill_points_spent({}, {"Climb"}) == 0.0


class TestTotalSkillPoints:
    def test_single_class_first_level_quadrupled(self) -> None:
        # Rogue (8) with +1 INT → 9/level; level 1 quadrupled = 36.
        assert total_skill_points([("Rogue", 1)], {"Rogue": 8}, int_mod=1) == 36

    def test_single_class_multiple_levels(self) -> None:
        # Level 1 = 36, levels 2-3 = 9 each → 54.
        assert total_skill_points([("Rogue", 3)], {"Rogue": 8}, int_mod=1) == 54

    def test_multiclass_quadruples_only_first_character_level(self) -> None:
        # Fighter first (2 base, 0 INT) → L1 = 8, then Wizard 1 level = 2 → 10.
        total = total_skill_points(
            [("Fighter", 1), ("Wizard", 1)],
            {"Fighter": 2, "Wizard": 2},
            int_mod=0,
        )
        assert total == 10

    def test_human_bonus_per_level(self) -> None:
        # Fighter (2) +0 INT, human (+1) → 3/level; L1 ×4 = 12.
        assert (
            total_skill_points([("Fighter", 1)], {"Fighter": 2}, 0, is_human=True) == 12
        )

    def test_missing_class_uses_default_base(self) -> None:
        # Unknown class falls back to the PHB minimum of 2 points/level.
        assert total_skill_points([("Homebrew", 1)], {}, int_mod=0) == 8

    def test_no_classes(self) -> None:
        assert total_skill_points([], {}, int_mod=2) == 0
