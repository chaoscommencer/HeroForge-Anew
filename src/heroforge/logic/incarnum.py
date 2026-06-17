"""Incarnum (Magic of Incarnum) calculations for HeroForge-Anew.

Reference: Magic of Incarnum (MoI) Chapters 2-3.  The per-class essentia and
soulmeld progressions and the chakra-bind unlock levels are seeded from the
workbook's "Soulmelds" sheet (Excel tab 8) into the ``incarnum_progression``
and ``incarnum_chakra`` tables and supplied to the functions here as an
:class:`IncarnumProgression` mapping (see
:meth:`heroforge.db.data_access.GameDataRepository.incarnum_progressions`), so
the Python build matches the spreadsheet exactly without hard-coding the data.
The module-level ``_FALLBACK_*`` constants are an offline fallback only, used
when the database has not been seeded; they are never the seeding source while
the workbook is available.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

#: The core meldshaping classes (MoI Chapter 2).
MELDSHAPING_CLASSES: tuple[str, ...] = ("Incarnate", "Soulborn", "Totemist")


@dataclass(frozen=True)
class IncarnumProgression:
    """Per-class meldshaping progression (Magic of Incarnum).

    Attributes:
        essentia:  Essentia pool granted, indexed by class level (level ``0``
            at index 0 through level ``len - 1``).  MoI p22/p30/p38.
        soulmelds: Number of soulmelds shapeable, indexed the same way.
        chakra_unlocks: Mapping of chakra name -> minimum class level at which a
            soulmeld may be bound to that chakra.
    """

    essentia: tuple[int, ...]
    soulmelds: tuple[int, ...]
    chakra_unlocks: dict[str, int]


@dataclass(frozen=True)
class IncarnumSummary:
    """Auto-calculated incarnum totals for the Soulmelds tab.

    Attributes:
        meldshaper_level:       Highest single-class meldshaper level.
        essentia_pool:          Total essentia available to invest.
        soulmeld_capacity:      Maximum essentia investable in one soulmeld.
        soulmelds_shapeable:    Number of soulmelds that can be shaped.
        chakra_binds_available: Number of chakras that can hold a bound soulmeld.
    """

    meldshaper_level: int
    essentia_pool: int
    soulmeld_capacity: int
    soulmelds_shapeable: int
    chakra_binds_available: int


# ---------------------------------------------------------------------------
# Offline fallback tables (transcribed from the workbook's "Soulmelds" sheet).
#
# These are used only when the ``incarnum_progression`` / ``incarnum_chakra``
# tables have not been seeded.  The seeded data, read through
# ``GameDataRepository.incarnum_progressions``, is authoritative at runtime.
# Index 0 corresponds to class level 0 (no levels); index N to class level N.
# ---------------------------------------------------------------------------

_FALLBACK_ESSENTIA: dict[str, tuple[int, ...]] = {
    "Incarnate": (
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        16,
        18,
        20,
        22,
        24,
        26,
    ),
    "Soulborn": (
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
        5,
        5,
        6,
        7,
        8,
        9,
        10,
    ),
    "Totemist": (
        0,
        1,
        2,
        2,
        3,
        3,
        4,
        5,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        16,
        18,
        20,
    ),
}

_FALLBACK_SOULMELDS: dict[str, tuple[int, ...]] = {
    "Incarnate": (
        0,
        2,
        3,
        3,
        4,
        4,
        4,
        5,
        5,
        5,
        6,
        6,
        6,
        7,
        7,
        7,
        8,
        8,
        8,
        9,
        9,
    ),
    "Soulborn": (
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
        3,
        3,
        3,
        3,
        4,
        4,
        4,
        4,
        5,
    ),
    "Totemist": (
        0,
        2,
        3,
        3,
        4,
        4,
        4,
        5,
        5,
        5,
        6,
        6,
        6,
        7,
        7,
        7,
        8,
        8,
        8,
        9,
        9,
    ),
}

_FALLBACK_CHAKRA_UNLOCKS: dict[str, dict[str, int]] = {
    "Incarnate": {
        "Crown": 2,
        "Feet": 4,
        "Hands": 4,
        "Arms": 9,
        "Brow": 9,
        "Shoulders": 9,
        "Throat": 14,
        "Waist": 14,
        "Heart": 16,
        "Soul": 19,
    },
    "Soulborn": {
        "Crown": 8,
        "Feet": 8,
        "Hands": 8,
        "Arms": 14,
        "Brow": 14,
        "Shoulders": 14,
        "Throat": 18,
        "Waist": 18,
    },
    "Totemist": {
        "Totem": 2,
        "Crown": 5,
        "Feet": 5,
        "Hands": 5,
        "Arms": 9,
        "Brow": 9,
        "Shoulders": 9,
        "Throat": 14,
        "Waist": 14,
        "Heart": 17,
    },
}


def _fallback_progressions() -> dict[str, IncarnumProgression]:
    """Return the in-code progression catalogue used when unseeded."""
    return {
        cls: IncarnumProgression(
            essentia=_FALLBACK_ESSENTIA[cls],
            soulmelds=_FALLBACK_SOULMELDS[cls],
            chakra_unlocks=dict(_FALLBACK_CHAKRA_UNLOCKS[cls]),
        )
        for cls in _FALLBACK_ESSENTIA
    }


def _table_lookup(table: tuple[int, ...], level: int) -> int:
    """Return ``table[level]``, clamping to the last entry beyond its length."""
    if level <= 0 or not table:
        return 0
    return table[min(level, len(table) - 1)]


def meldshaper_level(
    class_levels: Mapping[str, int],
    meldshaping_classes: tuple[str, ...] = MELDSHAPING_CLASSES,
) -> int:
    """Return the highest meldshaper level among meldshaping classes.

    Reference: MoI p49.

    Args:
        class_levels:        Mapping of class name -> levels.
        meldshaping_classes: Class names that grant a meldshaper level.

    Returns:
        Highest meldshaper level, or 0 if no meldshaping classes.
    """
    return max(
        (lvl for cls, lvl in class_levels.items() if cls in meldshaping_classes),
        default=0,
    )


def essentia_pool(
    class_levels: Mapping[str, int],
    feat_bonus: int = 0,
    progressions: Mapping[str, IncarnumProgression] | None = None,
) -> int:
    """Calculate the character's total essentia pool.

    Reference: MoI p22/p30/p38 (per-class essentia tables); the workbook sums
    each meldshaping class's essentia and adds bonus essentia from feats.

    Args:
        class_levels: Mapping of class name -> levels in that class.
        feat_bonus:   Additional essentia from feats (e.g. Bonus Essentia).
        progressions: Override mapping of class -> :class:`IncarnumProgression`.
            If ``None``, the in-code fallback tables are used.

    Returns:
        Total essentia pool size.
    """
    tables = progressions if progressions is not None else _fallback_progressions()
    total = feat_bonus
    for cls, lvl in class_levels.items():
        prog = tables.get(cls)
        if prog is not None and lvl > 0:
            total += _table_lookup(prog.essentia, lvl)
    return total


def soulmelds_shapeable(
    class_levels: Mapping[str, int],
    progressions: Mapping[str, IncarnumProgression] | None = None,
) -> int:
    """Return the total number of soulmelds the character can shape.

    Reference: MoI p22/p30/p38 (Soulmelds column of each class table).

    Args:
        class_levels: Mapping of class name -> levels in that class.
        progressions: Override mapping of class -> :class:`IncarnumProgression`.

    Returns:
        Total soulmelds shapeable across meldshaping classes.
    """
    tables = progressions if progressions is not None else _fallback_progressions()
    total = 0
    for cls, lvl in class_levels.items():
        prog = tables.get(cls)
        if prog is not None and lvl > 0:
            total += _table_lookup(prog.soulmelds, lvl)
    return total


def soulmeld_capacity(character_level: int) -> int:
    """Return the maximum essentia that can be invested in a single soulmeld.

    Capacity is set by overall character level, not meldshaper level: 1 essentia
    at 1st-5th, 2 at 6th-11th, 3 at 12th-17th, and 4 at 18th level and beyond.
    Reference: MoI p115 (essentia capacity); workbook "Soulmelds" cell ``AL27``
    (``=1+(HitDice>=6)+(HitDice>=12)+(HitDice>=18)``).

    Args:
        character_level: The character's total level (Hit Dice).

    Returns:
        Essentia capacity per soulmeld (0 for a level-0 character).
    """
    if character_level <= 0:
        return 0
    return (
        1 + (character_level >= 6) + (character_level >= 12) + (character_level >= 18)
    )


def unlocked_chakras(
    class_levels: Mapping[str, int],
    progressions: Mapping[str, IncarnumProgression] | None = None,
) -> set[str]:
    """Return the set of chakras the character can bind soulmelds to.

    A chakra is available if any meldshaping class has reached its unlock level.
    Multiclass meldshapers share the same physical chakra slots, so the result
    is the union across classes (mirroring the workbook's per-chakra "open if
    any class opens it" logic on the "Soulmelds" sheet).

    Reference: MoI p22/p30/p38 (chakra bind class features).

    Args:
        class_levels: Mapping of class name -> levels in that class.
        progressions: Override mapping of class -> :class:`IncarnumProgression`.

    Returns:
        Set of unlocked chakra names.
    """
    tables = progressions if progressions is not None else _fallback_progressions()
    chakras: set[str] = set()
    for cls, lvl in class_levels.items():
        prog = tables.get(cls)
        if prog is None or lvl <= 0:
            continue
        for chakra, min_level in prog.chakra_unlocks.items():
            if lvl >= min_level:
                chakras.add(chakra)
    return chakras


def chakra_binds_available(
    class_levels: Mapping[str, int],
    progressions: Mapping[str, IncarnumProgression] | None = None,
) -> int:
    """Return the number of chakras available to bind soulmelds to.

    Each open chakra can hold a single bound soulmeld, so this count is the
    maximum number of soulmelds the character may have bound at once.

    Reference: MoI p22/p30/p38 (chakra bind class features).

    Args:
        class_levels: Mapping of class name -> levels in that class.
        progressions: Override mapping of class -> :class:`IncarnumProgression`.

    Returns:
        Number of bindable chakras.
    """
    return len(unlocked_chakras(class_levels, progressions))


def meldshaping_class_levels(
    classes: list[tuple[str, int]],
    progressions: Mapping[str, IncarnumProgression],
) -> dict[str, int]:
    """Filter character class levels down to known meldshaping classes.

    Levels of repeated entries for the same class are summed.

    Args:
        classes:      Character class list of ``(class_name, level)`` tuples.
        progressions: Catalogue of meldshaping classes (typically from
            :meth:`GameDataRepository.incarnum_progressions`).

    Returns:
        Mapping of meldshaping class name -> total levels.
    """
    levels: dict[str, int] = {}
    for name, level in classes:
        if name in progressions and level > 0:
            levels[name] = levels.get(name, 0) + level
    return levels


def compute_incarnum(
    classes: list[tuple[str, int]],
    character_level: int,
    feat_bonus: int = 0,
    progressions: Mapping[str, IncarnumProgression] | None = None,
) -> IncarnumSummary:
    """Auto-calculate the incarnum totals for a character.

    Wires the individual calculations to the meldshaping-class catalogue so the
    Soulmelds tab can display values that match the workbook's "Soulmelds"
    sheet.

    Args:
        classes:         Character class list of ``(class_name, level)`` tuples.
        character_level: The character's total level (for soulmeld capacity).
        feat_bonus:      Additional essentia from feats (e.g. Bonus Essentia).
        progressions:    Catalogue of meldshaping classes (typically from
            :meth:`GameDataRepository.incarnum_progressions`).  If ``None``, the
            in-code fallback tables are used.

    Returns:
        An :class:`IncarnumSummary` with the derived totals.
    """
    tables = progressions if progressions is not None else _fallback_progressions()
    levels = meldshaping_class_levels(classes, tables)
    return IncarnumSummary(
        meldshaper_level=meldshaper_level(levels, tuple(tables)),
        essentia_pool=essentia_pool(levels, feat_bonus, tables),
        soulmeld_capacity=soulmeld_capacity(character_level),
        soulmelds_shapeable=soulmelds_shapeable(levels, tables),
        chakra_binds_available=chakra_binds_available(levels, tables),
    )
