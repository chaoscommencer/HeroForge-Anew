"""Tests for Tome of Battle maneuver/stance mechanics (Excel tab 8b).

These cover the structured stance-effect source of truth
(:mod:`heroforge.logic.maneuvers`) and its mechanical application to the
derived-stats pipeline.
"""

from __future__ import annotations

from heroforge.logic.derived_stats import compute_derived_stats
import pytest

from heroforge.logic.maneuvers import (
    KIND_AC,
    KIND_SAVE,
    STANCE_EFFECTS,
    StanceEffect,
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
    assert {(e.kind, e.target, e.bonus_type) for e in effects} == {
        (KIND_AC, "AC", "untyped")
    }
    # An active stance that is not in the catalogue contributes nothing.
    assert active_stance_effects([_maneuver("Iron Guard's Glare", True)]) == []


def test_unreadied_stance_has_no_effect() -> None:
    maneuvers = [_maneuver("Punishing Stance", False)]
    assert stance_save_bonuses(maneuvers) == {}
    assert stance_ac_bonuses(maneuvers) == []


def test_punishing_stance_unconditional_bonuses() -> None:
    maneuvers = [_maneuver("Punishing Stance", True)]
    # Punishing Stance: -2 AC (untyped) only; it has no save penalty
    # (workbook Maneuvers & Stances row 88, ToB p70).
    assert stance_save_bonuses(maneuvers) == {}
    assert stance_ac_bonuses(maneuvers) == [("untyped", -2)]


def test_conditional_stances_are_excluded() -> None:
    # Stonefoot Stance's +2 AC, Stance of Clarity's +2/-2 AC and Bolstering
    # Voice's ally-only +2 Will save are all situational, so none of them
    # feeds a computed total.
    maneuvers = [
        _maneuver("Stonefoot Stance", True),
        _maneuver("Stance of Clarity", True),
        _maneuver("Bolstering Voice", True),
    ]
    assert stance_save_bonuses(maneuvers) == {}
    assert stance_ac_bonuses(maneuvers) == []


def test_stance_save_bonuses_accumulate() -> None:
    custom = (
        *STANCE_EFFECTS,
        # Two unconditional Reflex effects on Punishing Stance.
        StanceEffect("Punishing Stance", -1, KIND_SAVE, "Reflex"),
        StanceEffect("Punishing Stance", -2, KIND_SAVE, "Reflex"),
    )
    maneuvers = [_maneuver("Punishing Stance", True)]
    assert stance_save_bonuses(maneuvers, custom) == {"ref": -3}


def test_describe_effect_text() -> None:
    by_name = {(e.stance_name, e.kind): e for e in STANCE_EFFECTS}
    punishing_ac = by_name[("Punishing Stance", "ac")]
    bolster = by_name[("Bolstering Voice", "save")]
    assert describe_effect(punishing_ac) == "-2 penalty to AC."
    # Workbook row 211: "Allies gain +2 bonus on Will saves, +4 against fear".
    assert describe_effect(bolster) == (
        "+2 bonus on Will saves for allies only (+4 against fear)."
    )


def test_catalogue_matches_workbook_text() -> None:
    """Conditional entries follow the workbook's Maneuvers & Stances text."""
    names = {e.stance_name for e in STANCE_EFFECTS}
    # Row 167: "+10 bonus on checks against bull rush, trip, and others, and
    # gain DR 2/-" — no AC or saving-throw effect to catalogue.
    assert "Roots of the Mountain" not in names
    # Row 66: "Gain +2 AC against one fo[e], -2 against all others"; ToB types
    # the bonus as insight.
    clarity = sorted(
        (e.value, e.bonus_type, e.condition)
        for e in STANCE_EFFECTS
        if e.stance_name == "Stance of Clarity"
    )
    assert clarity == [
        (-2, "untyped", "against all other opponents"),
        (2, "insight", "against one chosen opponent"),
    ]
    bolster = [e for e in STANCE_EFFECTS if e.stance_name == "Bolstering Voice"]
    assert len(bolster) == 1 and bolster[0].conditional


def test_derived_stats_apply_punishing_stance() -> None:
    base = Character(name="Warblade", ability_scores={"DEX": 10})
    base.classes = [("Warblade", 5)]
    baseline = compute_derived_stats(base)

    # compute_derived_stats reads the active stances from character.maneuvers,
    # as it does buffs and equipped magic items.
    base.maneuvers = [_maneuver("Punishing Stance", True)]
    stanced = compute_derived_stats(base)

    assert stanced.armor_class == baseline.armor_class - 2
    assert stanced.touch_ac == baseline.touch_ac - 2
    assert stanced.flat_footed_ac == baseline.flat_footed_ac - 2
    # Punishing Stance carries no save penalty, so every save is untouched.
    assert stanced.reflex == baseline.reflex
    assert stanced.fortitude == baseline.fortitude
    assert stanced.will == baseline.will


@pytest.fixture()
def custom_catalogue(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Return a setter that swaps the stance catalogue the pipeline reads."""
    import heroforge.logic.maneuvers as maneuvers_module

    def install(*effects: StanceEffect) -> None:
        monkeypatch.setattr(maneuvers_module, "STANCE_EFFECTS", effects)

    return install


def _buff(name: str, bonus_type: str, target: str, amount: int) -> dict:  # type: ignore[type-arg]
    return {
        "id": name,
        "name": name,
        "bonus_type": bonus_type,
        "target_stat": target,
        "amount": amount,
    }


def test_stance_bonuses_stack_with_buffs_by_type(custom_catalogue) -> None:  # type: ignore[no-untyped-def]
    """Stance bonuses share the PHB p176 stacking with buffs and items."""
    custom_catalogue(
        StanceEffect("Test Stance", 2, KIND_SAVE, "Will", bonus_type="morale"),
        StanceEffect("Test Stance", 1, KIND_AC, "AC", bonus_type="deflection"),
        StanceEffect("Test Stance", 1, KIND_AC, "AC", bonus_type="dodge"),
        StanceEffect("Test Stance", 1, KIND_SAVE, "Reflex"),
    )
    character = Character(name="Warblade", ability_scores={"DEX": 10})
    character.classes = [("Warblade", 5)]
    character.buffs = [
        _buff("Heroism", "morale", "Will", 2),
        _buff("Shield of Faith", "deflection", "AC", 2),
        _buff("Haste", "dodge", "AC", 1),
        _buff("Luck", "luck", "Reflex", 1),
    ]
    buffed = compute_derived_stats(character)

    character.maneuvers = [_maneuver("Test Stance", True)]
    stanced = compute_derived_stats(character)

    # +2 morale on Will does not stack with Heroism's +2 morale.
    assert stanced.will == buffed.will
    # +1 deflection is overlapped by Shield of Faith's +2; +1 dodge stacks.
    assert stanced.armor_class == buffed.armor_class + 1
    # Untyped bonuses always stack.
    assert stanced.reflex == buffed.reflex + 1


def test_stance_bonus_stacks_with_magic_item_by_type(custom_catalogue) -> None:  # type: ignore[no-untyped-def]
    """A larger stance bonus replaces, not adds to, an item's same-type bonus."""
    custom_catalogue(
        StanceEffect("Test Stance", 3, KIND_SAVE, "Fortitude", bonus_type="resistance"),
    )
    character = Character(name="Warblade")
    character.equipment = [
        {
            "item_name": "Cloak of Resistance +1",
            "slot": "Shoulders",
            "equipped": True,
            "bonuses": [{"bonus_type": "resistance", "target": "Saves", "value": 1}],
        }
    ]
    worn = compute_derived_stats(character)
    character.maneuvers = [_maneuver("Test Stance", True)]
    stanced = compute_derived_stats(character)
    assert stanced.fortitude == worn.fortitude + 2  # max(3, 1), not 3 + 1
    assert stanced.reflex == worn.reflex


_RAT_FAMILIAR = {"companion_type": "familiar", "name": "Scratch", "creature": "Rat"}


def test_model_derived_stats_apply_active_stance(qapp: object) -> None:
    """CharacterModel.derived_stats() applies a stance alongside a familiar."""
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    model.character.classes = [("Warblade", 5)]
    model.character.companions = [dict(_RAT_FAMILIAR)]
    before = model.derived_stats()

    model.character.maneuvers = [_maneuver("Punishing Stance", True)]
    after = model.derived_stats()

    assert after.armor_class == before.armor_class - 2
    assert after.touch_ac == before.touch_ac - 2
    assert after.flat_footed_ac == before.flat_footed_ac - 2
    # The Rat familiar's +2 Fortitude is kept; Punishing Stance has no save
    # penalty, so every save is unchanged.
    assert after.fortitude == before.fortitude
    assert after.reflex == before.reflex
    assert after.will == before.will

    model.character.maneuvers = [_maneuver("Punishing Stance", False)]
    assert model.derived_stats() == before


def test_model_stance_save_bonus_combines_with_familiar(
    qapp: object, custom_catalogue  # type: ignore[no-untyped-def]
) -> None:
    """An untyped stance save bonus adds to the familiar's untyped bonus."""
    from heroforge.ui.main_window import CharacterModel

    custom_catalogue(StanceEffect("Test Stance", 1, KIND_SAVE, "Fortitude"))
    model = CharacterModel()
    model.character.companions = [dict(_RAT_FAMILIAR)]
    familiar_only = model.derived_stats().fortitude
    model.character.companions = []
    assert model.derived_stats().fortitude == familiar_only - 2

    model.character.companions = [dict(_RAT_FAMILIAR)]
    model.character.maneuvers = [_maneuver("Test Stance", True)]
    assert model.derived_stats().fortitude == familiar_only + 1
