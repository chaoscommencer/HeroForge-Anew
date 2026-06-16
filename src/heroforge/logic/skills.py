"""Skill calculations for HeroForge-Anew.

Reference: PHB Chapter 4, p62–105.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# Number of ranks a skill must reach before it grants a synergy bonus (PHB p65).
SYNERGY_RANK_THRESHOLD = 5

# The canonical, *unconditional* PHB p65 skill-synergy pairs.  A character with
# ``SYNERGY_RANK_THRESHOLD`` or more ranks in ``from_skill`` gains a +2 bonus on
# ``to_skill`` checks.  Only synergies that apply in every situation are listed
# here; the many circumstance-specific synergies (e.g. Knowledge (dungeoneering)
# → Survival *while underground*) are deliberately omitted so they are never
# baked into a flat total.  This mirrors the reference workbook's Skills sheet,
# which only adds the unconditional synergies automatically, and serves as the
# offline fallback when the ``skill_synergies`` database table has not been
# seeded (see :meth:`heroforge.db.data_access.GameDataRepository.list_skill_synergies`).
STANDARD_SKILL_SYNERGIES: tuple[tuple[str, str], ...] = (
    ("Bluff", "Diplomacy"),
    ("Bluff", "Intimidate"),
    ("Bluff", "Sleight of Hand"),
    ("Handle Animal", "Ride"),
    ("Jump", "Tumble"),
    ("Knowledge (Arcana)", "Spellcraft"),
    ("Knowledge (Local)", "Gather Information"),
    ("Knowledge (Nature)", "Survival"),
    ("Knowledge (Nobility)", "Diplomacy"),
    ("Sense Motive", "Diplomacy"),
    ("Spellcraft", "Use Magic Device"),
    ("Tumble", "Balance"),
    ("Tumble", "Jump"),
)


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


def qualifying_synergy_skills(ranks_by_skill: Mapping[str, float]) -> list[str]:
    """Return the skills with enough ranks to grant a synergy bonus.

    Reference: PHB p65.  A skill grants its +2 synergy bonus only once the
    character has :data:`SYNERGY_RANK_THRESHOLD` (5) or more ranks in it.

    Args:
        ranks_by_skill: Mapping of skill name → ranks invested.

    Returns:
        The names of the skills with ≥ 5 ranks, in the iteration order of
        *ranks_by_skill*.
    """
    return [
        skill
        for skill, ranks in ranks_by_skill.items()
        if ranks >= SYNERGY_RANK_THRESHOLD
    ]


def skill_points_spent(
    ranks_by_skill: Mapping[str, float],
    class_skills: Iterable[str],
) -> float:
    """Return the total skill points spent for the given rank allocation.

    Reference: PHB p62.  A class skill costs 1 skill point per rank, while a
    cross-class skill costs 2 points per rank (i.e. one point buys half a rank).
    Cross-class half-ranks are therefore costed at :func:`cross_class_rank_cost`
    per whole rank.

    Args:
        ranks_by_skill: Mapping of skill name → ranks invested.
        class_skills:   The names of the character's class skills.

    Returns:
        The total number of skill points spent (may be fractional when
        cross-class half-ranks are used).
    """
    class_skill_set = set(class_skills)
    total = 0.0
    for skill, ranks in ranks_by_skill.items():
        if skill in class_skill_set:
            total += ranks
        else:
            total += ranks * cross_class_rank_cost()
    return total


def total_skill_points(
    class_levels: Iterable[tuple[str, int]],
    base_points_by_class: Mapping[str, int],
    int_mod: int,
    is_human: bool = False,
    *,
    default_base: int = 2,
) -> int:
    """Return the total skill-point budget earned across all class levels.

    Reference: PHB p62.  Each class level grants
    :func:`skill_points_per_level` points based on that class's base value and
    the character's Intelligence modifier; the very first character level
    (the first level of the first class taken) is quadrupled.

    Args:
        class_levels:         ``(class_name, levels)`` tuples in the order the
                              classes were taken (see ``Character.classes``).
        base_points_by_class: Mapping of class name → base skill points per
                              level (e.g. 2 for Fighter, 8 for Rogue).
        int_mod:              The character's Intelligence modifier.
        is_human:             Whether the character is human (+1 point/level).
        default_base:         Base points to assume for a class missing from
                              *base_points_by_class* (the PHB minimum is 2).

    Returns:
        The total skill-point budget available to spend on ranks.
    """
    total = 0
    is_first_level = True
    for class_name, levels in class_levels:
        base = base_points_by_class.get(class_name, default_base)
        for _ in range(max(0, levels)):
            total += skill_points_per_level(
                base, int_mod, is_first_level=is_first_level, is_human=is_human
            )
            is_first_level = False
    return total
