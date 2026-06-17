"""Experience point calculations for HeroForge-Anew.

Reference: PHB p22 (Experience and Levels table), p36 (XP Awards).
"""

from __future__ import annotations

# XP required to reach each level.  Index = level (1-based).
# PHB p22.
_XP_TABLE: dict[int, int] = {
    1: 0,
    2: 1_000,
    3: 3_000,
    4: 6_000,
    5: 10_000,
    6: 15_000,
    7: 21_000,
    8: 28_000,
    9: 36_000,
    10: 45_000,
    11: 55_000,
    12: 66_000,
    13: 78_000,
    14: 91_000,
    15: 105_000,
    16: 120_000,
    17: 136_000,
    18: 153_000,
    19: 171_000,
    20: 190_000,
}

# XP award table: base XP for defeating an equal-CR encounter (PHB p36).
# Key = CR difference (character_level - CR), capped at ±5.
_CR_DIFF_XP: dict[int, int] = {
    -5: 2_400,  # CR 5 above PC level
    -4: 2_100,
    -3: 1_800,
    -2: 1_500,
    -1: 1_200,
    0: 900,  # CR equals PC level → standard award
    1: 600,
    2: 450,
    3: 300,
    4: 225,
    5: 150,  # CR 5 below PC level
}


def xp_for_level(level: int) -> int:
    """Return the cumulative XP required to reach *level*.

    Reference: PHB p22.

    Args:
        level: Target character level (1–20; extrapolated beyond 20).

    Returns:
        XP total needed to reach that level.

    Raises:
        ValueError: If *level* is less than 1.
    """
    if level < 1:
        raise ValueError(f"Character level must be ≥ 1, got {level}.")
    if level in _XP_TABLE:
        return _XP_TABLE[level]
    # Beyond level 20: each level requires (level - 1) × 1_000 XP more than
    # the previous level (approximate extrapolation).
    base = _XP_TABLE[20]
    extra_levels = level - 20
    extra_xp = sum((20 + i) * 1_000 for i in range(extra_levels))
    return base + extra_xp


def level_for_xp(xp: int) -> int:
    """Return the highest level a character with *xp* experience points has.

    Reference: PHB p22.

    Args:
        xp: Current experience point total (≥ 0).

    Returns:
        Character level (minimum 1).
    """
    level = 1
    for lvl in range(1, 21):
        if xp >= _XP_TABLE[lvl]:
            level = lvl
        else:
            break
    return level


def encounter_xp(character_level: int, cr: float) -> int:
    """Return XP award for a single character defeating a CR *cr* encounter.

    Reference: PHB p36 (Experience Point Awards table).

    Args:
        character_level: The character's total level.
        cr:              Challenge Rating of the encounter (may be fractional).

    Returns:
        XP award for one character.
    """
    diff = character_level - int(round(cr))
    diff_clamped = max(-5, min(5, diff))
    return _CR_DIFF_XP.get(diff_clamped, 150)
