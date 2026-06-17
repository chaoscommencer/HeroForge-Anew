"""Aggregated derived-stat calculations for HeroForge-Anew.

This module is the single place where the per-character :class:`Character`
model is turned into the combat and saving-throw values shown across the UI.
It composes the lower-level :mod:`heroforge.logic.combat`,
:mod:`heroforge.logic.saving_throws`, and :mod:`heroforge.logic.ability_scores`
modules so the UI never duplicates that math.

Design notes (see ``docs/conversion-plan.md`` §8.6):

* The result is an immutable :class:`DerivedStats` value object so callers can
  cache or compare snapshots safely.
* Class BAB/save progressions are supplied as a mapping of class name →
  :class:`ClassProgression`.  Classes missing from the mapping fall back to the
  library defaults (``medium`` BAB, ``poor`` saves), so the computation never
  raises when game data is unavailable (e.g. a fresh checkout before seeding).
* The function is deliberately pure: it has no Qt or database dependencies,
  which keeps it unit-testable and lets the database layer depend on it rather
  than the other way around.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from heroforge.logic import combat, saving_throws
from heroforge.logic.ability_scores import ability_modifier
from heroforge.logic.health import hit_dice_sequence, max_hit_points

if TYPE_CHECKING:
    from heroforge.models.character import Character

_ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


@dataclass(frozen=True)
class ClassProgression:
    """BAB and saving-throw progression types for a single class.

    Each field is one of the strings accepted by the underlying logic
    functions: ``bab`` is ``'fast'``/``'medium'``/``'slow'`` and the save
    fields are ``'good'``/``'poor'``.
    """

    name: str
    bab: str = "medium"
    fort: str = "poor"
    ref: str = "poor"
    will: str = "poor"
    hit_die: int = 8
    """Hit Die size for the class (PHB Chapter 3), used for HP calculation."""


@dataclass(frozen=True)
class DerivedStats:
    """A snapshot of every value the UI derives from a character.

    Reference: PHB Chapter 8 (combat) and PHB p141 (saves).
    """

    ability_modifiers: Mapping[str, int]
    effective_ability_scores: Mapping[str, int]
    total_level: int
    level_adjustment: int
    effective_character_level: int
    size: str
    base_attack_bonus: int
    melee_attack: int
    ranged_attack: int
    grapple: int
    initiative: int
    hit_points: int
    armor_class: int
    touch_ac: int
    flat_footed_ac: int
    fortitude: int
    reflex: int
    will: int
    carrying_capacity: tuple[int, int, int]


def _class_levels(character: Character) -> dict[str, int]:
    """Collapse a character's ordered class list into name → total levels."""
    levels: dict[str, int] = {}
    for name, lvl in character.classes:
        levels[name] = levels.get(name, 0) + lvl
    return levels


