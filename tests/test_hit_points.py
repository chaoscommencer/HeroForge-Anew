"""Tests for heroforge.logic.hit_points.

Reference: PHB p145 (Hit Points / Hit Dice), DMG p198 (average HP).
"""

from __future__ import annotations

from heroforge.logic.hit_points import (
    average_hit_die_value,
    compute_hit_points,
)


class TestAverageHitDieValue:
    def test_standard_dice_round_up(self) -> None:
        assert average_hit_die_value(4) == 3
        assert average_hit_die_value(6) == 4
        assert average_hit_die_value(8) == 5
        assert average_hit_die_value(10) == 6
        assert average_hit_die_value(12) == 7

    def test_non_positive_die(self) -> None:
        assert average_hit_die_value(0) == 0
        assert average_hit_die_value(-4) == 0


class TestComputeHitPoints:
    def test_no_classes_is_zero(self) -> None:
        assert compute_hit_points([], {}, 0) == 0

    def test_single_level_is_maximised(self) -> None:
        # A level-1 Fighter (d10), no Con: max first level = 10.
        assert compute_hit_points([("Fighter", 1)], {"Fighter": 10}, 0) == 10

    def test_average_after_first_level(self) -> None:
        # Fighter 3 (d10): 10 (max) + 6 + 6 = 22.
        assert compute_hit_points([("Fighter", 3)], {"Fighter": 10}, 0) == 22

    def test_constitution_applies_per_hit_die(self) -> None:
        # Fighter 3 (d10), +2 Con: (10+2) + (6+2) + (6+2) = 28.
        assert compute_hit_points([("Fighter", 3)], {"Fighter": 10}, 2) == 28

    def test_minimum_one_per_hit_die_with_con_penalty(self) -> None:
        # Wizard 3 (d4), -5 Con: first level max(1, 4-5)=1, others max(1, 3-5)=1.
        assert compute_hit_points([("Wizard", 3)], {"Wizard": 4}, -5) == 3

    def test_max_method_takes_full_dice(self) -> None:
        # Fighter 3 (d10) using max method: 10 * 3 = 30.
        assert (
            compute_hit_points([("Fighter", 3)], {"Fighter": 10}, 0, method="max") == 30
        )

    def test_unknown_class_uses_default_hit_die(self) -> None:
        # Default d8: max 8 + average 5 = 13.
        assert compute_hit_points([("Homebrew", 2)], {}, 0) == 13

    def test_multiclass_keeps_first_level_max(self) -> None:
        # Order matters: Wizard 1 (d4 max=4) then Fighter 1 (d10 avg=6) = 10.
        assert (
            compute_hit_points(
                [("Wizard", 1), ("Fighter", 1)],
                {"Wizard": 4, "Fighter": 10},
                0,
            )
            == 10
        )

    def test_bonus_hp_added(self) -> None:
        # Fighter 1 (d10) + Toughness (+3) = 13.
        assert (
            compute_hit_points([("Fighter", 1)], {"Fighter": 10}, 0, bonus_hp=3) == 13
        )

    def test_disable_first_level_max(self) -> None:
        # Fighter 1 (d10) without maximised first level uses the average (6).
        assert (
            compute_hit_points(
                [("Fighter", 1)], {"Fighter": 10}, 0, max_first_level=False
            )
            == 6
        )
