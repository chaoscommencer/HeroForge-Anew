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

from heroforge.logic import buffs, combat, equipment, saving_throws
from heroforge.logic.ability_scores import ability_modifier
from heroforge.logic.health import hit_dice_sequence, max_hit_points

if TYPE_CHECKING:
    from heroforge.models.character import Character

_ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

# Maps a buff's ``target_stat`` (case-insensitive) onto an ability key so that
# ability-boosting buffs (e.g. Bull's Strength) feed the effective scores.
_BUFF_ABILITY_ALIASES: Mapping[str, str] = {
    "str": "STR",
    "strength": "STR",
    "dex": "DEX",
    "dexterity": "DEX",
    "con": "CON",
    "constitution": "CON",
    "int": "INT",
    "intelligence": "INT",
    "wis": "WIS",
    "wisdom": "WIS",
    "cha": "CHA",
    "charisma": "CHA",
}

# Maps a buff's ``target_stat`` onto the canonical derived-stat keys it affects.
# A single target may fan out to several keys (e.g. a generic "attack" buff
# touches both melee and ranged; "saves" touches all three saving throws).
_BUFF_STAT_ALIASES: Mapping[str, tuple[str, ...]] = {
    "attack": ("melee", "ranged"),
    "attacks": ("melee", "ranged"),
    "attack bonus": ("melee", "ranged"),
    "to hit": ("melee", "ranged"),
    "melee": ("melee",),
    "melee attack": ("melee",),
    "ranged": ("ranged",),
    "ranged attack": ("ranged",),
    "ac": ("ac",),
    "armor class": ("ac",),
    "armour class": ("ac",),
    "armor_class": ("ac",),
    "fort": ("fort",),
    "fortitude": ("fort",),
    "ref": ("ref",),
    "reflex": ("ref",),
    "will": ("will",),
    "save": ("fort", "ref", "will"),
    "saves": ("fort", "ref", "will"),
    "saving throw": ("fort", "ref", "will"),
    "saving throws": ("fort", "ref", "will"),
    "all saves": ("fort", "ref", "will"),
    "initiative": ("initiative",),
    "init": ("initiative",),
    "grapple": ("grapple",),
    "hp": ("hp",),
    "hit points": ("hp",),
    "hit_points": ("hp",),
}


def _canonical_buff_targets(target: str) -> tuple[str, ...]:
    """Resolve a buff's free-form ``target_stat`` to canonical stat keys."""
    key = target.strip().lower()
    if key in _BUFF_ABILITY_ALIASES:
        return (_BUFF_ABILITY_ALIASES[key],)
    return _BUFF_STAT_ALIASES.get(key, ())


