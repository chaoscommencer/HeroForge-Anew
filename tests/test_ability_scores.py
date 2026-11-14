"""Tests for heroforge.logic.ability_scores.

Reference: PHB p8, p307.
"""

from __future__ import annotations

import pytest

from heroforge.logic.ability_scores import (
    ability_modifier,
    apply_ability_damage,
    apply_ability_drain,
    point_buy_cost,
    total_point_buy_cost,
)


class TestAbilityModifier:
    def test_score_10_gives_zero(self) -> None:
        assert ability_modifier(10) == 0

    def test_score_11_gives_zero(self) -> None:
        # PHB p8: (11 - 10) // 2 = 0
        assert ability_modifier(11) == 0

    def test_score_12_gives_plus_one(self) -> None:
        assert ability_modifier(12) == 1

    def test_score_18_gives_plus_four(self) -> None:
        assert ability_modifier(18) == 4

    def test_score_8_gives_minus_one(self) -> None:
        assert ability_modifier(8) == -1

    def test_score_7_gives_minus_two(self) -> None:
        assert ability_modifier(7) == -2

    def test_score_1_gives_minus_five(self) -> None:
        assert ability_modifier(1) == -5

    def test_score_20_gives_plus_five(self) -> None:
        assert ability_modifier(20) == 5

    def test_score_3_gives_minus_four(self) -> None:
        assert ability_modifier(3) == -4

    def test_score_30_gives_plus_ten(self) -> None:
        assert ability_modifier(30) == 10


class TestApplyAbilityDrain:
    def test_drain_reduces_score(self) -> None:
        assert apply_ability_drain(18, 3) == 15

    def test_drain_clamped_to_zero(self) -> None:
        assert apply_ability_drain(2, 5) == 0

    def test_no_drain(self) -> None:
        assert apply_ability_drain(14, 0) == 14

    def test_exact_drain_to_zero(self) -> None:
        assert apply_ability_drain(6, 6) == 0


class TestApplyAbilityDamage:
    def test_damage_reduces_score(self) -> None:
        assert apply_ability_damage(16, 4) == 12

    def test_damage_clamped_to_one(self) -> None:
        # Score cannot be reduced below 1 by ability damage
        assert apply_ability_damage(3, 10) == 1

    def test_no_damage(self) -> None:
        assert apply_ability_damage(10, 0) == 10

    def test_damage_leaves_one(self) -> None:
        assert apply_ability_damage(5, 4) == 1


class TestPointBuyCost:
    def test_score_8_costs_zero(self) -> None:
        assert point_buy_cost(8) == 0

    def test_score_10_costs_two(self) -> None:
        assert point_buy_cost(10) == 2

    def test_score_14_costs_six(self) -> None:
        assert point_buy_cost(14) == 6

    def test_score_18_costs_sixteen(self) -> None:
        assert point_buy_cost(18) == 16

    def test_invalid_score_raises(self) -> None:
        with pytest.raises(ValueError):
            point_buy_cost(7)

    def test_invalid_high_score_raises(self) -> None:
        with pytest.raises(ValueError):
            point_buy_cost(19)


class TestTotalPointBuyCost:
    def test_all_tens_costs_twelve(self) -> None:
        scores = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        assert total_point_buy_cost(scores) == 12  # 6 × 2

    def test_standard_array_equivalent(self) -> None:
        # 15, 14, 13, 12, 10, 8 → 8 + 6 + 5 + 4 + 2 + 0 = 25
        scores = {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}
        assert total_point_buy_cost(scores) == 25
