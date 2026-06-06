"""Skill calculations for HeroForge-Anew.

Reference: PHB Chapter 4, p62–105.
"""

from __future__ import annotations


def max_ranks(character_level: int, is_class_skill: bool) -> float:
    """Return the maximum skill ranks for a character of *character_level*.

    Reference: PHB p62.

    - Class skill: ``character_level + 3``
    - Cross-class skill: ``(character_level + 3) / 2``

    Args:
        character_level: Total character level (1–20+).
        is_class_skill:  Whether this is a class skill for the character.

    Returns:
        Maximum allowable ranks (float for cross-class skills).
    """
    if is_class_skill:
        return float(character_level + 3)
    return (character_level + 3) / 2.0


def skill_modifier(
    ranks: float,
    ability_mod: int,
    is_class_skill: bool,
    misc: int = 0,
) -> int:
    """Calculate the total skill check modifier.

    Skill checks use the invested ranks, relevant ability modifier, and any
    miscellaneous modifiers.

    ``is_class_skill`` affects maximum ranks and point cost, but does not
    apply any additional check modifier by itself. The parameter is retained
    for API compatibility with existing call sites.

    Args:
        ranks:          Skill ranks invested.
        ability_mod:    Relevant ability modifier.
        is_class_skill: Whether this skill is a class skill.
        misc:           Miscellaneous bonuses (synergies, feats, items, etc.).

    Returns:
        Total skill modifier.
    """
    return int(ranks) + ability_mod + misc


def cross_class_rank_cost() -> int:
    """Return the skill-point cost for one rank in a cross-class skill.

    Reference: PHB p62.  Cross-class ranks always cost 2 skill points.

    Returns:
        Always ``2``.
    """
    return 2


def skill_synergy_bonus(
    qualifying_skills: list[str],
    synergies: list[tuple[str, str]],
) -> dict[str, int]:
    """Calculate synergy bonuses granted by *qualifying_skills*.

    A skill grants a +2 synergy bonus to another skill when the character
    has 5 or more ranks in the source skill.  Only skills in
    *qualifying_skills* (i.e. those with ≥ 5 ranks) are considered.

    Reference: PHB p65.

    Args:
        qualifying_skills: Skill names for which the character has ≥ 5 ranks.
        synergies:         List of ``(from_skill, to_skill)`` pairs from the
                           ``skill_synergies`` database table.

    Returns:
        Mapping of skill name → total synergy bonus applicable to that skill.
    """
    bonuses: dict[str, int] = {}
    qualifying_set = set(qualifying_skills)
    for from_skill, to_skill in synergies:
        if from_skill in qualifying_set:
            bonuses[to_skill] = bonuses.get(to_skill, 0) + 2
    return bonuses


def skill_points_per_level(
    base_points: int,
    int_mod: int,
    is_first_level: bool,
    is_human: bool = False,
) -> int:
    """Calculate skill points gained at a given level.

    Reference: PHB p62.

    Rules:
    - Minimum 1 skill point per level (before quadrupling).
    - At 1st level the total is quadrupled.
    - Humans gain +1 skill point per level.

    Args:
        base_points:    Class base skill points per level (e.g. 4 for Rogue).
        int_mod:        Intelligence modifier.
        is_first_level: True if this is character level 1.
        is_human:       True if the character is human.

    Returns:
        Total skill points gained at this level.
    """
    per_level = max(1, base_points + int_mod)
    if is_human:
        per_level += 1
    if is_first_level:
        per_level *= 4
    return per_level