def compute_derived_stats(
    character: Character,
    progressions: Mapping[str, ClassProgression] | None = None,
    *,
    size: str = "Medium",
    save_bonuses: Mapping[str, int] | None = None,
    ability_adjustments: Mapping[str, int] | None = None,
    level_adjustment: int = 0,
    ac_bonuses: Sequence[tuple[str, int]] | None = None,
    max_dex: int | None = None,
    hp_flat_bonus: int = 0,
    hp_per_level_bonus: int = 0,
) -> DerivedStats:
    """Compute every derived combat/save value for *character*.

    Args:
        character:     The active character whose ability scores and class
                       levels drive the calculation.
        progressions:  Mapping of class name → :class:`ClassProgression`.
                       Classes absent from the mapping use the logic-layer
                       defaults (``medium`` BAB, ``poor`` saves, d8 Hit Die).
        size:          Size category used for AC, attack, and grapple size
                       modifiers (PHB p149, p156).  Usually the selected race's
                       size.
        save_bonuses:  Optional miscellaneous saving-throw bonuses keyed by the
                       short save keys ``"fort"``, ``"ref"``, ``"will"`` (e.g. a
                       standard familiar's master benefit).  Missing keys are
                       treated as ``0``.
        ability_adjustments: Optional per-ability adjustments (keyed ``"STR"`` …)
                       contributed by the race and any applied templates.  These
                       are added to the character's raw scores before any
                       modifier or carrying-capacity math, flooring each
                       resulting score at 1.
        level_adjustment: Total level adjustment (LA) from race + templates,
                       used to compute the effective character level
                       (``ECL = total class level + LA``; DMG p199).
        ac_bonuses:    Optional ``(bonus_type, value)`` AC sources — worn armor,
                       shield, natural armor, deflection, dodge, etc.  These are
                       aggregated by bonus type (PHB p150–151) into the armor
                       class, touch and flat-footed readouts.  Size and Dex are
                       applied automatically and must not be included here.
        max_dex:       Optional Max Dex Bonus cap from worn armor, applied to the
                       Dexterity contribution to AC.
        hp_flat_bonus: Flat hit-point bonus from feats/templates (e.g.
                       Toughness's +3).
        hp_per_level_bonus: Per-Hit-Die hit-point bonus from feats/templates
                       (e.g. Improved Toughness's +1 per Hit Die).

    Returns:
        An immutable :class:`DerivedStats` snapshot.
    """
    progressions = progressions or {}
    save_bonuses = save_bonuses or {}
    adjustments = ability_adjustments or {}
    base_scores = character.ability_scores
    scores = {
        a: max(1, int(base_scores.get(a, 10)) + int(adjustments.get(a, 0)))
        for a in _ABILITIES
    }
    mods_dict = {a: ability_modifier(scores[a]) for a in _ABILITIES}
    mods: Mapping[str, int] = MappingProxyType(mods_dict)
    str_mod, dex_mod = mods["STR"], mods["DEX"]
    con_mod, wis_mod = mods["CON"], mods["WIS"]

    class_levels = _class_levels(character)
    bab_progressions = {
        name: progressions[name].bab for name in class_levels if name in progressions
    }
    save_progressions = {
        name: {
            "fort": progressions[name].fort,
            "ref": progressions[name].ref,
            "will": progressions[name].will,
        }
        for name in class_levels
        if name in progressions
    }

    bab = combat.base_attack_bonus(class_levels, bab_progressions)
    base_fort = saving_throws.base_save(class_levels, "fort", save_progressions)
    base_ref = saving_throws.base_save(class_levels, "ref", save_progressions)
    base_will = saving_throws.base_save(class_levels, "will", save_progressions)

    hit_die_lookup = {name: prog.hit_die for name, prog in progressions.items()}
    hit_dice = hit_dice_sequence(character.classes, hit_die_lookup)
    computed_hit_points = max_hit_points(
        hit_dice,
        con_mod,
        flat_bonus=hp_flat_bonus,
        per_level_bonus=hp_per_level_bonus,
    )
    hit_points = (
        character.hit_points
        if character.hit_points is not None
        else computed_hit_points
    )

    ac = combat.aggregate_armor_class(
        dex_mod, ac_bonuses or (), size=size, max_dex=max_dex
    )

    return DerivedStats(
        ability_modifiers=mods,
        effective_ability_scores=MappingProxyType(dict(scores)),
        total_level=character.total_level,
        level_adjustment=level_adjustment,
        effective_character_level=character.total_level + level_adjustment,
        size=size,
        base_attack_bonus=bab,
        melee_attack=combat.melee_attack(bab, str_mod, size=size),
        ranged_attack=combat.ranged_attack(bab, dex_mod, size=size),
        grapple=combat.grapple_modifier(bab, str_mod, size=size),
        initiative=combat.initiative(dex_mod),
        hit_points=hit_points,
        armor_class=ac.total,
        touch_ac=ac.touch,
        flat_footed_ac=ac.flat_footed,
        fortitude=saving_throws.fortitude(
            base_fort, con_mod, save_bonuses.get("fort", 0)
        ),
        reflex=saving_throws.reflex(base_ref, dex_mod, save_bonuses.get("ref", 0)),
        will=saving_throws.will(base_will, wis_mod, save_bonuses.get("will", 0)),
        carrying_capacity=combat.carrying_capacity(scores["STR"]),
    )
