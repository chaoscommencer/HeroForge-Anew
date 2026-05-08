"""Psionic power calculations for HeroForge-Anew.

Reference: Expanded Psionics Handbook (XPH) Chapters 2–3.
"""

from __future__ import annotations


def power_points_per_day(
    class_levels: dict[str, int],
    key_ability_mod: int,
    pp_tables: dict[str, list[int]],
) -> int:
    """Calculate total power points per day.

    Each manifesting class provides a number of power points based on class
    level (looked up in *pp_tables*).  The key ability modifier adds bonus
    power points equal to PP gained from each manifester class level × modifier
    (approximate; see XPH p19 for exact bonus PP table).

    Reference: XPH p19 (power points per day table).

    Args:
        class_levels:   Mapping of class name → levels in that class.
        key_ability_mod: Relevant ability modifier (INT for Psion, WIS for Ardent, etc.).
        pp_tables:       Mapping of class name → list of PP values indexed by level-1.

    Returns:
        Total power points per day.
    """
    total = 0
    for cls, lvl in class_levels.items():
        table = pp_tables.get(cls, [])
        if lvl > 0 and table:
            idx = min(lvl - 1, len(table) - 1)
            class_pp = table[idx]
            # Bonus PP from high ability: key_ability_mod × manifester_level (simplified)
            bonus_pp = max(0, key_ability_mod) * lvl
            total += class_pp + bonus_pp
    return total


def manifester_level(class_levels: dict[str, int]) -> int:
    """Return the highest single-class manifester level.

    For characters with multiple manifesting classes, the highest class level
    is used.  Reference: XPH p19.

    Args:
        class_levels: Mapping of class name → levels.

    Returns:
        Highest manifester level (or 0 if no psionic classes).
    """
    return max(class_levels.values(), default=0)


def augment_cost(base_cost: int, augment_count: int, cost_per_augment: int) -> int:
    """Calculate total power point cost after augmenting a power.

    Reference: XPH p19 (Augment descriptions in power listings).

    Args:
        base_cost:        Base power point cost of the power.
        augment_count:    Number of times the power is augmented.
        cost_per_augment: Additional PP cost per augmentation.

    Returns:
        Total PP cost.
    """
    return base_cost + augment_count * cost_per_augment
