"""Prestige class prerequisite checking for HeroForge-Anew.

Reference: PHB Chapter 3 (prestige class descriptions), DMG Chapter 2.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from heroforge.logic.feats import check_prerequisites
from heroforge.models.class_ import Class

# ---------------------------------------------------------------------------
# Reference prerequisite data (single structured source of truth)
# ---------------------------------------------------------------------------

# Prestige-class prerequisites for the core DMG prestige classes, expressed in
# the grammar understood by :func:`check_prestige_prerequisites` (ability
# scores, base attack bonus, skill ranks, feat names, and class/character
# levels).  The original workbook encodes each prerequisite as a per-cell
# spreadsheet formula evaluated against the live character sheet rather than as
# textual data, so there is no source file to seed from; this mapping is the
# single structured source of truth the application owns (mirroring
# :data:`heroforge.logic.familiar.STANDARD_FAMILIAR_BONUSES`).  Only the
# machine-checkable portion of each prestige class's requirements is listed;
# narrative requirements (alignment, race, "ability to cast 3rd-level arcane
# spells", and similar) are intentionally omitted because the prerequisite
# grammar cannot represent them.
#
# Reference: DMG p176-203 (Prestige Classes).
STANDARD_PRESTIGE_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "Arcane Archer": ("+6 BAB", "Point Blank Shot", "Precise Shot"),
    "Arcane Trickster": (
        "Decipher Script 7 ranks",
        "Disable Device 7 ranks",
        "Escape Artist 7 ranks",
        "Knowledge (arcana) 4 ranks",
    ),
    "Assassin": ("Disguise 4 ranks", "Hide 8 ranks", "Move Silently 8 ranks"),
    "Blackguard": (
        "+6 BAB",
        "Cleave",
        "Improved Sunder",
        "Power Attack",
        "Knowledge (religion) 2 ranks",
    ),
    "Dragon Disciple": ("Knowledge (arcana) 8 ranks",),
    "Duelist": (
        "+6 BAB",
        "Dodge",
        "Mobility",
        "Weapon Finesse",
        "Tumble 5 ranks",
    ),
    "Dwarven Defender": ("+7 BAB", "Dodge", "Endurance", "Toughness"),
    "Horizon Walker": ("Endurance", "Knowledge (geography) 8 ranks"),
    "Mystic Theurge": (
        "Knowledge (arcana) 6 ranks",
        "Knowledge (religion) 6 ranks",
    ),
    "Shadowdancer": (
        "Combat Reflexes",
        "Dodge",
        "Mobility",
        "Hide 10 ranks",
        "Move Silently 8 ranks",
    ),
    "Thaumaturgist": ("Spell Focus (Conjuration)",),
}


# ---------------------------------------------------------------------------
# Custom (homebrew) prestige-class persistence
# ---------------------------------------------------------------------------

# The ``content_type`` used for homebrew classes stored on a character's
# ``custom_content`` list (see :class:`heroforge.models.character.Character`).
# Mirrors the workbook's *Custom Class* sheet.
CUSTOM_CLASS_CONTENT_TYPE = "class"


def custom_class_to_content(cls: Class) -> dict[str, object]:
    """Serialise *cls* to a ``character.custom_content`` entry.

    Returns a ``{content_type, name, definition}`` mapping whose ``definition``
    is a JSON string capturing the remaining class fields so the homebrew class
    round-trips through save/load.
    """
    return {
        "content_type": CUSTOM_CLASS_CONTENT_TYPE,
        "name": cls.name,
        "definition": json.dumps(
            {
                "is_prestige": bool(cls.is_prestige),
                "hit_die": int(cls.hit_die),
                "bab_progression": cls.bab_progression,
                "fort_progression": cls.fort_progression,
                "ref_progression": cls.ref_progression,
                "will_progression": cls.will_progression,
                "skill_points_per_level": int(cls.skill_points_per_level),
                "prerequisites": list(cls.prerequisites),
            }
        ),
    }


def custom_class_from_content(entry: Mapping[str, object]) -> Class | None:
    """Reconstruct a :class:`Class` from a ``custom_content`` entry.

    Returns the decoded class, or ``None`` when *entry* is not a named custom
    class definition.
    """
    if entry.get("content_type") != CUSTOM_CLASS_CONTENT_TYPE:
        return None
    name = str(entry.get("name", "")).strip()
    if not name:
        return None
    data: dict[str, object] = {}
    raw = entry.get("definition")
    if isinstance(raw, str) and raw:
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            data = loaded

    def _int_field(value: object, default: int) -> int:
        # bool is a subclass of int; treat stray booleans as missing rather
        # than coercing True/False to 1/0.
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    def _str_field(value: object, default: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else default

    prereqs_raw = data.get("prerequisites")
    prerequisites = (
        [str(p) for p in prereqs_raw if str(p).strip()]
        if isinstance(prereqs_raw, list)
        else []
    )

    return Class(
        name=name,
        is_prestige=bool(data.get("is_prestige", False)),
        hit_die=_int_field(data.get("hit_die"), 8),
        bab_progression=_str_field(data.get("bab_progression"), "medium"),
        fort_progression=_str_field(data.get("fort_progression"), "poor"),
        ref_progression=_str_field(data.get("ref_progression"), "poor"),
        will_progression=_str_field(data.get("will_progression"), "poor"),
        skill_points_per_level=_int_field(data.get("skill_points_per_level"), 2),
        prerequisites=prerequisites,
    )


def list_custom_classes(
    custom_content: Iterable[Mapping[str, object]],
) -> list[Class]:
    """Return every custom class stored on a character's ``custom_content``."""
    result: list[Class] = []
    for entry in custom_content:
        cls = custom_class_from_content(entry)
        if cls is not None:
            result.append(cls)
    return result


def list_custom_prestige_classes(
    custom_content: Iterable[Mapping[str, object]],
) -> list[Class]:
    """Return only the custom *prestige* classes from ``custom_content``."""
    return [cls for cls in list_custom_classes(custom_content) if cls.is_prestige]


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
