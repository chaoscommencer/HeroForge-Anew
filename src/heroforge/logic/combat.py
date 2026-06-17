"""Combat calculations for HeroForge-Anew.

Reference: PHB Chapter 8, p135–163.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

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
# Typed AC aggregation (PHB p150–151 stacking rules)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmorClassResult:
    """The three Armor Class readouts derived from a set of typed bonuses."""

    total: int
    touch: int
    flat_footed: int


# AC bonus types ignored when computing Touch AC (PHB p137): armor, shield and
# natural-armor bonuses do not apply against touch attacks.
_TOUCH_EXCLUDED_AC_TYPES: frozenset[str] = frozenset({"armor", "shield", "natural", "natural armor"})

# AC bonus types that stack with themselves (PHB p150–151).  Every other named
# bonus type is non-stacking, so only the single largest bonus of that type
# applies.  Penalties (negative values) always stack regardless of type.
_STACKING_AC_TYPES: frozenset[str] = frozenset({"untyped", "dodge", "circumstance"})


def aggregate_ac_bonuses(
    bonuses: Iterable[tuple[str, int]],
    *,
    exclude_types: Collection[str] = (),
) -> int:
    """Sum typed AC bonuses, honouring D&D 3.5 stacking rules.

    Reference: PHB p150–151 (bonus types and stacking).

    Same-type bonuses do **not** stack — only the largest of each non-stacking
    type counts — except dodge, circumstance and untyped bonuses, which stack
    with everything.  Penalties always stack.

    Args:
        bonuses:       Iterable of ``(bonus_type, value)`` pairs.  An empty or
                       unknown type is treated as untyped.
        exclude_types: Bonus types to drop entirely (used to derive Touch and
                       Flat-Footed AC from the same source list).

    Returns:
        The aggregated bonus (may be negative).
    """
    excluded = {str(t).strip().lower() for t in exclude_types}
    typed_best: dict[str, int] = {}
    stacking_total = 0
    for raw_type, raw_value in bonuses:
        btype = (str(raw_type).strip().lower()) or "untyped"
        if btype in excluded:
            continue
        value = int(raw_value)
        if value < 0 or btype in _STACKING_AC_TYPES:
            stacking_total += value
        else:
            typed_best[btype] = max(typed_best.get(btype, 0), value)
    return stacking_total + sum(typed_best.values())


def aggregate_armor_class(
    dex_mod: int,
    bonuses: Iterable[tuple[str, int]] = (),
    *,
    size: str = "Medium",
    max_dex: int | None = None,
) -> ArmorClassResult:
    """Aggregate every AC source into total, touch and flat-footed values.

    Reference: PHB p137 (AC, Touch AC, Flat-Footed AC).

    Args:
        dex_mod: The character's Dexterity modifier.
        bonuses: Iterable of ``(bonus_type, value)`` AC sources — armor,
                 shield, natural armor, deflection, dodge, etc.  Size and Dex
                 are applied separately and must not be included here.
        size:    Size category, supplying the size modifier (PHB p149).
        max_dex: Optional Max Dex Bonus cap from worn armor; when set, the Dex
                 contribution to AC is capped at this value.

    Returns:
        An :class:`ArmorClassResult` snapshot.
    """
    capped_dex = dex_mod if max_dex is None else min(dex_mod, max_dex)
    size_mod = _size_ac_attack_mod(size)
    bonus_list = list(bonuses)
    total = 10 + capped_dex + size_mod + aggregate_ac_bonuses(bonus_list)
    touch = (
        10
        + capped_dex
        + size_mod
        + aggregate_ac_bonuses(bonus_list, exclude_types=_TOUCH_EXCLUDED_AC_TYPES)
    )
    # Flat-footed loses Dexterity *bonuses* and dodge bonuses (PHB p137); a Dex
    # penalty still applies.
    flat_dex = min(capped_dex, 0)
    flat = (
        10
        + flat_dex
        + size_mod
        + aggregate_ac_bonuses(bonus_list, exclude_types={"dodge"})
    )
    return ArmorClassResult(total=total, touch=touch, flat_footed=flat)


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
