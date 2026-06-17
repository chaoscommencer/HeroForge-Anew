"""Animal companion level-based stat progression for HeroForge-Anew.

Reference: PHB p35–36 (Druid "Animal Companion" class feature and the *Animal
Companion Basics* / *Companion Statistics* tables), p47 (Ranger).

In the original Excel source (``HeroForge Anew 3.5 v7.4.0.1.xlsm``, tab 9 –
*Animal Companion*) the companion's bonus Hit Dice, natural-armor adjustment,
Strength/Dexterity adjustment, bonus tricks and extra special qualities all
scale with the master's *effective druid level* rather than being entered by
hand.  This module ports that progression so the values can be derived
automatically and applied on top of the companion's base creature stats.

The effective druid level is the sum of every companion-granting class's
contribution (a Druid counts its full level; a Ranger counts half its level,
rounded down – PHB p47), optionally boosted by the Natural Bond feat (+3) but
never exceeding the character's total level (see CHANGELOG Issue #98).

Design notes:

* The progression table is the single structured source of truth, mirroring the
  workbook's lookup table; the per-level values are *generated* from it so the
  displayed numbers can never drift from the applied mechanics.
* Every function is pure (no Qt or database dependency) so it is trivially
  unit-testable, matching the style of :mod:`heroforge.logic.wild_shape` and
  :mod:`heroforge.logic.familiar`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

# The Natural Bond feat (Complete Adventurer p110) adds +3 to the effective
# druid level used for the animal companion, capped at the character's level.
NATURAL_BOND_FEAT = "Natural Bond"
NATURAL_BOND_BONUS = 3


@dataclass(frozen=True)
class CompanionProgression:
    """One tier of the standard animal-companion progression (PHB p36).

    Attributes:
        min_level:          Lowest effective druid level in this tier.
        max_level:          Highest effective druid level in this tier.
        bonus_hd:           Additional d8 Hit Dice granted to the companion.
        natural_armor:      Adjustment added to the companion's natural armor.
        ability_adjustment: Adjustment added to *both* Strength and Dexterity.
        bonus_tricks:       Number of bonus tricks the companion knows.
        special:            The new special quality unlocked at this tier
                            (empty when the tier adds nothing new).
    """

    min_level: int
    max_level: int
    bonus_hd: int
    natural_armor: int
    ability_adjustment: int
    bonus_tricks: int
    special: str = ""


# The canonical PHB p36 standard-companion table, keyed on effective druid
# level.  The ``special`` column lists only the *newly gained* quality for the
# tier; earlier qualities persist (see :func:`cumulative_special_qualities`).
STANDARD_COMPANION_PROGRESSION: tuple[CompanionProgression, ...] = (
    CompanionProgression(1, 2, 0, 0, 0, 1, "Link, share spells"),
    CompanionProgression(3, 5, 2, 2, 1, 2, "Evasion"),
    CompanionProgression(6, 8, 4, 4, 2, 3, "Devotion"),
    CompanionProgression(9, 11, 6, 6, 3, 4, "Multiattack"),
    CompanionProgression(12, 14, 8, 8, 4, 5),
    CompanionProgression(15, 17, 10, 10, 5, 6, "Improved evasion"),
    CompanionProgression(18, 20, 12, 12, 6, 7),
)


@dataclass(frozen=True)
class ProgressionLabel:
    """A field heading shown on the Animal Companion tab (workbook tab 9).

    Attributes:
        field_key: Stable identifier for the progression field.
        label:     The human-readable heading text as it appears on the
            workbook's *Animal Companion* tab.
    """

    field_key: str
    label: str


# Row headings for the level-progression summary, transcribed from the
# workbook's *Animal Companion* tab (``HeroForge Anew 3.5 v7.4.0.1.xlsm`` tab 9).
# Kept here as the single structured source of truth seeded into the
# ``companion_progression_labels`` table and read back by the UI so the headings
# are never hardcoded at runtime (the constant is only an offline fallback).
COMPANION_PROGRESSION_LABELS: tuple[ProgressionLabel, ...] = (
    ProgressionLabel("effective_druid_level", "Effective Druid Level"),
    ProgressionLabel("bonus_hd", "Bonus HD"),
    ProgressionLabel("natural_armor", "Natural Armor Adj."),
    ProgressionLabel("ability_adjustment", "Str/Dex Adj."),
    ProgressionLabel("bonus_tricks", "Bonus Tricks"),
    ProgressionLabel("special", "Special"),
)


# Map a companion-granting class (lower-cased) to a function returning that
# class's contribution to the effective druid level.  Extensible: add further
# classes/archetypes here without touching the lookup logic.
_EFFECTIVE_LEVEL_SOURCES: dict[str, Callable[[int], int]] = {
    "druid": lambda level: level,
    "ranger": lambda level: level // 2,
}

# Parses a Hit Dice expression such as ``"3d8+6"`` or ``"5d10"`` into its
# component groups: number of dice, die size, and optional flat modifier.
_HIT_DICE_RE = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def companion_progression(
    effective_level: int,
    table: Iterable[CompanionProgression] = STANDARD_COMPANION_PROGRESSION,
) -> CompanionProgression | None:
    """Return the progression tier for *effective_level*.

    Args:
        effective_level: The master's effective druid level (1+).
        table:           Progression tiers to search (defaults to the PHB table).

    Returns:
        The matching :class:`CompanionProgression`, or ``None`` when
        *effective_level* is below the first tier (no companion yet).  Levels
        above the final tier clamp to it (the table tops out at 20th).
    """
    if effective_level < 1:
        return None
    last: CompanionProgression | None = None
    for tier in table:
        if tier.min_level <= effective_level <= tier.max_level:
            return tier
        last = tier
    # Above the table's range: clamp to the highest tier.
    if last is not None and effective_level > last.max_level:
        return last
    return None


def cumulative_special_qualities(
    effective_level: int,
    table: Iterable[CompanionProgression] = STANDARD_COMPANION_PROGRESSION,
) -> tuple[str, ...]:
    """Return every special quality a companion has gained by *effective_level*.

    The PHB ``Special`` column is cumulative: a 9th-level druid's companion has
    Link, share spells, Evasion, Devotion *and* Multiattack.  Each tier's entry
    may list several comma-separated qualities (e.g. ``"Link, share spells"``);
    they are split into individual qualities here.

    Args:
        effective_level: The master's effective druid level.
        table:           Progression tiers to search (defaults to the PHB table).

    Returns:
        The gained special qualities in acquisition order (empty when no
        companion is available).
    """
    if effective_level < 1:
        return ()
    qualities: list[str] = []
    for tier in table:
        if tier.min_level > effective_level:
            break
        if not tier.special:
            continue
        for quality in tier.special.split(","):
            cleaned = quality.strip()
            if cleaned:
                qualities.append(cleaned)
    return tuple(qualities)


def effective_druid_level(
    classes: Iterable[tuple[str, int]],
    feats: Iterable[str] = (),
    character_level: int | None = None,
) -> int:
    """Return the effective druid level for animal-companion purposes.

    Sums each companion-granting class's contribution (Druid counts its full
    level; Ranger counts half its level, rounded down – PHB p47).  The Natural
    Bond feat adds +3, but the result is capped at the character's total level
    (CHANGELOG Issue #98).

    Args:
        classes:         ``(class_name, level)`` pairs for the character.
        feats:           The character's feats (checked for Natural Bond).
        character_level: The character's total level used as the hard cap.
            Defaults to the sum of *classes* levels when not supplied.

    Returns:
        The effective druid level (``0`` when no companion-granting class is
        present).
    """
    class_list = list(classes)
    level = 0
    for name, class_level in class_list:
        source = _EFFECTIVE_LEVEL_SOURCES.get(str(name).strip().lower())
        if source is not None:
            level += int(source(class_level))
    if level <= 0:
        return 0
    has_natural_bond = any(
        str(feat).strip().lower() == NATURAL_BOND_FEAT.lower() for feat in feats
    )
    if has_natural_bond:
        level += NATURAL_BOND_BONUS
    cap = (
        character_level
        if character_level is not None
        else sum(lvl for _, lvl in class_list)
    )
    if cap > 0:
        level = min(level, cap)
    return level


def _ability_modifier(score: int) -> int:
    """Return the D&D 3.5 ability modifier for *score* (PHB p8)."""
    return (score - 10) // 2


def adjust_hit_dice(hit_dice: str, bonus_hd: int, con_score: int | None = None) -> str:
    """Return *hit_dice* with *bonus_hd* extra d8 Hit Dice applied.

    Animal companion bonus HD are d8 (the animal Hit Die).  The flat modifier is
    recomputed from *con_score* when supplied (Constitution modifier × total
    Hit Dice, the standard animal-HP calculation, PHB p36); otherwise the
    original modifier is preserved.

    Args:
        hit_dice:  The companion's base Hit Dice string (e.g. ``"3d8+6"``).
        bonus_hd:  Additional Hit Dice to add (``0`` leaves the string intact).
        con_score: The companion's Constitution score used to recompute the flat
            modifier; ``None`` keeps the original modifier.

    Returns:
        The adjusted Hit Dice string.  When *hit_dice* cannot be parsed it is
        returned unchanged.
    """
    match = _HIT_DICE_RE.match(hit_dice or "")
    if match is None:
        return hit_dice
    count = int(match.group(1))
    die = int(match.group(2))
    new_count = count + max(0, bonus_hd)
    if con_score is not None:
        modifier = _ability_modifier(con_score) * new_count
    else:
        raw = match.group(3)
        modifier = int(raw.replace(" ", "")) if raw else 0
    result = f"{new_count}d{die}"
    if modifier > 0:
        result += f"+{modifier}"
    elif modifier < 0:
        result += f"{modifier}"
    return result


@dataclass(frozen=True)
class CompanionStats:
    """The companion stats after applying a progression tier.

    Attributes:
        ability_scores: STR/DEX/CON/INT/WIS/CHA after the Str/Dex adjustment.
        natural_armor:  Base natural armor plus the tier's adjustment.
        hit_dice:       Hit Dice string with the bonus Hit Dice applied.
        bonus_hd:       The number of bonus Hit Dice granted.
        bonus_tricks:   The number of bonus tricks the companion knows.
        special_qualities: Cumulative special qualities gained by this level.
    """

    ability_scores: dict[str, int]
    natural_armor: int
    hit_dice: str
    bonus_hd: int
    bonus_tricks: int
    special_qualities: tuple[str, ...]


def apply_progression(
    base_scores: Mapping[str, int],
    base_natural_armor: int,
    base_hit_dice: str,
    effective_level: int,
    table: Iterable[CompanionProgression] = STANDARD_COMPANION_PROGRESSION,
) -> CompanionStats:
    """Apply the level-based progression to a companion's base creature stats.

    Reference: PHB p36.  Strength and Dexterity each gain the tier's ability
    adjustment, natural armor gains its adjustment, and the companion gains
    bonus d8 Hit Dice; bonus tricks and special qualities scale alongside.

    Args:
        base_scores:        The base creature's ability scores.
        base_natural_armor: The base creature's natural-armor bonus.
        base_hit_dice:      The base creature's Hit Dice string (e.g. ``"2d8+4"``).
        effective_level:    The master's effective druid level.
        table:              Progression tiers (defaults to the PHB table).

    Returns:
        A :class:`CompanionStats` snapshot.  When *effective_level* is below the
        first tier the base stats are returned unchanged (no companion bonuses).
    """
    scores = {key: int(value) for key, value in base_scores.items()}
    tier = companion_progression(effective_level, table)
    if tier is None:
        return CompanionStats(
            ability_scores=scores,
            natural_armor=int(base_natural_armor),
            hit_dice=base_hit_dice,
            bonus_hd=0,
            bonus_tricks=0,
            special_qualities=(),
        )
    if "STR" in scores:
        scores["STR"] += tier.ability_adjustment
    if "DEX" in scores:
        scores["DEX"] += tier.ability_adjustment
    return CompanionStats(
        ability_scores=scores,
        natural_armor=int(base_natural_armor) + tier.natural_armor,
        hit_dice=adjust_hit_dice(base_hit_dice, tier.bonus_hd, scores.get("CON")),
        bonus_hd=tier.bonus_hd,
        bonus_tricks=tier.bonus_tricks,
        special_qualities=cumulative_special_qualities(effective_level, table),
    )
