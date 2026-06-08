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

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from heroforge.logic import combat, saving_throws
from heroforge.logic.ability_scores import ability_modifier

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


@dataclass(frozen=True)
class DerivedStats:
    """A snapshot of every value the UI derives from a character.

    Reference: PHB Chapter 8 (combat) and PHB p141 (saves).
    """

    ability_modifiers: Mapping[str, int]
    total_level: int
    base_attack_bonus: int
    melee_attack: int
    ranged_attack: int
    grapple: int
    initiative: int
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
) -> DerivedStats:
    """Compute every derived combat/save value for *character*.

    Args:
        character:     The active character whose ability scores and class
                       levels drive the calculation.
        progressions:  Mapping of class name → :class:`ClassProgression`.
                       Classes absent from the mapping use the logic-layer
                       defaults (``medium`` BAB, ``poor`` saves).
        size:          Size category used for AC, attack, and grapple size
                       modifiers (PHB p149, p156).

    Returns:
        An immutable :class:`DerivedStats` snapshot.
    """
    progressions = progressions or {}
    scores = character.ability_scores
    mods: Mapping[str, int] = MappingProxyType(
        {a: ability_modifier(int(scores.get(a, 10))) for a in _ABILITIES}
    )
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

    return DerivedStats(
        ability_modifiers=mods,
        total_level=character.total_level,
        base_attack_bonus=bab,
        melee_attack=combat.melee_attack(bab, str_mod, size=size),
        ranged_attack=combat.ranged_attack(bab, dex_mod, size=size),
        grapple=combat.grapple_modifier(bab, str_mod, size=size),
        initiative=combat.initiative(dex_mod),
        armor_class=combat.armor_class(dex_mod, size=size),
        touch_ac=combat.touch_ac(dex_mod, size=size),
        flat_footed_ac=combat.flat_footed_ac(size=size),
        fortitude=saving_throws.fortitude(base_fort, con_mod),
        reflex=saving_throws.reflex(base_ref, dex_mod),
        will=saving_throws.will(base_will, wis_mod),
        carrying_capacity=combat.carrying_capacity(int(scores.get("STR", 10))),
    )
