"""Tests for buff stacking calculations (heroforge.logic.buffs)."""

from __future__ import annotations

from heroforge.logic.buffs import (
    aggregate_bonuses,
    apply_buff,
    effective_bonus,
    remove_buff,
    stacks_with,
    temporary_hp_total,
)


class TestStacksWith:
    def test_same_named_type_does_not_stack(self) -> None:
        assert stacks_with("morale", "morale") is False
        assert stacks_with("enhancement", "enhancement") is False

    def test_different_named_types_stack(self) -> None:
        assert stacks_with("morale", "enhancement") is True

    def test_always_stacking_types(self) -> None:
        assert stacks_with("dodge", "dodge") is True
        assert stacks_with("circumstance", "circumstance") is True
        assert stacks_with("untyped", "untyped") is True
        # Case-insensitive.
        assert stacks_with("Dodge", "DODGE") is True


class TestApplyAndRemoveBuff:
    def test_apply_records_bonus(self) -> None:
        bonuses: dict[str, dict[str, int]] = {}
        apply_buff(bonuses, "Bless", "morale", "attack", 1)
        assert bonuses == {"attack": {"Bless::morale": 1}}

    def test_remove_strips_all_of_a_buffs_bonuses(self) -> None:
        bonuses: dict[str, dict[str, int]] = {}
        apply_buff(bonuses, "Bless", "morale", "attack", 1)
        apply_buff(bonuses, "Bless", "morale", "saves", 1)
        remove_buff(bonuses, "Bless")
        assert bonuses == {"attack": {}, "saves": {}}


class TestEffectiveBonus:
    def test_non_stacking_types_take_highest(self) -> None:
        bonuses: dict[str, dict[str, int]] = {}
        apply_buff(bonuses, "Prayer", "luck", "attack", 1)
        apply_buff(bonuses, "Aid", "luck", "attack", 3)
        assert effective_bonus(bonuses, "attack") == 3

    def test_stacking_types_sum(self) -> None:
        bonuses: dict[str, dict[str, int]] = {}
        apply_buff(bonuses, "Haste", "dodge", "AC", 1)
        apply_buff(bonuses, "Shield Spell", "dodge", "AC", 2)
        assert effective_bonus(bonuses, "AC") == 3

    def test_mixed_types_combine(self) -> None:
        bonuses: dict[str, dict[str, int]] = {}
        apply_buff(bonuses, "Bless", "morale", "attack", 1)
        apply_buff(bonuses, "Greater Magic Weapon", "enhancement", "attack", 2)
        apply_buff(bonuses, "Inspire Courage", "morale", "attack", 2)
        # morale -> max(1, 2) = 2; enhancement -> 2; total 4.
        assert effective_bonus(bonuses, "attack") == 4

    def test_unknown_stat_is_zero(self) -> None:
        assert effective_bonus({}, "attack") == 0


class TestAggregateBonuses:
    def test_groups_by_stat(self) -> None:
        net = aggregate_bonuses(
            [
                ("bless", "morale", "melee", 1),
                ("mage_armor", "armor", "ac", 4),
            ]
        )
        assert net == {"melee": 1, "ac": 4}

    def test_same_type_duplicates_do_not_stack(self) -> None:
        # Two castings of Bless from different sources: morale does not stack.
        net = aggregate_bonuses(
            [
                ("bless_a", "morale", "melee", 1),
                ("bless_b", "morale", "melee", 1),
            ]
        )
        assert net == {"melee": 1}

    def test_stacking_type_duplicates_sum(self) -> None:
        net = aggregate_bonuses(
            [
                ("a", "dodge", "ac", 1),
                ("b", "dodge", "ac", 1),
            ]
        )
        assert net == {"ac": 2}

    def test_identical_sources_remain_distinct(self) -> None:
        # Equal source labels must not collapse before stacking is evaluated.
        net = aggregate_bonuses(
            [
                ("dup", "dodge", "ac", 1),
                ("dup", "dodge", "ac", 1),
            ]
        )
        assert net == {"ac": 2}

    def test_empty_records(self) -> None:
        assert aggregate_bonuses([]) == {}


class TestTemporaryHp:
    def test_highest_only(self) -> None:
        assert temporary_hp_total([5, 10, 3]) == 10

    def test_empty_is_zero(self) -> None:
        assert temporary_hp_total([]) == 0
