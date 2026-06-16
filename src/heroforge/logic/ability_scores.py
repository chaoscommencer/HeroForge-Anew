"""Ability score calculations for HeroForge-Anew.

Reference: PHB p8, p307.
"""

from __future__ import annotations

from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Ability score modifier
# ---------------------------------------------------------------------------

# Point-buy cost table per score value. DMG p169.
_POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 6,
    15: 8,
    16: 10,
    17: 13,
    18: 16,
}


def ability_modifier(score: int) -> int:
    """Standard ability modifier formula: ``(score - 10) // 2``.

    Reference: PHB p8.

    Args:
        score: The raw ability score value.

    Returns:
        The corresponding ability modifier (can be negative).
    """
    return (score - 10) // 2


def apply_ability_drain(score: int, drain: int) -> int:
    """Reduce an ability score permanently by *drain* points.

    The score can be reduced to 0 (which has special consequences for
    each ability).  Reference: PHB p307.

    Args:
        score: Current ability score.
        drain: Amount of permanent drain to apply.

    Returns:
        The new ability score (minimum 0).
    """
    return max(0, score - drain)


def apply_ability_damage(score: int, damage: int) -> int:
    """Temporarily reduce an ability score by *damage* points.

    Ability score damage cannot reduce the effective score below 1.
    Reference: PHB p307.

    Args:
        score: Current ability score.
        damage: Amount of temporary damage to apply.

    Returns:
        The effective ability score after damage (minimum 1).
    """
    return max(1, score - damage)


def point_buy_cost(score: int) -> int:
    """Return the point-buy cost for a given starting ability score.

    Reference: DMG p169.

    Args:
        score: Desired starting score in the range 8–18.

    Returns:
        Point-buy cost for that score.

    Raises:
        ValueError: If *score* is outside the valid point-buy range.
    """
    if score not in _POINT_BUY_COSTS:
        raise ValueError(f"Score {score} is outside the valid point-buy range (8–18).")
    return _POINT_BUY_COSTS[score]


def total_point_buy_cost(scores: dict[str, int]) -> int:
    """Return the total point-buy cost for a set of ability scores.

    Args:
        scores: Mapping of ability name to score value (STR, DEX, …).

    Returns:
        Total point-buy points spent.

    Raises:
        ValueError: If any score is outside the valid range.
    """
    return sum(point_buy_cost(v) for v in scores.values())


def point_buy_spent(scores: Mapping[str, int]) -> int:
    """Return the point-buy points spent, tolerating out-of-range scores.

    Unlike :func:`total_point_buy_cost`, this never raises: scores below the
    point-buy minimum (8) cost nothing, and scores above the maximum (18) are
    treated as the most expensive entry. This makes it safe to call against the
    free-form ability spinboxes (which allow 1–100) when displaying a live
    point-buy summary against the configured budget.

    Reference: DMG p169.

    Args:
        scores: Mapping of ability name to score value (STR, DEX, …).

    Returns:
        Total point-buy points spent across all supplied scores.
    """
    lowest = min(_POINT_BUY_COSTS)
    highest = max(_POINT_BUY_COSTS)
    total = 0
    for value in scores.values():
        clamped = max(lowest, min(highest, value))
        total += _POINT_BUY_COSTS[clamped]
    return total
