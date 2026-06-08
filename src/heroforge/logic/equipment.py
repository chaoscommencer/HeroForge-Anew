"""Equipment and encumbrance calculations for HeroForge-Anew.

Reference: PHB p162 (Carrying Capacity), p123–126 (Equipment chapter).
"""

from __future__ import annotations


def total_weight(items: list[dict]) -> float:  # type: ignore[type-arg]
    """Calculate the total carried weight of a list of items.

    Each item dict should have ``'weight'`` (float, per unit) and
    ``'quantity'`` (int, defaults to 1) keys.

    Reference: PHB p162.

    Args:
        items: List of equipment item dicts.

    Returns:
        Total weight in pounds.
    """
    weight = 0.0
    for item in items:
        qty = float(item.get("quantity", 1))
        w = float(item.get("weight", 0.0))
        weight += w * qty
    return weight


def encumbrance_category(
    total_weight: float,
    light_max: int,
    medium_max: int,
) -> str:
    """Determine the encumbrance category for a character.

    Categories:
    - ``'Light'``:      total_weight ≤ light_max
    - ``'Medium'``:     light_max < total_weight ≤ medium_max
    - ``'Heavy'``:      medium_max < total_weight ≤ heavy_max (= 2 × medium_max)
    - ``'Overloaded'``: total_weight > heavy_max

    Reference: PHB p162.

    Args:
        total_weight: Character's carried weight in pounds.
        light_max:    Maximum weight for Light load.
        medium_max:   Maximum weight for Medium load.

    Returns:
        Encumbrance category string.
    """
    heavy_max = medium_max * 2
    if total_weight <= light_max:
        return "Light"
    if total_weight <= medium_max:
        return "Medium"
    if total_weight <= heavy_max:
        return "Heavy"
    return "Overloaded"


def armor_check_penalty(armor_acp: int, shield_acp: int) -> int:
    """Calculate combined armor check penalty from armor and shield.

    Both values are typically negative in the DB (negative impact on skill
    checks).  The function returns the sum.

    Reference: PHB p123.

    Args:
        armor_acp:  Armor's check penalty (e.g. -6 for Full Plate).
        shield_acp: Shield's check penalty (e.g. -1 for Light Shield).

    Returns:
        Combined armor check penalty (sum of both, typically ≤ 0).
    """
    return armor_acp + shield_acp


def enhancement_bonus(base_item: dict) -> int:  # type: ignore[type-arg]
    """Return the enhancement bonus of an item.

    Reads the ``'enhancement_bonus'`` key from the item dict; defaults to 0.

    Reference: PHB p217 (magic item descriptions).

    Args:
        base_item: Item dict (may or may not contain ``'enhancement_bonus'``).

    Returns:
        Enhancement bonus as an integer.
    """
    return int(base_item.get("enhancement_bonus", 0))
