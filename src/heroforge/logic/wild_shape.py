"""Wild Shape calculations for Druid characters in HeroForge-Anew.

Reference: PHB p37 (Druid class feature), MM appendix (creature stats).

Wild Shape is a polymorph effect: while active the druid gains the new form's
size, physical ability scores (Strength, Dexterity, Constitution) and natural
armor, while retaining their own mental scores (Intelligence, Wisdom, Charisma).
The form is chosen from the seeded ``creatures`` catalogue and persisted on the
character as a single ``companion_type == "wild_shape"`` entry so it round-trips
through save/load like the Animal Companion and Familiar (Excel tab 9d).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from heroforge.logic.natural_attacks import NaturalAttack, parse_natural_attacks

if TYPE_CHECKING:  # pragma: no cover - typing-only
    from heroforge.db.data_access import Creature

# Persisted ``companion_type`` discriminator for the active Wild Shape form.
COMPANION_TYPE = "wild_shape"

# Physical ability scores replaced by the new form (PHB p37).  Mental scores
# (INT/WIS/CHA) are retained from the character.
PHYSICAL_ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON")

# Class whose levels grant and govern Wild Shape (PHB p37).
_DRUID_CLASS = "druid"

_LEADING_INT = re.compile(r"\s*(\d+)")


# ---------------------------------------------------------------------------
# Creature accessors
# ---------------------------------------------------------------------------


def _creature_type(creature: Creature | Mapping[str, Any]) -> str:
    """Return the lower-cased creature type for *creature* (object or mapping)."""
    if isinstance(creature, Mapping):
        return str(creature.get("type", "")).strip().lower()
    return str(getattr(creature, "type", "")).strip().lower()


def _creature_size(creature: Creature | Mapping[str, Any]) -> str:
    """Return the size category for *creature* (object or mapping)."""
    if isinstance(creature, Mapping):
        return str(creature.get("size", "Medium")).strip()
    return str(getattr(creature, "size", "Medium")).strip()


def creature_hit_dice(creature: Creature | Mapping[str, Any]) -> int | None:
    """Return the number of Hit Dice of *creature*, or ``None`` if unrecorded.

    Reads the leading integer of the ``hit_dice`` text, so both the seeded
    plain count (``"12"``) and a full expression (``"12d8+51"``) work.
    """
    if isinstance(creature, Mapping):
        text = str(creature.get("hit_dice", "") or "")
    else:
        text = str(getattr(creature, "hit_dice", "") or "")
    match = _LEADING_INT.match(text)
    return int(match.group(1)) if match else None


def _creature_ability_scores(
    creature: Creature | Mapping[str, Any],
) -> dict[str, int]:
    """Return the form's ability scores keyed ``STR``/``DEX``/``CON``/…

    Accepts either a :class:`~heroforge.db.data_access.Creature` (which exposes
    an ``ability_scores`` mapping) or a raw mapping using either the
    ``ability_scores`` sub-mapping or flat ``str_score``/``dex_score``/… keys.
    """
    if isinstance(creature, Mapping):
        scores = creature.get("ability_scores")
        if isinstance(scores, Mapping):
            return {str(k): int(v) for k, v in scores.items()}
        return {
            "STR": int(creature.get("str_score", 10)),
            "DEX": int(creature.get("dex_score", 10)),
            "CON": int(creature.get("con_score", 10)),
            "INT": int(creature.get("int_score", 10)),
            "WIS": int(creature.get("wis_score", 10)),
            "CHA": int(creature.get("cha_score", 10)),
        }
    scores = getattr(creature, "ability_scores", {})
    return {str(k): int(v) for k, v in dict(scores).items()}


# ---------------------------------------------------------------------------
# Druid level / form availability
# ---------------------------------------------------------------------------


def druid_wild_shape_level(classes: Iterable[tuple[str, int]]) -> int:
    """Return the Druid class level that governs Wild Shape (PHB p37).

    Wild Shape is a Druid class feature; only levels in the Druid class count
    toward the form-unlock table.  Returns ``0`` when the character has no
    Druid levels.

    Args:
        classes: ``(class_name, level)`` pairs for the character.

    Returns:
        The total Druid class level.
    """
    return sum(
        int(level)
        for name, level in classes
        if str(name).strip().lower() == _DRUID_CLASS
    )


# Minimum Druid level at which Wild Shape unlocks each size of a form type
# (PHB p37 Druid table; workbook ``'Class Abilities'!H33:J41``
# ``TblWildshapeSizes`` and ``M33:N46`` ``TblWildshapeForms``).  Plant forms
# (12th level) follow the same size restrictions as animals; elementals have
# their own progression.  Types absent from this table (e.g. magical beasts,
# which only the Magical Beast Wild Shape feat grants) are never available
# from Druid levels alone.
_ANIMAL_SIZE_LEVELS: Mapping[str, int] = {
    "Small": 5,
    "Medium": 5,
    "Large": 8,
    "Tiny": 11,
    "Huge": 15,
}
_ELEMENTAL_SIZE_LEVELS: Mapping[str, int] = {
    "Small": 16,
    "Medium": 16,
    "Large": 16,
    "Huge": 20,
}
FORM_UNLOCK_LEVELS: Mapping[str, tuple[int, Mapping[str, int]]] = {
    "animal": (5, _ANIMAL_SIZE_LEVELS),
    "plant": (12, _ANIMAL_SIZE_LEVELS),
    "elemental": (16, _ELEMENTAL_SIZE_LEVELS),
}
"""Creature type → (type unlock level, size → unlock level) for Wild Shape."""


def form_unlock_level(creature: Creature | Mapping[str, Any]) -> int | None:
    """Return the Druid level at which *creature* becomes a Wild Shape form.

    The form must be of an allowed type (animal, plant or elemental) and size
    (PHB p37); the result is the later of the type's and the size's unlock
    level.  Returns ``None`` when Druid levels alone never allow the form.
    """
    entry = FORM_UNLOCK_LEVELS.get(_creature_type(creature))
    if entry is None:
        return None
    type_level, size_levels = entry
    size_level = size_levels.get(_creature_size(creature).capitalize())
    if size_level is None:
        return None
    return max(type_level, size_level)


def available_forms(
    druid_level: int,
    all_creatures: Sequence[Creature] | Sequence[Mapping[str, Any]],
) -> list[Any]:
    """Return the creatures the druid can assume with Wild Shape.

    Unlocking by Druid level (PHB p37; see :data:`FORM_UNLOCK_LEVELS`):

    - Level  5: Small and Medium animals
    - Level  8: Large animals
    - Level 11: Tiny animals
    - Level 12: plants, with the same size limits as animals
    - Level 15: Huge animals (and plants)
    - Level 16: Small, Medium and Large elementals
    - Level 20: Huge elementals

    Magical beasts are never available from Druid levels alone.  The form's
    Hit Dice cannot exceed the Druid level, and a form with no recorded Hit
    Dice is never offered (PHB p37; workbook ``WildShapeHDLimit`` and the
    ``'Creature Info'`` "Wild Shape Available" column).

    Args:
        druid_level:   The character's Druid class level.
        all_creatures: Creature catalogue entries (objects exposing ``type``,
                       ``size`` and ``hit_dice`` attributes, or mappings with
                       those keys).

    Returns:
        Filtered list of creatures the druid may Wild Shape into, preserving
        the input order.
    """
    result: list[Any] = []
    for creature in all_creatures:
        unlock = form_unlock_level(creature)
        if unlock is None or druid_level < unlock:
            continue
        hit_dice = creature_hit_dice(creature)
        if hit_dice is None or hit_dice > druid_level:
            continue
        result.append(creature)
    return result


# ---------------------------------------------------------------------------
# Stat replacement
# ---------------------------------------------------------------------------


def apply_wild_shape(
    base_scores: Mapping[str, int],
    creature: Creature | Mapping[str, Any],
) -> dict[str, int]:
    """Return *base_scores* with the form's physical ability scores applied.

    Rules (PHB p37):
    - STR, DEX, CON are replaced by the creature's scores.
    - INT, WIS, CHA are retained from the character.

    Args:
        base_scores: The character's current ability scores.
        creature:    The form being assumed.

    Returns:
        New ability score dict after transformation.
    """
    result = dict(base_scores)
    form = _creature_ability_scores(creature)
    for ability in PHYSICAL_ABILITIES:
        result[ability] = int(form.get(ability, result.get(ability, 10)))
    return result


def wild_shape_ability_adjustments(
    base_scores: Mapping[str, int],
    creature: Creature | Mapping[str, Any],
) -> dict[str, int]:
    """Return STR/DEX/CON deltas that replace the character's physical scores.

    :func:`heroforge.logic.derived_stats.compute_derived_stats` applies ability
    *adjustments* additively on top of the base scores, so to make the effective
    physical scores equal the form's, the adjustment for each physical ability is
    ``form_score - base_score`` (PHB p37 polymorph: the druid gains the new
    form's physical ability scores while keeping their mental scores).

    Args:
        base_scores: The character's pre-transformation ability scores.
        creature:    The form being assumed.

    Returns:
        Mapping of ``"STR"``/``"DEX"``/``"CON"`` to the additive delta.
    """
    form = _creature_ability_scores(creature)
    return {
        ability: int(form.get(ability, base_scores.get(ability, 10)))
        - int(base_scores.get(ability, 10))
        for ability in PHYSICAL_ABILITIES
    }


def revert_wild_shape(original_scores: Mapping[str, int]) -> dict[str, int]:
    """Return a copy of *original_scores* (Wild Shape ended, PHB p37)."""
    return dict(original_scores)


@dataclass(frozen=True)
class FormEffects:
    """What an active Wild Shape form replaces on the druid (PHB p37).

    These are *replacements*, not typed bonuses: the form's size, physical
    ability scores (as deltas over the base scores, see
    :func:`wild_shape_ability_adjustments`), natural armor and land speed take
    the place of the character's own.  Bonuses that still apply in the new form
    (enhancement bonuses from buffs, items, stances, vestiges, auras, a
    natural-armor enhancement and so on) keep flowing through the typed
    stacking path in :mod:`heroforge.logic.derived_stats`.
    """

    form: str
    """Name of the creature whose form is assumed."""
    size: str
    """Size category of the form."""
    ability_adjustments: Mapping[str, int]
    """STR/DEX/CON deltas that make the effective scores equal the form's."""
    natural_armor: int
    """The form's natural armor bonus, replacing the race's."""
    land_speed: int
    """The form's land speed in feet (0 when the form has none)."""
    natural_attacks: tuple[NaturalAttack, ...] = ()
    """The form's natural attacks, replacing the race's (workbook
    ``'Class Weapons & Armor'!BK20`` swaps ``RaceAttacks`` for
    ``WildShapeAttacks``)."""


def creature_land_speed(creature: Creature | Mapping[str, Any]) -> int:
    """Return *creature*'s land speed in feet, ``0`` when none is recorded.

    Reads the leading integer of the ``speed`` text: the seeded ``Land`` value
    (``"50"``) or a stat-block style string (``"10 ft., fly 60 ft."``).  A form
    with no land speed (an air elemental only flies) has a land speed of 0.
    """
    if isinstance(creature, Mapping):
        text = str(creature.get("speed", "") or "")
    else:
        text = str(getattr(creature, "speed", "") or "")
    match = _LEADING_INT.match(text)
    return int(match.group(1)) if match else 0


def form_effects(
    base_scores: Mapping[str, int],
    creature: Creature | Mapping[str, Any],
) -> FormEffects:
    """Return the :class:`FormEffects` of assuming *creature*'s form.

    Args:
        base_scores: The character's pre-transformation ability scores.
        creature:    The form being assumed.
    """
    if isinstance(creature, Mapping):
        name = str(creature.get("name", ""))
        natural_armor = creature.get("natural_armor", 0)
        attacks = creature.get("natural_attacks", "")
    else:
        name = str(getattr(creature, "name", ""))
        natural_armor = getattr(creature, "natural_armor", 0)
        attacks = getattr(creature, "natural_attacks", "")
    return FormEffects(
        form=name,
        size=_creature_size(creature) or "Medium",
        ability_adjustments=wild_shape_ability_adjustments(base_scores, creature),
        natural_armor=int(natural_armor or 0),
        land_speed=creature_land_speed(creature),
        natural_attacks=tuple(parse_natural_attacks(str(attacks or ""))),
    )


# ---------------------------------------------------------------------------
# Persistence helpers (character.companions)
# ---------------------------------------------------------------------------


def active_form_name(companions: Iterable[Mapping[str, Any]]) -> str | None:
    """Return the active Wild Shape form's creature name, or ``None``.

    Scans the character's ``companions`` for the ``wild_shape`` entry and
    returns its ``creature`` only when the form is flagged active in the
    JSON-encoded ``notes`` column.  Returns ``None`` when no form is selected,
    the form is inactive, or the notes cannot be parsed.

    Args:
        companions: The character's ``companions`` list.

    Returns:
        The active form's creature name, or ``None``.
    """
    for entry in companions:
        if entry.get("companion_type") != COMPANION_TYPE:
            continue
        name = str(entry.get("creature", "")).strip()
        if not name:
            return None
        notes = entry.get("notes", "")
        try:
            data = json.loads(notes) if notes else {}
        except (TypeError, ValueError):
            data = {}
        if isinstance(data, Mapping) and bool(data.get("active", False)):
            return name
        return None
    return None
