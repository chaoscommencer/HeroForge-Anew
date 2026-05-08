"""Combat calculations for HeroForge-Anew.

Reference: PHB Chapter 8, p135–163.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Size modifier tables (PHB p149, p312)
# ---------------------------------------------------------------------------

# Size modifier applied to AC and attack rolls (attack and AC use same value).
_SIZE_AC_ATTACK: dict[str, int] = {
    "Fine": 8,
    "Diminutive": 4,
    "Tiny": 2,
    "Small": 1,
    "Medium": 0,
    "Large": -1,
    "Huge": -2,
    "Gargantuan": -4,
    "Colossal": -8,
}

# Size modifier applied to grapple checks (PHB p156).
_SIZE_GRAPPLE: dict[str, int] = {
    "Fine": -16,
    "Diminutive": -12,
    "Tiny": -8,
    "Small": -4,
    "Medium": 0,
    "Large": 4,
    "Huge": 8,
    "Gargantuan": 12,
    "Colossal": 16,
}

# Carrying-capacity multiplier by Strength score (PHB p162).
# Light load = index 0, Medium = index 1, Heavy = index 2.
_CARRY_BASE: dict[int, tuple[int, int, int]] = {
    1: (3, 6, 10),
    2: (6, 13, 20),
    3: (10, 20, 30),
    4: (13, 26, 40),
    5: (16, 33, 50),
    6: (20, 40, 60),
    7: (23, 46, 70),
    8: (26, 53, 80),
    9: (30, 60, 90),
    10: (33, 66, 100),
    11: (38, 76, 115),
    12: (43, 86, 130),
    13: (50, 100, 150),
    14: (58, 116, 175),
    15: (66, 133, 200),
    16: (76, 153, 230),
    17: (86, 173, 260),
    18: (100, 200, 300),
    19: (116, 233, 350),
    20: (133, 266, 400),
    21: (153, 306, 460),
    22: (173, 346, 520),
    23: (200, 400, 600),
    24: (233, 466, 700),
    25: (266, 533, 800),
    26: (306, 613, 920),
    27: (346, 693, 1040),
    28: (400, 800, 1200),
    29: (466, 933, 1400),
}


def _size_ac_attack_mod(size: str) -> int:
    """Return the size modifier to AC and attack rolls. PHB p149."""
    return _SIZE_AC_ATTACK.get(size, 0)


def _size_grapple_mod(size: str) -> int:
    """Return the size modifier to grapple checks. PHB p156."""
    return _SIZE_GRAPPLE.get(size, 0)


# ---------------------------------------------------------------------------
# BAB
# ---------------------------------------------------------------------------


def base_attack_bonus(
    class_levels: dict[str, int],
    bab_progressions: dict[str, str],
) -> int:
    """Calculate the total Base Attack Bonus.

    Reference: PHB p22 (class tables), PHB p135.

    Args:
        class_levels:    Mapping of class name → levels taken in that class.
        bab_progressions: Mapping of class name → progression type.
                          Valid values: ``'fast'``, ``'medium'``, ``'slow'``.

    Returns:
        Total BAB (integer, pre-iterative-attack calculation).
    """
    total = 0
    for cls, lvl in class_levels.items():
        progression = bab_progressions.get(cls, "medium").lower()
        if progression == "fast":
            total += lvl
        elif progression == "medium":
            total += lvl * 3 // 4
        else:  # slow
            total += lvl // 2
    return total


# ---------------------------------------------------------------------------
# Armor Class
# ---------------------------------------------------------------------------


def armor_class(
    dex_mod: int,
    armor: int = 0,
    shield: int = 0,
    size: str = "Medium",
    natural: int = 0,
    deflect: int = 0,
    dodge: int = 0,
    misc: int = 0,
) -> int:
    """Calculate full Armor Class.

    Reference: PHB p135 (AC = 10 + armor + shield + dex + size + natural +
    deflection + dodge + misc).

    Returns:
        Total AC value.
    """
    return (
        10
        + armor
        + shield
        + dex_mod
        + _size_ac_attack_mod(size)
        + natural
        + deflect
        + dodge
        + misc
    )


def touch_ac(
    dex_mod: int,
    size: str = "Medium",
    deflect: int = 0,
    dodge: int = 0,
    misc: int = 0,
) -> int:
    """Calculate Touch Armor Class (no armor/shield/natural). PHB p135.

    Returns:
        Touch AC value.
    """
    return 10 + dex_mod + _size_ac_attack_mod(size) + deflect + dodge + misc


def flat_footed_ac(
    armor: int = 0,
    shield: int = 0,
    size: str = "Medium",
    natural: int = 0,
    deflect: int = 0,
    misc: int = 0,
) -> int:
    """Calculate Flat-Footed Armor Class (no Dex or Dodge). PHB p135.

    Returns:
        Flat-footed AC value.
    """
    return 10 + armor + shield + _size_ac_attack_mod(size) + natural + deflect + misc


# ---------------------------------------------------------------------------
# Grapple / Initiative / Attacks
# ---------------------------------------------------------------------------


def grapple_modifier(
    bab: int,
    str_mod: int,
    size_mod: int = 0,
    size: str = "Medium",
) -> int:
    """Calculate the grapple check modifier.

    Reference: PHB p155.

    Args:
        bab:      Base attack bonus.
        str_mod:  Strength modifier.
        size_mod: Explicit size modifier override; if 0 and *size* is provided,
                  the lookup table is used instead.
        size:     Size category string (ignored when *size_mod* != 0).

    Returns:
        Grapple modifier.
    """
    effective_size_mod = size_mod if size_mod != 0 else _size_grapple_mod(size)
    return bab + str_mod + effective_size_mod


def initiative(dex_mod: int, feat_bonus: int = 0, misc: int = 0) -> int:
    """Calculate initiative modifier.

    Reference: PHB p136.

    Returns:
        Initiative modifier.
    """
    return dex_mod + feat_bonus + misc


def melee_attack(
    bab: int,
    str_mod: int,
    size_mod: int = 0,
    size: str = "Medium",
    misc: int = 0,
) -> int:
    """Calculate melee attack bonus.

    Reference: PHB p135 (Attack roll = d20 + BAB + STR mod + size mod).

    Args:
        bab:     Base attack bonus.
        str_mod: Strength modifier.
        size_mod: Explicit size modifier override.
        size:    Size category string.
        misc:    Miscellaneous bonuses (weapon focus, etc.).

    Returns:
        Melee attack bonus (first attack).
    """
    effective_size = size_mod if size_mod != 0 else _size_ac_attack_mod(size)
    return bab + str_mod + effective_size + misc


def ranged_attack(
    bab: int,
    dex_mod: int,
    size_mod: int = 0,
    size: str = "Medium",
    misc: int = 0,
) -> int:
    """Calculate ranged attack bonus.

    Reference: PHB p135 (Attack roll = d20 + BAB + DEX mod + size mod).

    Returns:
        Ranged attack bonus (first attack).
    """
    effective_size = size_mod if size_mod != 0 else _size_ac_attack_mod(size)
    return bab + dex_mod + effective_size + misc


def damage_bonus(
    str_mod: int,
    two_handed: bool = False,
    off_hand: bool = False,
) -> int:
    """Calculate the Strength bonus to damage.

    Reference: PHB p135.
    - Two-handed: 1.5× STR modifier (round down).
    - Off-hand: 0.5× STR modifier if positive (round down); full if negative.

    Returns:
        Damage bonus from Strength.
    """
    if two_handed:
        if str_mod >= 0:
            return int(str_mod * 1.5)
        return str_mod
    if off_hand:
        if str_mod > 0:
            return str_mod // 2
        return str_mod
    return str_mod


def carrying_capacity(str_score: int) -> tuple[int, int, int]:
    """Return (light_max, medium_max, heavy_max) carrying limits in pounds.

    For Strength scores above 29, each 10-point increment doubles the
    capacity. For scores below 1, use 1's limits.

    Reference: PHB p162.

    Returns:
        Tuple of ``(light_max, medium_max, heavy_max)``.
    """
    if str_score <= 0:
        str_score = 1

    if str_score <= 29:
        return _CARRY_BASE[str_score]

    # For STR > 29: every +10 STR doubles the capacity of STR 29.
    multiplier = 1
    excess = str_score - 29
    doublings = (excess + 9) // 10  # ceiling division
    for _ in range(doublings):
        multiplier *= 2

    base = _CARRY_BASE[29]
    return (base[0] * multiplier, base[1] * multiplier, base[2] * multiplier)
