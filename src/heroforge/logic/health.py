"""Hit-point calculations for HeroForge-Anew.

Ports the workbook's *Stats & Character Details* hit-point logic: a
character's maximum HP is derived from the Hit Die of each class level, the
Constitution modifier applied per Hit Die, and any flat or per-level bonuses
contributed by feats or templates (e.g. Toughness, Improved Toughness).

Design notes:

* The first character level grants the maximum value of its Hit Die (the
  standard D&D 3.5 convention; PHB p7), while every subsequent level grants the
  Hit Die's average rounded up (``die // 2 + 1`` — e.g. d8 → 5, d10 → 6).  This
  keeps HP deterministic so it can be auto-computed and unit-tested, mirroring
  the workbook's "take average" behaviour rather than rolling.
* Each Hit Die always contributes at least 1 hit point even when the
  Constitution modifier is strongly negative (PHB p7).
* The functions are pure (no Qt/database dependencies) so the UI and database
  layers can depend on them rather than the reverse.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_DEFAULT_HIT_DIE = 8


def hit_dice_sequence(
    classes: Sequence[tuple[str, int]],
    hit_die_lookup: Mapping[str, int] | None = None,
    *,
    default_hit_die: int = _DEFAULT_HIT_DIE,
) -> list[int]:
    """Expand ordered ``(class_name, levels)`` pairs into per-level Hit Dice.

    Args:
        classes:        Ordered class levels exactly as taken, so the very first
                        entry is the character's first level (which gets maximum
                        HP).
        hit_die_lookup: Mapping of class name → Hit Die size.  Classes absent
                        from the mapping fall back to *default_hit_die* so the
                        computation never fails for homebrew/unseeded classes.
        default_hit_die: Hit Die used when a class is not in *hit_die_lookup*.

    Returns:
        A flat list of Hit Die sizes, one per character level, in order.
    """
    lookup = hit_die_lookup or {}
    sequence: list[int] = []
    for name, levels in classes:
        die = int(lookup.get(name, default_hit_die))
        sequence.extend([die] * max(0, int(levels)))
    return sequence


def max_hit_points(
    hit_dice: Sequence[int],
    con_mod: int,
    *,
    max_first_level: bool = True,
    flat_bonus: int = 0,
    per_level_bonus: int = 0,
) -> int:
    """Compute a character's maximum hit points.

    Reference: PHB p7 (hit points), PHB Chapter 3 (class Hit Dice).

    Args:
        hit_dice:        Ordered Hit Die sizes, one per character level (see
                         :func:`hit_dice_sequence`).
        con_mod:         Constitution modifier, applied to every Hit Die.
        max_first_level: When ``True`` (the default) the first Hit Die grants
                         its maximum value; otherwise it uses the same average
                         as later levels.
        flat_bonus:      A one-off bonus added to the total (e.g. the Toughness
                         feat's +3, or a template's flat HP grant).
        per_level_bonus: A bonus added to every Hit Die (e.g. Improved
                         Toughness's +1 per Hit Die).

    Returns:
        The maximum hit-point total (never below 0).
    """
    total = 0
    for index, raw_die in enumerate(hit_dice):
        die = int(raw_die)
        if die <= 0:
            # Non-positive Hit Die contributes no rolled HP; the per-Hit-Die
            # minimum of 1 below still guarantees at least 1 hp for it.
            base = 0
        elif index == 0 and max_first_level:
            base = die
        else:
            base = die // 2 + 1
        # Each Hit Die yields at least 1 hp, even with a punishing Con penalty.
        total += max(1, base + con_mod + per_level_bonus)
    return max(0, total + flat_bonus)
