"""Saving throw calculations for HeroForge-Anew.

Reference: PHB p141, p22 (class tables).
"""

from __future__ import annotations


def base_save(
    class_levels: dict[str, int],
    save_type: str,
    progressions: dict[str, dict[str, str]],
) -> int:
    """Calculate the base saving throw bonus from class levels.

    Reference: PHB p22 (class tables) and p141.

    Progression formulas:
    - ``'good'``:  ``2 + level // 2``
    - ``'poor'``:  ``level // 3``

    Args:
        class_levels: Mapping of class name → levels in that class.
        save_type:    One of ``'fort'``, ``'ref'``, or ``'will'``.
        progressions: Mapping of class name → dict with key *save_type*
                      whose value is ``'good'`` or ``'poor'``.

    Returns:
        Total base save bonus (integer).
    """
    total = 0
    for cls, lvl in class_levels.items():
        prog_map = progressions.get(cls, {})
        prog = prog_map.get(save_type, "poor").lower()
        if prog == "good":
            total += 2 + lvl // 2
        else:
            total += lvl // 3
    return total


def fortitude(base: int, con_mod: int, misc: int = 0) -> int:
    """Calculate the total Fortitude saving throw.

    Reference: PHB p141.

    Args:
        base:    Base Fortitude bonus from class levels.
        con_mod: Constitution modifier.
        misc:    Miscellaneous bonuses (items, feats, spells, etc.).

    Returns:
        Total Fortitude save modifier.
    """
    return base + con_mod + misc


def reflex(base: int, dex_mod: int, misc: int = 0) -> int:
    """Calculate the total Reflex saving throw.

    Reference: PHB p141.

    Args:
        base:    Base Reflex bonus from class levels.
        dex_mod: Dexterity modifier.
        misc:    Miscellaneous bonuses.

    Returns:
        Total Reflex save modifier.
    """
    return base + dex_mod + misc


def will(base: int, wis_mod: int, misc: int = 0) -> int:
    """Calculate the total Will saving throw.

    Reference: PHB p141.

    Args:
        base:    Base Will bonus from class levels.
        wis_mod: Wisdom modifier.
        misc:    Miscellaneous bonuses.

    Returns:
        Total Will save modifier.
    """
    return base + wis_mod + misc
