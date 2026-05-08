"""Tests for heroforge.logic.skills.

Reference: PHB Chapter 4.
"""

from __future__ import annotations

from heroforge.logic.skills import (
    cross_class_rank_cost,
    max_ranks,
    skill_modifier,
    skill_points_per_level,
    skill_synergy_bonus,
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
        # 4 ranks, +2 ability, class skill: 4+2+3 = 9
        assert skill_modifier(4.0, 2, is_class_skill=True) == 9

    def test_cross_class_skill(self) -> None:
        # 2 ranks, +1 ability, not class skill: 2+1 = 3
        assert skill_modifier(2.0, 1, is_class_skill=False) == 3

    def test_no_ranks_class_skill_no_bonus(self) -> None:
        # 0 ranks → no class skill bonus
        assert skill_modifier(0.0, 3, is_class_skill=True) == 3

    def test_with_misc(self) -> None:
        assert skill_modifier(4.0, 2, is_class_skill=True, misc=2) == 11

    def test_negative_ability(self) -> None:
        assert skill_modifier(2.0, -1, is_class_skill=True) == 4  # 2-1+3


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
