"""Wild Shape calculations for Druid characters in HeroForge-Anew.

Reference: PHB p37 (Druid class feature), MM appendix (creature stats).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Wild Shape availability by Druid level
# ---------------------------------------------------------------------------

# Each entry: (min_druid_level, criteria_function_or_description)
# Criteria functions take a creature dict and return True if usable.
# PHB p37: Wild Shape unlocks progressively.


def _creature_type(creature: dict) -> str:  # type: ignore[type-arg]
    return str(creature.get("type", "")).strip().lower()


def _creature_size(creature: dict) -> str:  # type: ignore[type-arg]
    return str(creature.get("size", "Medium")).strip()


_SIZE_ORDER = ["Fine", "Diminutive", "Tiny", "Small", "Medium", "Large", "Huge",
               "Gargantuan", "Colossal"]


def _size_rank(size: str) -> int:
    try:
        return _SIZE_ORDER.index(size)
    except ValueError:
        return _SIZE_ORDER.index("Medium")


def available_forms(druid_level: int, all_creatures: list[dict]) -> list[dict]:  # type: ignore[type-arg]
    """Return a list of creature dicts the druid can assume with Wild Shape.

    Unlocking by Druid level (PHB p37):
    - Level  5: Small and Medium Animals
    - Level  6: Large Animals
    - Level  7: Tiny Animals
    - Level  8: Plants (Small–Medium)
    - Level  9: Huge Animals
    - Level 11: Elementals (Small–Large, 1/day; Medium–Large at 16th)
    - Level 12: Small and Medium Magical Beasts

    Args:
        druid_level:   Character's Druid class level.
        all_creatures: List of creature dicts with at least ``'type'``,
                       ``'size'``, and ``'subtype'`` keys.

    Returns:
        Filtered list of creature dicts the druid may Wild Shape into.
    """
    if druid_level < 5:
        return []

    result = []
    for creature in all_creatures:
        ctype = _creature_type(creature)
        size = _creature_size(creature)
        rank = _size_rank(size)

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


def apply_wild_shape(
    base_scores: dict[str, int],
    creature: dict,  # type: ignore[type-arg]
) -> dict[str, int]:
    """Apply Wild Shape transformation to a character's ability scores.

    Rules (PHB p37):
    - STR, DEX, CON are replaced by the creature's scores.
    - INT, WIS, CHA are retained from the character.

    Args:
        base_scores: Character's current ability scores (STR/DEX/CON/INT/WIS/CHA).
        creature:    Creature dict with ``'str_score'``, ``'dex_score'``,
                     and ``'con_score'`` keys.

    Returns:
        New ability score dict after transformation.
    """
    result = dict(base_scores)
    result["STR"] = int(creature.get("str_score", base_scores.get("STR", 10)))
    result["DEX"] = int(creature.get("dex_score", base_scores.get("DEX", 10)))
    result["CON"] = int(creature.get("con_score", base_scores.get("CON", 10)))
    return result


def revert_wild_shape(original_scores: dict[str, int]) -> dict[str, int]:
    """Revert ability scores to original values after Wild Shape ends.

    Args:
        original_scores: The character's pre-transformation ability scores.

    Returns:
        A copy of *original_scores* (no modifications needed).
    """
    return dict(original_scores)
