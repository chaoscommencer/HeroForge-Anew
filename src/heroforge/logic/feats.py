"""Feat slot and prerequisite calculations for HeroForge-Anew.

Reference: PHB p87–88 (feat acquisition), PHB Chapter 5 (feat list).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def feat_slots_available(
    character_level: int,
    fighter_levels: int = 0,
    wizard_levels: int = 0,
) -> int:
    """Return the number of feat slots a character has earned.

    Reference: PHB p87.

    General feat levels: 1, 3, 6, 9, 12, 15, 18.
    Fighters gain a bonus feat every even level (1, 2, 4, 6, 8, …).
    Wizards gain a bonus feat at 1st, 5th, 10th, 15th, 20th wizard level.

    Args:
        character_level: Total character level.
        fighter_levels:  Levels taken in the Fighter class.
        wizard_levels:   Levels taken in the Wizard class.

    Returns:
        Total feat slots available.
    """
    # General feats at levels 1, 3, 6, 9, 12, 15, 18
    general_feat_levels = {1, 3, 6, 9, 12, 15, 18}
    general = sum(1 for lvl in general_feat_levels if lvl <= character_level)

    # Fighter bonus feats at levels 1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20
    fighter_bonus_levels = {1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20}
    fighter_bonus = sum(1 for lvl in fighter_bonus_levels if lvl <= fighter_levels)

    # Wizard bonus feats at wizard levels 1, 5, 10, 15, 20
    wizard_bonus_levels = {1, 5, 10, 15, 20}
    wizard_bonus = sum(1 for lvl in wizard_bonus_levels if lvl <= wizard_levels)

    return general + fighter_bonus + wizard_bonus


# ---------------------------------------------------------------------------
# Prerequisite checking
# ---------------------------------------------------------------------------


def _parse_ability_prereq(prereq: str) -> tuple[str, int] | None:
    """Extract ``(ability_name, minimum_score)`` from a prerequisite string.

    Handles patterns like ``'STR 13'``, ``'Intelligence 13'``.

    Returns:
        Tuple or ``None`` if the string does not match.
    """
    abilities = {
        "str": "STR",
        "strength": "STR",
        "dex": "DEX",
        "dexterity": "DEX",
        "con": "CON",
        "constitution": "CON",
        "int": "INT",
        "intelligence": "INT",
        "wis": "WIS",
        "wisdom": "WIS",
        "cha": "CHA",
        "charisma": "CHA",
    }
    m = re.match(r"^(\w+)\s+(\d+)$", prereq.strip(), re.IGNORECASE)
    if m:
        key = m.group(1).lower()
        if key in abilities:
            return abilities[key], int(m.group(2))
    return None


def _parse_bab_prereq(prereq: str) -> int | None:
    """Extract minimum BAB value from strings like ``'+6 BAB'`` or ``'BAB +6'``."""
    m = re.search(r"bab\s*\+?(\d+)|bab.*?(\d+)|\+?(\d+)\s*bab", prereq, re.IGNORECASE)
    if m:
        val = m.group(1) or m.group(2) or m.group(3)
        return int(val) if val else None
    return None


def _parse_skill_prereq(prereq: str) -> tuple[str, float] | None:
    """Extract ``(skill_name, minimum_ranks)`` from strings like ``'Climb 5 ranks'``."""
    m = re.match(r"^(.+?)\s+(\d+(?:\.\d+)?)\s*ranks?$", prereq.strip(), re.IGNORECASE)
    if m:
        return m.group(1).strip(), float(m.group(2))
    return None


def check_prerequisites(
    feat_prerequisites: list[str],
    character_bab: int,
    character_ability_scores: dict[str, int],
    character_skills: dict[str, float],
    character_feats: list[str],
    character_level: int,
    feat_prereqs: dict[str, list[str]] | None = None,
    _chain: frozenset[str] | None = None,
    _prereq_map_lower: dict[str, list[str]] | None = None,
) -> bool:
    """Determine whether a character satisfies all prerequisites.

    Supported prerequisite string formats:
    - Ability score: ``'STR 13'``, ``'Intelligence 13'``
    - BAB: ``'+6 BAB'``, ``'BAB +6'``
    - Feat: exact feat name string
    - Skill: ``'Climb 5 ranks'``
    - Level: ``'Character level 5'``

    Unknown prerequisite formats are conservatively assumed to be *not met*.

    When a *feat_prereqs* mapping is supplied, feat-name prerequisites are
    validated **recursively**: a chained prerequisite feat is only considered
    satisfied if the character also meets that feat's own prerequisites.  This
    walks the full prerequisite tree (PHB Chapter 5) rather than checking a
    single level, and is guarded against cycles via ``_chain``.

    Reference: PHB Chapter 5 (individual feat entries).

    Args:
        feat_prerequisites:      List of prerequisite strings.
        character_bab:           Character's current base attack bonus.
        character_ability_scores: Mapping of ability name → score.
        character_skills:        Mapping of skill name → ranks.
        character_feats:         List of feat names the character possesses.
        character_level:         Total character level.
        feat_prereqs:            Optional mapping of feat name → prerequisite
            strings used to recurse through nested feat prerequisites.  When
            ``None`` (the default) feat-name prerequisites are checked only by
            possession, preserving the original shallow behaviour.
        _chain:                  Internal set of feat names already being
            evaluated higher in the recursion, used to break prerequisite
            cycles.  Callers should not set this.
        _prereq_map_lower:       Internal lowercased copy of *feat_prereqs*,
            built once at the top-level call and reused across recursion.
            Callers should not set this.

    Returns:
        ``True`` if all prerequisites are satisfied, ``False`` otherwise.
    """
    feats_lower = {f.lower() for f in character_feats}
    chain = _chain or frozenset()
    prereq_map_lower = _prereq_map_lower
    if prereq_map_lower is None and feat_prereqs:
        prereq_map_lower = {name.lower(): reqs for name, reqs in feat_prereqs.items()}

    for prereq in feat_prerequisites:
        prereq = prereq.strip()
        if not prereq:
            logger.debug(
                "Received empty prerequisite in prerequisite list: %r",
                feat_prerequisites,
            )
            continue

        # Check ability score prerequisite
        ability_result = _parse_ability_prereq(prereq)
        if ability_result is not None:
            ability, minimum = ability_result
            if character_ability_scores.get(ability, 0) < minimum:
                return False
            continue

        # Check BAB prerequisite
        bab_result = _parse_bab_prereq(prereq)
        if bab_result is not None:
            if character_bab < bab_result:
                return False
            continue

        # Check skill prerequisite
        skill_result = _parse_skill_prereq(prereq)
        if skill_result is not None:
            skill_name, min_ranks = skill_result
            if character_skills.get(skill_name, 0.0) < min_ranks:
                return False
            continue

        # Check level prerequisite
        level_m = re.search(r"character\s+level\s+(\d+)", prereq, re.IGNORECASE)
        if level_m:
            if character_level < int(level_m.group(1)):
                return False
            continue

        # Check feat prerequisite (by name)
        prereq_key = prereq.lower()
        if prereq_key in feats_lower:
            # Recurse into the prerequisite feat's own prerequisites so chained
            # requirements are fully validated.  The cycle guard prevents
            # infinite recursion on self-referential or circular data.
            if prereq_map_lower is not None and prereq_key not in chain:
                nested = prereq_map_lower.get(prereq_key)
                if nested and not check_prerequisites(
                    nested,
                    character_bab,
                    character_ability_scores,
                    character_skills,
                    character_feats,
                    character_level,
                    feat_prereqs=feat_prereqs,
                    _chain=chain | {prereq_key},
                    _prereq_map_lower=prereq_map_lower,
                ):
                    return False
            continue

        # Unknown prerequisite – conservatively fail
        return False

    return True


def available_feats(
    all_feats: list[str],
    feat_prereqs: dict[str, list[str]],
    character_bab: int,
    character_ability_scores: dict[str, int],
    character_skills: dict[str, float],
    character_feats: list[str],
    character_level: int,
) -> list[str]:
    """Return all feats the character qualifies for (and doesn't already have).

    Args:
        all_feats:               Complete list of feat names in the game.
        feat_prereqs:            Mapping of feat name → list of prerequisite strings.
        character_bab:           Current base attack bonus.
        character_ability_scores: Ability score mapping.
        character_skills:        Skill ranks mapping.
        character_feats:         Feats already taken.
        character_level:         Total character level.

    Returns:
        Sorted list of available feat names.
    """
    current_feats_set = set(character_feats)
    result = []
    for feat in all_feats:
        if feat in current_feats_set:
            continue
        prereqs = feat_prereqs.get(feat, [])
        if check_prerequisites(
            prereqs,
            character_bab,
            character_ability_scores,
            character_skills,
            character_feats,
            character_level,
            feat_prereqs=feat_prereqs,
        ):
            result.append(feat)
    return sorted(result)
