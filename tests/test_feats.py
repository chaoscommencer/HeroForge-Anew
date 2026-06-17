"""Tests for heroforge.logic.feats.

Reference: PHB Chapter 5.
"""

from __future__ import annotations

import logging

import pytest

from heroforge.logic.feats import (
    available_feats,
    check_prerequisites,
    feat_slots_available,
)


class TestFeatSlotsAvailable:
    def test_level_1(self) -> None:
        # Level 1 always gets 1 general feat
        assert feat_slots_available(1) == 1

    def test_level_3(self) -> None:
        assert feat_slots_available(3) == 2

    def test_level_6(self) -> None:
        assert feat_slots_available(6) == 3

    def test_level_20(self) -> None:
        # General feats at 1,3,6,9,12,15,18 = 7
        assert feat_slots_available(20) == 7

    def test_fighter_bonus_feats(self) -> None:
        # Fighter 4: general=2 (levels 1,3), fighter=3 (levels 1,2,4)
        assert feat_slots_available(4, fighter_levels=4) == 5

    def test_wizard_bonus_feats(self) -> None:
        # Wizard 5: general=2, wizard bonus=2 (levels 1,5)
        assert feat_slots_available(5, wizard_levels=5) == 4

    def test_no_bonus_feats(self) -> None:
        assert feat_slots_available(9, fighter_levels=0, wizard_levels=0) == 4


class TestCheckPrerequisites:
    def test_empty_prereqs_always_passes(self) -> None:
        assert check_prerequisites([], 10, {"STR": 10}, {}, [], 5) is True

    def test_bab_met(self) -> None:
        assert check_prerequisites(["+6 BAB"], 6, {"STR": 10}, {}, [], 10) is True

    def test_bab_not_met(self) -> None:
        assert check_prerequisites(["+6 BAB"], 5, {"STR": 10}, {}, [], 10) is False

    def test_ability_score_met(self) -> None:
        assert check_prerequisites(["STR 13"], 5, {"STR": 15}, {}, [], 5) is True

    def test_ability_score_not_met(self) -> None:
        assert check_prerequisites(["STR 13"], 5, {"STR": 11}, {}, [], 5) is False

    def test_feat_prereq_met(self) -> None:
        assert (
            check_prerequisites(
                ["Power Attack"], 5, {"STR": 13}, {}, ["Power Attack"], 5
            )
            is True
        )

    def test_feat_prereq_not_met(self) -> None:
        assert check_prerequisites(["Power Attack"], 5, {"STR": 13}, {}, [], 5) is False

    def test_skill_prereq_met(self) -> None:
        assert (
            check_prerequisites(["Tumble 5 ranks"], 5, {}, {"Tumble": 6.0}, [], 5)
            is True
        )

    def test_skill_prereq_not_met(self) -> None:
        assert (
            check_prerequisites(["Tumble 5 ranks"], 5, {}, {"Tumble": 4.0}, [], 5)
            is False
        )

    def test_multiple_prereqs_all_met(self) -> None:
        assert (
            check_prerequisites(
                ["STR 13", "Power Attack"],
                6,
                {"STR": 16},
                {},
                ["Power Attack"],
                6,
            )
            is True
        )

    def test_multiple_prereqs_one_fails(self) -> None:
        assert (
            check_prerequisites(
                ["STR 13", "Power Attack"],
                6,
                {"STR": 16},
                {},
                [],  # Missing Power Attack
                6,
            )
            is False
        )

    def test_empty_prereq_logs_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="heroforge.logic.feats"):
            result = check_prerequisites(["", "STR 13"], 5, {"STR": 13}, {}, [], 5)
        assert result is True
        assert "Received empty prerequisite" in caplog.text


class TestRecursivePrerequisites:
    """Recursive validation through chained feat prerequisites (issue #64)."""

    # Greater Cleave -> Cleave -> Power Attack -> STR 13
    _prereq_mapping = {
        "Greater Cleave": ["Cleave"],
        "Cleave": ["Power Attack"],
        "Power Attack": ["STR 13"],
    }

    def test_full_chain_satisfied(self) -> None:
        assert (
            check_prerequisites(
                ["Cleave"],
                0,
                {"STR": 13},
                {},
                ["Cleave", "Power Attack"],
                6,
                feat_prereqs=self._prereq_mapping,
            )
            is True
        )

    def test_nested_feat_missing_fails(self) -> None:
        # Character has Cleave but is missing its prerequisite Power Attack.
        assert (
            check_prerequisites(
                ["Cleave"],
                0,
                {"STR": 13},
                {},
                ["Cleave"],  # Power Attack absent
                6,
                feat_prereqs=self._prereq_mapping,
            )
            is False
        )

    def test_deep_nested_ability_unmet_fails(self) -> None:
        # All feats present, but Power Attack's STR 13 requirement is unmet.
        assert (
            check_prerequisites(
                ["Cleave"],
                0,
                {"STR": 10},
                {},
                ["Cleave", "Power Attack"],
                6,
                feat_prereqs=self._prereq_mapping,
            )
            is False
        )

    def test_without_mapping_is_shallow(self) -> None:
        # No mapping supplied: only direct possession is checked (legacy
        # behaviour), so the missing nested prerequisite is not detected.
        assert (
            check_prerequisites(
                ["Cleave"],
                0,
                {"STR": 10},
                {},
                ["Cleave"],
                6,
            )
            is True
        )

    def test_cycle_is_handled(self) -> None:
        cyclic = {"A": ["B"], "B": ["A"]}
        assert (
            check_prerequisites(
                ["A"],
                0,
                {},
                {},
                ["A", "B"],
                1,
                feat_prereqs=cyclic,
            )
            is True
        )

    def test_available_feats_recurses(self) -> None:
        all_feats = ["Power Attack", "Cleave", "Greater Cleave"]
        # Character has Cleave but not Power Attack, so Greater Cleave (which
        # requires Cleave, which requires the missing Power Attack) must be
        # excluded.
        result = available_feats(
            all_feats, self._prereq_mapping, 0, {"STR": 13}, {}, ["Cleave"], 6
        )
        assert "Greater Cleave" not in result


class TestAvailableFeats:
    def test_no_prereqs_available(self) -> None:
        all_feats = ["Alertness", "Improved Initiative"]
        feat_prereqs: dict[str, list[str]] = {}
        result = available_feats(all_feats, feat_prereqs, 0, {}, {}, [], 1)
        assert "Alertness" in result
        assert "Improved Initiative" in result

    def test_already_taken_excluded(self) -> None:
        all_feats = ["Alertness", "Improved Initiative"]
        result = available_feats(all_feats, {}, 0, {}, {}, ["Alertness"], 1)
        assert "Alertness" not in result
        assert "Improved Initiative" in result

    def test_prereq_filters_out(self) -> None:
        all_feats = ["Power Attack", "Cleave"]
        feat_prereqs = {"Cleave": ["Power Attack"]}
        result = available_feats(all_feats, feat_prereqs, 10, {"STR": 16}, {}, [], 1)
        assert "Power Attack" in result
        assert "Cleave" not in result

    def test_prereq_met_included(self) -> None:
        all_feats = ["Power Attack", "Cleave"]
        feat_prereqs = {"Cleave": ["Power Attack"]}
        result = available_feats(
            all_feats, feat_prereqs, 10, {"STR": 16}, {}, ["Power Attack"], 1
        )
        assert "Cleave" in result
