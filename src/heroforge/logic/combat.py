"""Combat calculations for HeroForge-Anew.

Reference: PHB Chapter 8, p135–163.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from heroforge.logic.buffs import STACKABLE_BONUS_TYPES

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
# Aggregated, type-aware Armor Class
# ---------------------------------------------------------------------------

# AC bonus types that are ignored against touch attacks (armor, shields, and
# natural armor do not apply to touch AC).  PHB p146.
_TOUCH_EXCLUDED_TYPES: frozenset[str] = frozenset({"armor", "shield", "natural"})

# AC bonus types lost while flat-footed (you also lose your Dex bonus). PHB p137.
_FLATFOOTED_EXCLUDED_TYPES: frozenset[str] = frozenset({"dodge"})


@dataclass(frozen=True)
class ArmorClassBreakdown:
    """The three Armor Class values derived from a set of typed bonuses.

    Reference: PHB p135–137, p146.
    """

    total: int
    touch: int
    flat_footed: int


def _normalize_ac_bonus_type(bonus_type: str) -> str:
    """Canonicalise an AC bonus-type label for grouping/stacking.

    Empty or unknown labels collapse to ``"untyped"`` (which stacks), and the
    common ``"natural armor"`` spelling is folded onto ``"natural"``.
    """
    key = (bonus_type or "").strip().lower()
    if not key:
        return "untyped"
    if key in ("natural armor", "naturalarmor"):
        return "natural"
    return key


def _aggregate_ac_bonuses(bonuses: Iterable[tuple[str, int]]) -> dict[str, int]:
    """Collapse ``(bonus_type, value)`` pairs into a net value per bonus type.

    Stackable types (dodge, circumstance, racial, untyped) sum together; every
    other type keeps only its single largest bonus, matching the general
    stacking rule used elsewhere in the app (PHB p146).
    """
    grouped: dict[str, list[int]] = {}
    for bonus_type, value in bonuses:
        grouped.setdefault(_normalize_ac_bonus_type(bonus_type), []).append(int(value))

    net: dict[str, int] = {}
    for key, values in grouped.items():
        if key in STACKABLE_BONUS_TYPES:
            net[key] = sum(values)
        else:
            net[key] = max(values)
    return net


def aggregate_armor_class(
    dex_mod: int,
    size: str = "Medium",
    bonuses: Iterable[tuple[str, int]] = (),
    max_dex: int | None = None,
) -> ArmorClassBreakdown:
    """Aggregate typed AC bonuses into total, touch, and flat-footed AC.

    Each entry in *bonuses* is a ``(bonus_type, value)`` pair describing one
    contributing source (e.g. ``("armor", 8)``, ``("deflection", 1)``,
    ``("natural", 2)``, ``("dodge", 1)``).  Bonuses of the same non-stackable
    type are reduced to the largest value before being summed, while dodge,
    circumstance, racial, and untyped bonuses stack (PHB p146).

    Reference: PHB p135 (AC), p137 (flat-footed), p146 (touch / stacking).

    Args:
        dex_mod: Dexterity modifier.
        size:    Size category supplying the size modifier (PHB p149).
        bonuses: Iterable of ``(bonus_type, value)`` AC bonus sources.
        max_dex: Maximum Dexterity bonus to AC (e.g. an armor's max-Dex cap).
                 When set, the Dex contribution to every AC value is capped at
                 this value; ``None`` means uncapped.

    Returns:
        An :class:`ArmorClassBreakdown` with the three AC values.
    """
    net = _aggregate_ac_bonuses(bonuses)
    size_mod = _size_ac_attack_mod(size)
    effective_dex = dex_mod if max_dex is None else min(dex_mod, max_dex)

    total = 10 + effective_dex + size_mod + sum(net.values())
    touch = (
        10
        + effective_dex
        + size_mod
        + sum(v for k, v in net.items() if k not in _TOUCH_EXCLUDED_TYPES)
    )
    # When flat-footed you lose your Dex bonus (but keep a Dex penalty) and any
    # dodge bonuses.
    flat_dex = min(effective_dex, 0)
    flat_footed = (
        10
        + flat_dex
        + size_mod
        + sum(v for k, v in net.items() if k not in _FLATFOOTED_EXCLUDED_TYPES)
    )
    return ArmorClassBreakdown(total=total, touch=touch, flat_footed=flat_footed)


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
