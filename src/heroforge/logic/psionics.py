"""Psionic power calculations for HeroForge-Anew.

Reference: Expanded Psionics Handbook (XPH) Chapters 2–3, plus the
manifesting classes catalogued on the workbook's "Psionic Info" sheet
(Excel tab 7b).  The per-class power-point-per-day progressions and key
abilities below are transcribed directly from that sheet so the Python
build matches the spreadsheet exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

from heroforge.logic.ability_scores import ability_modifier


def power_points_per_day(
    class_levels: dict[str, int],
    key_ability_mod: int,
    pp_tables: dict[str, list[int]],
) -> int:
    """Calculate total power points per day.

    Each manifesting class provides a number of power points based on class
    level (looked up in *pp_tables*).  A manifester with a high key ability
    score also gains bonus power points equal to ``floor(mod × manifester
    level ÷ 2)`` for each manifesting class.

    Reference: XPH p18-20 (power points per day / bonus power points), as
    implemented on the workbook's "Psionic Info" sheet (cells ``Q4:R12``).

    Args:
        class_levels:   Mapping of class name → levels in that class.
        key_ability_mod: Relevant ability modifier (INT for Psion, WIS for Ardent,
            etc.).
        pp_tables:       Mapping of class name → list of PP values indexed by level.

    Returns:
        Total power points per day.
    """
    total = 0
    for cls, lvl in class_levels.items():
        table = pp_tables.get(cls, [])
        if lvl > 0 and table:
            idx = min(lvl, len(table) - 1)
            class_pp = table[idx]
            # Bonus PP from a high key ability: floor(mod × manifester level ÷ 2).
            bonus_pp = max(0, key_ability_mod) * lvl // 2
            total += class_pp + bonus_pp
    return total


def manifester_level(class_levels: dict[str, int]) -> int:
    """Return the highest single-class manifester level.

    For characters with multiple manifesting classes, the highest class level
    is used.  Reference: XPH p18; workbook "Psionic Info" cell ``F18``.

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


# ---------------------------------------------------------------------------
# Manifesting-class catalogue
#
# Key ability and the power-points-per-day progression for every manifesting
# class on the workbook's "Psionic Info" sheet.  Each progression is indexed
# by manifester level (index 0 == no levels); the values are the base power
# points granted before the high-ability bonus is added.  Prestige classes
# whose manifesting tops out before character level 20 simply have shorter
# tables.
# ---------------------------------------------------------------------------

# fmt: off
_PP_PRIMARY: tuple[int, ...] = (
    0, 2, 6, 11, 17, 25, 35, 46, 58, 72, 88,
    106, 126, 147, 170, 195, 221, 250, 280, 311, 343,
)

_PP_DIVINE_MIND: tuple[int, ...] = (
    0, 0, 1, 2, 3, 4, 6, 8, 10, 12, 14,
    18, 22, 26, 30, 35, 40, 45, 50, 55, 62,
)

_PP_LURK: tuple[int, ...] = (
    0, 1, 2, 3, 5, 7, 11, 15, 19, 23, 27,
    35, 43, 51, 59, 67, 79, 91, 103, 115, 127,
)

_PP_PSYCHIC_WARRIOR: tuple[int, ...] = (
    0, 0, 1, 3, 5, 7, 11, 15, 19, 23, 27,
    35, 43, 51, 59, 67, 79, 91, 103, 115, 127,
)
# fmt: on


@dataclass(frozen=True)
class ManifesterInfo:
    """Manifesting metadata for a psionic class.

    Attributes:
        key_ability: The ability whose modifier drives manifesting
            (``"INT"``, ``"WIS"`` or ``"CHA"``).
        pp_per_day:  Base power points per day indexed by manifester level.
    """

    key_ability: str
    pp_per_day: tuple[int, ...]


MANIFESTING_CLASSES: dict[str, ManifesterInfo] = {
    "Ardent": ManifesterInfo("WIS", _PP_PRIMARY),
    "Divine Mind": ManifesterInfo("WIS", _PP_DIVINE_MIND),
    "Fist of Zuoken": ManifesterInfo("WIS", (0, 1, 3, 6, 10, 15, 23, 31, 43, 55, 71)),
    "Lurk": ManifesterInfo("INT", _PP_LURK),
    "Psion": ManifesterInfo("INT", _PP_PRIMARY),
    "Psychic Warrior": ManifesterInfo("WIS", _PP_PSYCHIC_WARRIOR),
    "War Mind": ManifesterInfo("WIS", (0, 2, 5, 9, 14, 20, 28, 37, 47, 58, 70)),
    "Wilder": ManifesterInfo("CHA", _PP_PRIMARY),
    "Zerth Cenobite": ManifesterInfo("WIS", (0, 1, 2, 3, 5, 7, 11, 15, 19, 23, 27)),
}


@dataclass(frozen=True)
class PsionicsSummary:
    """Auto-calculated psionics totals for the Psionics tab.

    Attributes:
        manifester_level: Highest single-class manifester level.
        power_points:     Total power points per day from manifesting classes.
    """

    manifester_level: int
    power_points: int


def psionic_class_levels(classes: list[tuple[str, int]]) -> dict[str, int]:
    """Filter character class levels down to known manifesting classes.

    Levels of repeated entries for the same class are summed.

    Args:
        classes: Character class list of ``(class_name, level)`` tuples.

    Returns:
        Mapping of manifesting class name → total levels.
    """
    levels: dict[str, int] = {}
    for name, level in classes:
        if name in MANIFESTING_CLASSES and level > 0:
            levels[name] = levels.get(name, 0) + level
    return levels


def compute_psionics(
    classes: list[tuple[str, int]], ability_scores: dict[str, int]
) -> PsionicsSummary:
    """Auto-calculate manifester level and power points for a character.

    Wires :func:`manifester_level` and :func:`power_points_per_day` to the
    manifesting-class catalogue so the Psionics tab can display values that
    match the workbook's "Psionic Info" sheet.

    Args:
        classes:        Character class list of ``(class_name, level)`` tuples.
        ability_scores: Mapping of ability name → score (e.g. ``{"INT": 16}``).

    Returns:
        A :class:`PsionicsSummary` with the manifester level and power points.
    """
    levels = psionic_class_levels(classes)
    if not levels:
        return PsionicsSummary(manifester_level=0, power_points=0)

    ml = manifester_level(levels)

    # Group manifesting classes by key ability so each group is scored with the
    # correct ability modifier, then reuse power_points_per_day per group.
    total_pp = 0
    abilities = {MANIFESTING_CLASSES[name].key_ability for name in levels}
    for ability in abilities:
        group = {
            name: lvl
            for name, lvl in levels.items()
            if MANIFESTING_CLASSES[name].key_ability == ability
        }
        pp_tables = {name: list(MANIFESTING_CLASSES[name].pp_per_day) for name in group}
        mod = ability_modifier(ability_scores.get(ability, 10))
        total_pp += power_points_per_day(group, mod, pp_tables)

    return PsionicsSummary(manifester_level=ml, power_points=total_pp)
