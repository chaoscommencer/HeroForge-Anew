"""Buff / bonus stacking calculations for HeroForge-Anew.

Reference: PHB p176 (Bonus Types and Stacking).
"""

from __future__ import annotations

# Bonus types that stack with themselves and with everything else.
STACKABLE_BONUS_TYPES: set[str] = {"dodge", "circumstance", "racial", "untyped"}


def stacks_with(type_a: str, type_b: str) -> bool:
    """Return ``True`` if bonuses of *type_a* and *type_b* stack.

    Dodge, circumstance, racial, and untyped bonuses stack with all other
    bonuses (including the same type).  All other named bonus types
    (enhancement, morale, sacred, profane, etc.) do not stack with
    themselves.

    Reference: PHB p176.

    Args:
        type_a: First bonus type (case-insensitive).
        type_b: Second bonus type (case-insensitive).

    Returns:
        ``True`` if the bonuses stack.
    """
    ta = type_a.lower()
    tb = type_b.lower()
    if ta in STACKABLE_BONUS_TYPES or tb in STACKABLE_BONUS_TYPES:
        return True
    # Two named bonuses of the same non-stackable type do NOT stack.
    return ta != tb


def apply_buff(
    current_bonuses: dict[str, dict[str, int]],
    buff_name: str,
    bonus_type: str,
    stat: str,
    amount: int,
) -> dict[str, dict[str, int]]:
    """Record a buff's bonus to a stat.

    The structure is ``{stat: {buff_name: amount}}``.  Multiple buffs to
    the same stat are kept so that :func:`effective_bonus` can properly
    handle stacking rules.

    Reference: PHB p176.

    Args:
        current_bonuses: Existing bonus tracking dict (mutated and returned).
        buff_name:       Unique buff identifier (e.g. ``'Bless'``).
        bonus_type:      Bonus type string (e.g. ``'morale'``).
        stat:            Stat being buffed (e.g. ``'attack'``, ``'AC'``).
        amount:          Bonus amount (can be negative for penalties).

    Returns:
        Updated *current_bonuses* dict.
    """
    key = f"{buff_name}::{bonus_type}"
    if stat not in current_bonuses:
        current_bonuses[stat] = {}
    current_bonuses[stat][key] = amount
    return current_bonuses


def remove_buff(
    current_bonuses: dict[str, dict[str, int]],
    buff_name: str,
) -> dict[str, dict[str, int]]:
    """Remove all bonuses contributed by *buff_name*.

    Args:
        current_bonuses: Existing bonus tracking dict (mutated and returned).
        buff_name:       Unique buff identifier to remove.

    Returns:
        Updated *current_bonuses* dict.
    """
    for stat in current_bonuses:
        keys_to_remove = [
            k for k in current_bonuses[stat] if k.startswith(f"{buff_name}::")
        ]
        for k in keys_to_remove:
            del current_bonuses[stat][k]
    return current_bonuses


def effective_bonus(bonuses: dict[str, dict[str, int]], stat: str) -> int:
    """Calculate the net bonus to *stat* after applying stacking rules.

    For each bonus type:
    - Stackable types (dodge, circumstance, racial, untyped): sum all bonuses.
    - Non-stackable types: take only the highest value.

    Reference: PHB p176.

    Args:
        bonuses: Bonus tracking dict ``{stat: {buff_key: amount}}``.
        stat:    The stat to compute the net bonus for.

    Returns:
        Total effective bonus.
    """
    stat_bonuses = bonuses.get(stat, {})
    # Group by bonus type
    by_type: dict[str, list[int]] = {}
    for key, amount in stat_bonuses.items():
        # key format: "BuffName::type"
        parts = key.split("::", 1)
        btype = parts[1].lower() if len(parts) == 2 else "untyped"
        by_type.setdefault(btype, []).append(amount)

    total = 0
    for btype, amounts in by_type.items():
        if btype in STACKABLE_BONUS_TYPES:
            total += sum(amounts)
        else:
            total += max(amounts)
    return total


def temporary_hp_total(temp_hp_grants: list[int]) -> int:
    """Return effective temporary HP from multiple sources.

    Temporary HP from different sources do NOT stack; only the highest
    value applies.  Reference: PHB p146.

    Args:
        temp_hp_grants: List of temporary HP amounts from various sources.

    Returns:
        Highest temporary HP value, or 0 if the list is empty.
    """
    return max(temp_hp_grants, default=0)
