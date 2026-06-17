"""Tests for hit-point calculations (heroforge.logic.health)."""

from __future__ import annotations

from heroforge.logic.health import hit_dice_sequence, max_hit_points


class TestHitDiceSequence:
    def test_expands_classes_in_order(self) -> None:
        seq = hit_dice_sequence(
            [("Fighter", 2), ("Wizard", 3)],
            {"Fighter": 10, "Wizard": 4},
        )
        assert seq == [10, 10, 4, 4, 4]

    def test_unknown_class_uses_default_hit_die(self) -> None:
        assert hit_dice_sequence([("Homebrew", 3)]) == [8, 8, 8]
        assert hit_dice_sequence([("Homebrew", 2)], default_hit_die=6) == [6, 6]

    def test_zero_or_negative_levels_contribute_nothing(self) -> None:
        assert hit_dice_sequence([("Fighter", 0), ("Rogue", -1)], {"Fighter": 10}) == []


class TestMaxHitPoints:
    def test_empty_character_has_no_hit_points(self) -> None:
        assert max_hit_points([], 0) == 0

    def test_first_level_is_maximised(self) -> None:
        # A single d10 level grants the full die.
        assert max_hit_points([10], 0) == 10

    def test_later_levels_take_average_rounded_up(self) -> None:
        # Fighter 3 (d10): 10 (max) + 6 + 6 = 22.
        assert max_hit_points([10, 10, 10], 0) == 22

    def test_constitution_modifier_applied_per_hit_die(self) -> None:
        # d8 ×2 with +2 Con: (8 + 2) + (5 + 2) = 17.
        assert max_hit_points([8, 8], 2) == 17

    def test_each_hit_die_yields_at_least_one(self) -> None:
        # Punishing Con penalty floors each Hit Die at 1 hp.
        assert max_hit_points([6, 6, 6], -10) == 3

    def test_flat_bonus_added_once(self) -> None:
        # Toughness-style +3 flat bonus.
        assert max_hit_points([8, 8], 0, flat_bonus=3) == 8 + 5 + 3

    def test_per_level_bonus_added_to_every_hit_die(self) -> None:
        # Improved Toughness-style +1 per Hit Die.
        assert max_hit_points([8, 8], 0, per_level_bonus=1) == (8 + 1) + (5 + 1)

    def test_zero_hit_die_contributes_minimum_one(self) -> None:
        # A 0-sized die still yields the per-level minimum of 1.
        assert max_hit_points([0, 0], 0) == 2

    def test_max_first_level_disabled_uses_average(self) -> None:
        assert max_hit_points([10, 10], 0, max_first_level=False) == 6 + 6