def _buff_bonus_sources(
    character: Character,
) -> tuple[dict[str, int], list[tuple[str, int]]]:
    """Aggregate the typed bonuses of active buffs and equipped magic items.

    Returns ``(net, ac_bonuses)`` where *net* maps canonical derived-stat keys
    (ability scores plus ``melee``/``ranged``/``fort``/``ref``/``will``/
    ``initiative``/``grapple``/``hp``) to their net bonus after stacking, and
    *ac_bonuses* is a list of ``(bonus_type, amount)`` pairs routed through the
    armor-class aggregator so AC bonuses stack with armor/shield sources by type.

    Buffs and magic items are stacked together, so a Bull's Strength (+4
    enhancement) and Gauntlets of ogre power (+2 enhancement) give +4, not +6.

    Reference: PHB p176 (bonus types and stacking).
    """
    records: list[tuple[str, str, str, int]] = []
    ac_bonuses: list[tuple[str, int]] = []

    def add(source: str, bonus_type: object, target: object, amount: int) -> None:
        target_text = str(target or "")
        if amount == 0 or not target_text.strip():
            return
        btype = str(bonus_type or "untyped").strip() or "untyped"
        for canonical in _canonical_buff_targets(target_text):
            if canonical == "ac":
                ac_bonuses.append((btype, amount))
            else:
                records.append((source, btype, canonical, amount))

    for index, entry in enumerate(getattr(character, "buffs", None) or []):
        add(
            f"buff:{entry.get('id') or index}",
            entry.get("bonus_type"),
            entry.get("target_stat"),
            buffs.buff_amount(entry.get("amount")),
        )
    for index, item in enumerate(getattr(character, "equipment", None) or []):
        for spec in equipment.item_bonus_specs(item):
            add(
                f"item:{index}",
                spec.get("bonus_type"),
                spec.get("target"),
                buffs.buff_amount(spec.get("value")),
            )
    return buffs.aggregate_bonuses(records), ac_bonuses


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
    carried_weight: float = 0.0
    """Total weight of :attr:`Character.equipment`, in pounds (PHB p162)."""
    load: str = "Light"
    """Load category: ``Light``, ``Medium``, ``Heavy`` or ``Overloaded``."""
    load_check_penalty: int = 0
    """Check penalty from the load (0/-3/-6); does not stack with armor's."""
    speed: int = 30
    """Land speed in feet after worn armor and load (PHB p162)."""
    run_multiplier: int = 4
    """Run multiplier: ×4, or ×3 in heavy armor or under a heavy load."""


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
    weight_catalog: Mapping[str, float] | None = None,
    base_speed: int = 30,
    armor_type: str | None = None,
    speed_ignores_encumbrance: bool = False,
) -> DerivedStats:
    """Compute every derived combat/save value for *character*.

    The character's active :attr:`~heroforge.models.character.Character.buffs`
    and the bonus specs of equipped magic items in
    :attr:`~heroforge.models.character.Character.equipment` are aggregated
    together with the bonus-type stacking rules (PHB p176) and folded in:
    ability-score buffs adjust the effective scores, AC buffs join the
    armor-class aggregation by type, and the remaining typed bonuses are added to
    the relevant attack, save, initiative, grapple and hit-point readouts.

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
        weight_catalog: Optional item name → unit weight map used for equipment
                       entries stored without a weight.  The carried weight sets
                       the load (PHB p162); a medium or heavy load caps the
                       Dexterity bonus to AC at +3/+1 alongside *max_dex* and
                       sets :attr:`DerivedStats.load_check_penalty`.
        base_speed:    Base land speed in feet, usually the race's.
        armor_type:    Type of the worn body armor (``"Light"``, ``"Medium"``,
                       ``"Heavy"``), or ``None``.  Medium/heavy armor or a load
                       above light reduces :attr:`DerivedStats.speed`, and heavy
                       armor or load lowers the run multiplier
                       (:func:`heroforge.logic.equipment.encumbered_speed`).
        speed_ignores_encumbrance: Keep the full speed in armor and under load
                       (e.g. a dwarf, PHB p14).

    Returns:
        An immutable :class:`DerivedStats` snapshot.
    """
    progressions = progressions or {}
    save_bonuses = save_bonuses or {}
    adjustments = ability_adjustments or {}
    buff_net, buff_ac = _buff_bonus_sources(character)
    base_scores = character.ability_scores
    scores = {
        a: max(
            1,
            int(base_scores.get(a, 10))
            + int(adjustments.get(a, 0))
            + buff_net.get(a, 0),
        )
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
    ) + buff_net.get("hp", 0)

    capacity = combat.carrying_capacity(scores["STR"])
    carried = equipment.carried_weight(character.equipment or [], weight_catalog)
    load = equipment.encumbrance_category(carried, *capacity)
    load_max_dex, load_check_penalty = equipment.load_effects(load)
    if load_max_dex is not None:
        max_dex = load_max_dex if max_dex is None else min(max_dex, load_max_dex)
    speed, run_multiplier = equipment.encumbered_speed(
        base_speed,
        armor_type,
        load,
        ignore_encumbrance=speed_ignores_encumbrance,
    )

    combined_ac_bonuses = list(ac_bonuses or ())
    combined_ac_bonuses.extend(buff_ac)
    ac = combat.aggregate_armor_class(
        dex_mod, combined_ac_bonuses, size=size, max_dex=max_dex
    )

    return DerivedStats(
        ability_modifiers=mods,
        effective_ability_scores=MappingProxyType(dict(scores)),
        total_level=character.total_level,
        level_adjustment=level_adjustment,
        effective_character_level=character.total_level + level_adjustment,
        size=size,
        base_attack_bonus=bab,
        melee_attack=combat.melee_attack(
            bab, str_mod, size=size, misc=buff_net.get("melee", 0)
        ),
        ranged_attack=combat.ranged_attack(
            bab, dex_mod, size=size, misc=buff_net.get("ranged", 0)
        ),
        grapple=(
            combat.grapple_modifier(bab, str_mod, size=size)
            + buff_net.get("grapple", 0)
        ),
        initiative=combat.initiative(dex_mod, misc=buff_net.get("initiative", 0)),
        hit_points=hit_points,
        armor_class=ac.total,
        touch_ac=ac.touch,
        flat_footed_ac=ac.flat_footed,
        fortitude=saving_throws.fortitude(
            base_fort, con_mod, save_bonuses.get("fort", 0) + buff_net.get("fort", 0)
        ),
        reflex=saving_throws.reflex(
            base_ref, dex_mod, save_bonuses.get("ref", 0) + buff_net.get("ref", 0)
        ),
        will=saving_throws.will(
            base_will, wis_mod, save_bonuses.get("will", 0) + buff_net.get("will", 0)
        ),
        carrying_capacity=capacity,
        carried_weight=carried,
        load=load,
        load_check_penalty=load_check_penalty,
        speed=speed,
        run_multiplier=run_multiplier,
    )
