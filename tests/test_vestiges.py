"""Tests for binder vestige logic (Tome of Magic; Excel tab 8d)."""

from __future__ import annotations

import pytest

from heroforge.logic import vestiges
from heroforge.logic.derived_stats import compute_derived_stats
from heroforge.models.character import Character


class TestBinderLevel:
    def test_sums_binder_class_levels(self) -> None:
        char = Character(classes=[("Binder", 5), ("Fighter", 2)])
        assert vestiges.binder_level(char) == 5

    def test_case_insensitive_class_name(self) -> None:
        char = Character(classes=[("binder", 3)])
        assert vestiges.binder_level(char) == 3

    def test_non_binder_without_feat_is_zero(self) -> None:
        char = Character(classes=[("Fighter", 10)])
        assert vestiges.binder_level(char) == 0

    def test_bind_vestige_feat_grants_level_one(self) -> None:
        char = Character(classes=[("Fighter", 10)], feats=["Bind Vestige"])
        assert vestiges.binder_level(char) == 1

    def test_improved_bind_vestige_feat_grants_level_five(self) -> None:
        char = Character(
            classes=[("Fighter", 10)],
            feats=["Bind Vestige", "Improved Bind Vestige"],
        )
        assert vestiges.binder_level(char) == 5

    def test_binder_levels_outrank_feat_fallback(self) -> None:
        char = Character(classes=[("Binder", 4)], feats=["Bind Vestige"])
        assert vestiges.binder_level(char) == 4


class TestMaxVestigeLevel:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, 0),
            (1, 1),
            (2, 1),
            (3, 2),
            (5, 3),
            (7, 4),
            (10, 5),
            (12, 6),
            (15, 7),
            (17, 8),
            (20, 8),
        ],
    )
    def test_progression(self, level: int, expected: int) -> None:
        assert vestiges.max_vestige_level(level) == expected


class TestMaxVestigesBound:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, 0),
            (1, 1),
            (7, 1),
            (8, 2),
            (13, 2),
            (14, 3),
            (19, 3),
            (20, 4),
        ],
    )
    def test_progression(self, level: int, expected: int) -> None:
        assert vestiges.max_vestiges_bound(level) == expected


class TestCanBind:
    def test_within_limit(self) -> None:
        assert vestiges.can_bind(1, 1) is True

    def test_above_limit(self) -> None:
        # A 2nd-level vestige needs binder level 3.
        assert vestiges.can_bind(2, 1) is False
        assert vestiges.can_bind(2, 3) is True

    def test_unknown_level_allowed_for_binder(self) -> None:
        assert vestiges.can_bind(None, 1) is True
        assert vestiges.can_bind(None, 0) is False


class TestBoundVestigeNames:
    def test_only_bound_entries(self) -> None:
        char = Character(
            vestiges=[
                {"vestige_name": "Eligor", "level": 7, "bound": True},
                {"vestige_name": "Paimon", "level": 3, "bound": False},
                {"vestige_name": "", "level": 1, "bound": True},
            ]
        )
        assert vestiges.bound_vestige_names(char) == ["Eligor"]

    def test_missing_bound_key_defaults_true(self) -> None:
        char = Character(vestiges=[{"vestige_name": "Paimon", "level": 3}])
        assert vestiges.bound_vestige_names(char) == ["Paimon"]


class TestEffects:
    def test_ability_adjustments(self) -> None:
        assert vestiges.ability_adjustments(["Eligor"]) == {"STR": 4}
        assert vestiges.ability_adjustments(["Paimon"]) == {"DEX": 4}

    def test_ability_adjustments_accumulate(self) -> None:
        assert vestiges.ability_adjustments(["Eligor", "Paimon"]) == {
            "STR": 4,
            "DEX": 4,
        }

    def test_ac_bonuses(self) -> None:
        assert vestiges.ac_bonuses(["Eligor"]) == [("natural", 3)]

    def test_case_insensitive(self) -> None:
        assert vestiges.ability_adjustments(["eligor"]) == {"STR": 4}

    def test_unknown_vestige_has_no_effect(self) -> None:
        assert vestiges.ability_adjustments(["Amon"]) == {}
        assert vestiges.ac_bonuses(["Amon"]) == []


class TestEffectsFeedDerivedStats:
    def test_ability_bonus_changes_modifier(self) -> None:
        base = Character(ability_scores={"STR": 10, "DEX": 14})
        bound = vestiges.bound_vestige_names(
            Character(vestiges=[{"vestige_name": "Eligor", "bound": True}])
        )
        adjustments = vestiges.ability_adjustments(bound)
        stats = compute_derived_stats(base, ability_adjustments=adjustments)
        # +4 STR raises STR to 14 (+2 modifier) from the baseline +0.
        assert stats.effective_ability_scores["STR"] == 14
        assert stats.ability_modifiers["STR"] == 2

    def test_natural_armor_bonus_raises_ac(self) -> None:
        base = Character(ability_scores={"DEX": 10})
        without = compute_derived_stats(base)
        with_vestige = compute_derived_stats(
            base, ac_bonuses=vestiges.ac_bonuses(["Eligor"])
        )
        assert with_vestige.armor_class == without.armor_class + 3
