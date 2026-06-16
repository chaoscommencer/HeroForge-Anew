"""Prestige class prerequisite checking for HeroForge-Anew.

Reference: PHB Chapter 3 (prestige class descriptions), DMG Chapter 2.
"""

from __future__ import annotations

from heroforge.logic.feats import check_prerequisites


def check_prestige_prerequisites(
    prerequisites: list[str],
    character_bab: int,
    character_ability_scores: dict[str, int],
    character_skills: dict[str, float],
    character_feats: list[str],
    character_level: int,
    character_classes: dict[str, int],
) -> bool:
    """Determine whether a character meets all prerequisites for a prestige class.

    Extends the generic feat prerequisite checker with support for
    class-level prerequisites (e.g. ``'Spellcaster level 3'``).

    Reference: PHB p168 (Prestige Class descriptions).

    Args:
        prerequisites:           List of prerequisite strings.
        character_bab:           Current base attack bonus.
        character_ability_scores: Ability score mapping.
        character_skills:        Skill ranks mapping.
        character_feats:         Feats already taken.
        character_level:         Total character level.
        character_classes:       Mapping of class name → levels taken.

    Returns:
        ``True`` if all prerequisites are satisfied.
    """
    import re

    for prereq in prerequisites:
        prereq = prereq.strip()
        if not prereq:
            continue

        # Check class-level prerequisites: "Wizard 5", "Fighter 2", …
        class_m = re.match(r"^(\w[\w\s]*?)\s+(\d+)$", prereq, re.IGNORECASE)
        if class_m:
            cls_name = class_m.group(1).strip()
            min_level = int(class_m.group(2))
            # Try matching against known class names (case-insensitive)
            matched = False
            for cls, lvl in character_classes.items():
                if cls.lower() == cls_name.lower():
                    if lvl >= min_level:
                        matched = True
                    else:
                        return False
                    break
            if matched:
                continue

        # Delegate to the generic checker for ability/BAB/feat/skill prereqs
        if not check_prerequisites(
            [prereq],
            character_bab,
            character_ability_scores,
            character_skills,
            character_feats,
            character_level,
        ):
            return False

    return True


def available_prestige_classes(
    all_prestige_classes: list[dict],  # type: ignore[type-arg]
    prereq_map: dict[str, list[str]],
    character_bab: int,
    character_ability_scores: dict[str, int],
    character_skills: dict[str, float],
    character_feats: list[str],
    character_level: int,
    character_classes: dict[str, int],
) -> list[str]:
    """Return prestige class names that the character currently qualifies for.

    Args:
        all_prestige_classes: List of prestige class dicts with at least a
                              ``'name'`` key.
        prereq_map:           Mapping of prestige class name → prerequisite list.
        character_bab:        Current BAB.
        character_ability_scores: Ability scores.
        character_skills:     Skill ranks.
        character_feats:      Feats taken.
        character_level:      Total character level.
        character_classes:    Class levels taken.

    Returns:
        Sorted list of available prestige class names.
    """
    result = []
    for pc in all_prestige_classes:
        name = pc.get("name", "")
        if not name:
            continue
        prereqs = prereq_map.get(name, [])
        if check_prestige_prerequisites(
            prereqs,
            character_bab,
            character_ability_scores,
            character_skills,
            character_feats,
            character_level,
            character_classes,
        ):
            result.append(name)
    return sorted(result)
