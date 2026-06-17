"""Tests for Tome of Battle maneuver/stance mechanics (Excel tab 8b).

These cover the structured stance-effect source of truth
(:mod:`heroforge.logic.maneuvers`) and its mechanical application to the
derived-stats pipeline.
"""

from __future__ import annotations

from heroforge.logic.derived_stats import compute_derived_stats
from heroforge.logic.maneuvers import (
    STANCE_EFFECTS,
    active_stance_effects,
    active_stance_names,
    describe_effect,
    stance_ac_bonuses,
    stance_save_bonuses,
)
from heroforge.models.character import Character


def _maneuver(name: str, readied: bool) -> dict:  # type: ignore[type-arg]
    return {"maneuver_name": name, "readied": readied}


def test_active_stance_names_only_readied() -> None:
    maneuvers = [
        _maneuver("Punishing Stance", True),
        _maneuver("Iron Guard's Glare", False),
        _maneuver("Punishing Stance", True),  # duplicate ignored
        {"maneuver_name": "", "readied": True},  # blank ignored
    ]
    assert active_stance_names(maneuvers) == ["Punishing Stance"]


def test_active_stance_effects_matches_catalogue() -> None:
    maneuvers = [_maneuver("Punishing Stance", True)]
    effects = active_stance_effects(maneuvers)
    assert {e.target for e in effects} == {"untyped", "Reflex"}
    # An active stance that is not in the catalogue contributes nothing.
    assert active_stance_effects([_maneuver("Iron Guard's Glare", True)]) == []


def test_unreadied_stance_has_no_effect() -> None:
    maneuvers = [_maneuver("Punishing Stance", False)]
    assert stance_save_bonuses(maneuvers) == {}
    assert stance_ac_bonuses(maneuvers) == []


def test_punishing_stance_unconditional_bonuses() -> None:
    maneuvers = [_maneuver("Punishing Stance", True)]
    # Punishing Stance: -2 AC (untyped) and -2 Reflex saves (ToB p70).
    assert stance_save_bonuses(maneuvers) == {"ref": -2}
    assert stance_ac_bonuses(maneuvers) == [("untyped", -2)]


def test_conditional_stances_are_excluded() -> None:
    # Stonefoot Stance's +2 AC and Bolstering Voice's +2 Will save are both
    # situational, so neither feeds a computed total.
    maneuvers = [
        _maneuver("Stonefoot Stance", True),
        _maneuver("Bolstering Voice", True),
    ]
    assert stance_save_bonuses(maneuvers) == {}
    assert stance_ac_bonuses(maneuvers) == []


def test_stance_save_bonuses_accumulate() -> None:
    from heroforge.logic.maneuvers import KIND_SAVE, StanceEffect

    custom = (
        *STANCE_EFFECTS,
        # A second unconditional Reflex effect on Punishing Stance.
        StanceEffect("Punishing Stance", -1, KIND_SAVE, "Reflex"),
    )
    maneuvers = [_maneuver("Punishing Stance", True)]
    assert stance_save_bonuses(maneuvers, custom) == {"ref": -3}


def test_describe_effect_text() -> None:
    by_name = {(e.stance_name, e.kind): e for e in STANCE_EFFECTS}
    punishing_ac = by_name[("Punishing Stance", "ac")]
    punishing_ref = by_name[("Punishing Stance", "save")]
    bolster = by_name[("Bolstering Voice", "save")]
    assert describe_effect(punishing_ac) == "-2 penalty to AC."
    assert describe_effect(punishing_ref) == "-2 penalty on Reflex saves."
    assert describe_effect(bolster) == (
        "+2 bonus on Will saves against fear and charm effects."
    )


def test_derived_stats_apply_punishing_stance() -> None:
    base = Character(name="Warblade", ability_scores={"DEX": 10})
    base.classes = [("Warblade", 5)]
    baseline = compute_derived_stats(base)

    base.maneuvers = [_maneuver("Punishing Stance", True)]
    saves = stance_save_bonuses(base.maneuvers)
    ac = stance_ac_bonuses(base.maneuvers)
    stanced = compute_derived_stats(base, save_bonuses=saves, ac_bonuses=ac)

    assert stanced.armor_class == baseline.armor_class - 2
    assert stanced.touch_ac == baseline.touch_ac - 2
    assert stanced.flat_footed_ac == baseline.flat_footed_ac - 2
    assert stanced.reflex == baseline.reflex - 2
    # Other saves are untouched.
    assert stanced.fortitude == baseline.fortitude
    assert stanced.will == baseline.will
