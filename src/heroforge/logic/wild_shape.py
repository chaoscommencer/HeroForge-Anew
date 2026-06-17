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
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from heroforge.db.data_access import Creature

# Persisted ``companion_type`` discriminator for the active Wild Shape form.
COMPANION_TYPE = "wild_shape"

# Physical ability scores replaced by the new form (PHB p37).  Mental scores
# (INT/WIS/CHA) are retained from the character.
PHYSICAL_ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON")

# Class whose levels grant and govern Wild Shape (PHB p37).
_DRUID_CLASS = "druid"


# ---------------------------------------------------------------------------
# Size helpers
# ---------------------------------------------------------------------------

_SIZE_ORDER = [
    "Fine",
    "Diminutive",
    "Tiny",
    "Small",
    "Medium",
    "Large",
    "Huge",
    "Gargantuan",
    "Colossal",
]


def _size_rank(size: str) -> int:
    try:
        return _SIZE_ORDER.index(size)
    except ValueError:
        return _SIZE_ORDER.index("Medium")


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


def available_forms(
    druid_level: int,
    all_creatures: Sequence[Creature] | Sequence[Mapping[str, Any]],
) -> list[Any]:
    """Return the creatures the druid can assume with Wild Shape.

    Unlocking by Druid level (PHB p37):
    - Level  5: Small and Medium Animals
    - Level  6: Large Animals
    - Level  7: Tiny Animals
    - Level  8: Plants (Small–Medium)
    - Level  9: Huge Animals
    - Level 11: Elementals (Small–Large)
    - Level 12: Small and Medium Magical Beasts

    Args:
        druid_level:   The character's Druid class level.
        all_creatures: Creature catalogue entries (objects exposing ``type``
                       and ``size`` attributes, or mappings with those keys).

    Returns:
        Filtered list of creatures the druid may Wild Shape into, preserving
        the input order.
    """
    if druid_level < 5:
        return []

    result: list[Any] = []
    for creature in all_creatures:
        ctype = _creature_type(creature)
        rank = _size_rank(_creature_size(creature))

        if ctype == "animal":
            # Small (rank 3) and Medium (rank 4) from level 5
            if druid_level >= 5 and 3 <= rank <= 4:
                result.append(creature)
            # Large (rank 5) from level 6
            elif druid_level >= 6 and rank == 5:
                result.append(creature)
            # Tiny (rank 2) from level 7
            elif druid_level >= 7 and rank == 2:
                result.append(creature)
            # Huge (rank 6) from level 9
            elif druid_level >= 9 and rank == 6:
                result.append(creature)

        elif ctype == "plant":
            # Small and Medium plants from level 8
            if druid_level >= 8 and 3 <= rank <= 4:
                result.append(creature)

        elif ctype == "elemental":
            # Small–Large elementals from level 11
            if druid_level >= 11 and 3 <= rank <= 5:
                result.append(creature)

        elif ctype in ("magical beast", "magical_beast"):
            # Small and Medium magical beasts from level 12
            if druid_level >= 12 and 3 <= rank <= 4:
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
