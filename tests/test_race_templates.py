"""Tests for racial/template adjustment logic (heroforge.logic.race_templates)."""

from __future__ import annotations

from heroforge.logic import race_templates as rt
from heroforge.models.race import Race
from heroforge.models.template import Template


def _elf() -> Race:
    return Race(name="Elf", size="Medium", dex_adj=2, con_adj=-2, level_adjustment=0)


def _half_dragon() -> Template:
    return Template(
        name="Half-Dragon",
        str_adj=8,
        con_adj=2,
        int_adj=2,
        cha_adj=2,
        level_adjustment=3,
    )


def _fiendish() -> Template:
    return Template(name="Fiendish", level_adjustment=2)


class TestAbilityAdjustments:
    def test_race_only(self) -> None:
        adj = rt.ability_adjustments(_elf())
        assert adj == {
            "STR": 0,
            "DEX": 2,
            "CON": -2,
            "INT": 0,
            "WIS": 0,
            "CHA": 0,
        }

    def test_no_race_no_templates(self) -> None:
        assert rt.ability_adjustments(None) == {
            "STR": 0,
            "DEX": 0,
            "CON": 0,
            "INT": 0,
            "WIS": 0,
            "CHA": 0,
        }

    def test_race_and_template_stack_additively(self) -> None:
        # Elf DEX +2 / CON -2 stacks with Half-Dragon STR +8 / CON +2 / INT +2.
        adj = rt.ability_adjustments(_elf(), [_half_dragon()])
        assert adj["STR"] == 8
        assert adj["DEX"] == 2
        assert adj["CON"] == 0  # -2 (race) + 2 (template)
        assert adj["INT"] == 2
        assert adj["CHA"] == 2

    def test_multiple_templates_stack(self) -> None:
        # Two templates each contributing CON +2 stack on top of the race.
        a = Template(name="A", con_adj=2)
        b = Template(name="B", con_adj=2)
        adj = rt.ability_adjustments(_elf(), [a, b])
        assert adj["CON"] == 2  # -2 (elf) + 2 + 2


class TestApplyAbilityAdjustments:
    def _base(self) -> dict[str, int]:
        return {ab: 10 for ab in ("STR", "DEX", "CON", "INT", "WIS", "CHA")}

    def test_applies_race_and_templates(self) -> None:
        scores = rt.apply_ability_adjustments(self._base(), _elf(), [_half_dragon()])
        assert scores["STR"] == 18
        assert scores["DEX"] == 12
        assert scores["CON"] == 10
        assert scores["INT"] == 12
        assert scores["CHA"] == 12

    def test_penalty_floored_at_one(self) -> None:
        weak = Template(name="Weak", str_adj=-20)
        scores = rt.apply_ability_adjustments({"STR": 8}, None, [weak])
        assert scores["STR"] == 1

    def test_missing_base_defaults_to_ten(self) -> None:
        scores = rt.apply_ability_adjustments({}, _elf())
        assert scores["DEX"] == 12
        assert scores["CON"] == 8


class TestLevelAdjustment:
    def test_total_la_sums_race_and_templates(self) -> None:
        la = rt.total_level_adjustment(_elf(), [_half_dragon(), _fiendish()])
        assert la == 5  # 0 + 3 + 2

    def test_total_la_no_inputs(self) -> None:
        assert rt.total_level_adjustment(None) == 0

    def test_effective_character_level(self) -> None:
        ecl = rt.effective_character_level(5, _elf(), [_half_dragon()])
        assert ecl == 8  # 5 class levels + 3 LA

    def test_effective_character_level_no_adjustments(self) -> None:
        assert rt.effective_character_level(7, None) == 7
