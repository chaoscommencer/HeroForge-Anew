"""Tests for build / house-rule options storage and retrieval.

Covers the declarative option registry (:mod:`heroforge.models.options`) and the
tolerant point-buy helper used to apply the point-buy budget option.
"""

from __future__ import annotations

import pytest

from heroforge.logic.ability_scores import point_buy_spent
from heroforge.models.options import (
    POINT_BUY_BUDGET,
    OptionSpec,
    default_options,
    get_int_option,
    point_buy_budget,
)


class TestOptionSpec:
    def test_coerce_parses_string(self) -> None:
        spec = OptionSpec("k", "K", default=25, minimum=15, maximum=40)
        assert spec.coerce("30") == 30

    def test_coerce_clamps_to_range(self) -> None:
        spec = OptionSpec("k", "K", default=25, minimum=15, maximum=40)
        assert spec.coerce("100") == 40
        assert spec.coerce("1") == 15

    def test_coerce_falls_back_on_garbage(self) -> None:
        spec = OptionSpec("k", "K", default=25, minimum=15, maximum=40)
        assert spec.coerce("not-a-number") == 25
        assert spec.coerce(None) == 25


class TestDefaultsAndAccessors:
    def test_default_options_are_strings(self) -> None:
        defaults = default_options()
        assert defaults[POINT_BUY_BUDGET] == "25"
        assert all(isinstance(v, str) for v in defaults.values())

    def test_point_buy_budget_reads_stored_value(self) -> None:
        assert point_buy_budget({POINT_BUY_BUDGET: "32"}) == 32

    def test_point_buy_budget_defaults_when_unset(self) -> None:
        assert point_buy_budget({}) == 25

    def test_get_int_option_unknown_key_raises(self) -> None:
        with pytest.raises(KeyError):
            get_int_option({}, "no_such_option")


class TestPointBuySpent:
    def test_all_tens_costs_twelve(self) -> None:
        scores = dict.fromkeys(("STR", "DEX", "CON", "INT", "WIS", "CHA"), 10)
        assert point_buy_spent(scores) == 12

    def test_tolerates_out_of_range_scores(self) -> None:
        # Below 8 costs nothing; above 18 is treated as the most expensive entry.
        assert point_buy_spent({"STR": 1, "DEX": 100}) == 16
