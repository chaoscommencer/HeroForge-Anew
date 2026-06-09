"""Hit-point calculations for HeroForge-Anew.

Ports the workbook's *Stats & Character Details* HP logic: a character's
maximum hit points are derived from the Hit Die of every class level taken,
the Constitution modifier (applied per Hit Die), and any flat HP-affecting
bonuses from feats or templates (e.g. Toughness).

Reference: PHB p145 (Hit Points / Hit Dice), DMG p198 (average HP).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# The default Hit Die used when a class has no recorded value.  Matches the
# ``Class.hit_die`` model default (a d8).
DEFAULT_HIT_DIE = 8

# Per-level HP methods understood by :func:`compute_hit_points`.
HP_METHOD_AVERAGE = "average"
HP_METHOD_MAX = "max"


def average_hit_die_value(die: int) -> int:
    """Return the average roll of a *die*-sided Hit Die, rounded up.

    The average of a dX is ``(X + 1) / 2``; HeroForge (like most tables that
    award fixed HP) rounds that up, e.g. d8 → 5, d10 → 6, d12 → 7, d6 → 4.

    Reference: DMG p198 (fixed/average hit points).

    Args:
        die: Number of sides on the Hit Die (e.g. ``8`` for a d8).

    Returns:
        The rounded-up average value, or ``0`` for a non-positive *die*.
    """
    if die <= 0:
        return 0
    # Ceiling of (die + 1) / 2 — i.e. round the true average up.  For the even
    # Hit Dice used in 3.5 (d4..d12) this equals (die + 2) // 2.
    return (die + 1 + 1) // 2


def _per_level_value(die: int, *, maximised: bool, method: str) -> int:
    """Return the rolled HP contribution of a single Hit Die (pre-CON)."""
    if die <= 0:
        return 0
    if maximised or method == HP_METHOD_MAX:
        return die
    return average_hit_die_value(die)


def _expand_hit_dice(
    classes: Iterable[tuple[str, int]],
    hit_dice: Mapping[str, int],
    default_hit_die: int,
) -> list[int]:
    """Expand ordered class levels into a flat, per-character-level Hit Die list."""
    flat: list[int] = []
    for name, levels in classes:
        # Double fallback: ``get`` covers a missing class; ``or`` covers a
        # stored ``None``/``0`` Hit Die (both fall back to the default).
        die = int(hit_dice.get(name, default_hit_die) or default_hit_die)
        flat.extend([die] * max(0, int(levels)))
    return flat


def compute_hit_points(
    classes: Iterable[tuple[str, int]],
    hit_dice: Mapping[str, int],
    con_mod: int,
    *,
    method: str = HP_METHOD_AVERAGE,
    max_first_level: bool = True,
    default_hit_die: int = DEFAULT_HIT_DIE,
    bonus_hp: int = 0,
) -> int:
    """Compute a character's maximum hit points.

    The first character level (the first level of the first class taken) is
    maximised when *max_first_level* is set, mirroring the standard PHB rule;
    every later Hit Die contributes either its maximum or its rounded-up
    average depending on *method*.  The Constitution modifier is added to each
    Hit Die, and a character always gains at least 1 hit point per Hit Die
    regardless of a Constitution penalty (PHB p145).

    Reference: PHB p145, DMG p198.

    Args:
        classes:         Ordered ``(class_name, levels)`` pairs as taken.
        hit_dice:        Mapping of class name → Hit Die size (e.g. ``8``).
        con_mod:         Constitution modifier applied per Hit Die.
        method:          ``"average"`` (default) or ``"max"`` for HP awarded on
                         levels after the first.
        max_first_level: Maximise the very first Hit Die when ``True``.
        default_hit_die: Hit Die assumed for classes absent from *hit_dice*.
        bonus_hp:        Flat extra HP from feats/templates (e.g. Toughness).

    Returns:
        Total maximum hit points (never negative).
    """
    flat = _expand_hit_dice(classes, hit_dice, default_hit_die)
    total = 0
    for index, die in enumerate(flat):
        maximised = max_first_level and index == 0
        rolled = _per_level_value(die, maximised=maximised, method=method)
        # Minimum 1 hp per Hit Die, even with a Constitution penalty (PHB p145).
        total += max(1, rolled + con_mod)
    total += bonus_hp
    return max(0, total)
