"""Incarnum (Magic of Incarnum) calculations for HeroForge-Anew.

Reference: Magic of Incarnum (MoI) Chapters 2–3.
"""

from __future__ import annotations

# Soulmeld capacity by meldshaper level.  MoI p49.
_CAPACITY_TABLE: list[int] = [
    # index = meldshaper_level - 1
    1,  # level 1
    1,  # level 2
    2,  # level 3
    2,  # level 4
    2,  # level 5
    3,  # level 6
    3,  # level 7
    3,  # level 8
    4,  # level 9
    4,  # level 10
    4,  # level 11
    4,  # level 12
    5,  # level 13
    5,  # level 14
    5,  # level 15
    5,  # level 16
    6,  # level 17
    6,  # level 18
    6,  # level 19
    6,  # level 20
]

# Default essentia tables per class (MoI p22, p30, p38).
_DEFAULT_ESSENTIA_TABLES: dict[str, list[int]] = {
    "Incarnate": [1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11],
    "Totemist":  [1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11],
    "Soulborn":  [0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7],
}


def essentia_pool(
    class_levels: dict[str, int],
    feat_bonus: int = 0,
    essentia_tables: dict[str, list[int]] | None = None,
) -> int:
    """Calculate the character's total essentia pool.

    Reference: MoI p49 (essentia pool table).

    Args:
        class_levels:     Mapping of class name → levels in that class.
        feat_bonus:       Additional essentia from feats (e.g. Bonus Essentia).
        essentia_tables:  Override mapping of class → essentia table.
                          If ``None``, built-in defaults are used.

    Returns:
        Total essentia pool size.
    """
    tables = essentia_tables if essentia_tables is not None else _DEFAULT_ESSENTIA_TABLES
    total = feat_bonus
    for cls, lvl in class_levels.items():
        table = tables.get(cls, [])
        if lvl > 0 and table:
            idx = min(lvl - 1, len(table) - 1)
            total += table[idx]
    return total


def meldshaper_level(class_levels: dict[str, int]) -> int:
    """Return the highest meldshaper level among meldshaping classes.

    Reference: MoI p49.

    Args:
        class_levels: Mapping of class name → levels.

    Returns:
        Highest meldshaper level, or 0 if no meldshaping classes.
    """
    meldshaping_classes = {"Incarnate", "Totemist", "Soulborn"}
    return max(
        (lvl for cls, lvl in class_levels.items() if cls in meldshaping_classes),
        default=0,
    )


def soulmeld_capacity(meldshaper_lvl: int) -> int:
    """Return the maximum essentia that can be invested in a single soulmeld.

    Reference: MoI p49 (Essentia Capacity column).

    Args:
        meldshaper_lvl: The character's meldshaper level.

    Returns:
        Essentia capacity per soulmeld.
    """
    if meldshaper_lvl <= 0:
        return 0
    idx = min(meldshaper_lvl - 1, len(_CAPACITY_TABLE) - 1)
    return _CAPACITY_TABLE[idx]


def chakra_binds_available(class_name: str, class_level: int) -> int:
    """Return the number of chakra binds available at a given class level.

    Reference: MoI p22 (Incarnate table), p30 (Totemist), p38 (Soulborn).

    Args:
        class_name:  One of ``'Incarnate'``, ``'Totemist'``, or ``'Soulborn'``.
        class_level: Level in that class (1–20).

    Returns:
        Number of chakra binds.
    """
    if class_level <= 0:
        return 0

    # Incarnate: binds at levels 5, 8, 11, 14, 17, 20 (one each)
    if class_name == "Incarnate":
        bind_levels = [5, 8, 11, 14, 17, 20]
        return sum(1 for lvl in bind_levels if class_level >= lvl)

    # Totemist: binds at levels 4, 8, 12, 16, 20
    if class_name == "Totemist":
        bind_levels = [4, 8, 12, 16, 20]
        return sum(1 for lvl in bind_levels if class_level >= lvl)

    # Soulborn: bind at levels 6, 12, 18
    if class_name == "Soulborn":
        bind_levels = [6, 12, 18]
        return sum(1 for lvl in bind_levels if class_level >= lvl)

    return 0
