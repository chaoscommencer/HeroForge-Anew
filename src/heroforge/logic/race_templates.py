"""Racial and template adjustment logic for HeroForge-Anew.

This module ports the *Race Info* / *Template Info* workbook behaviour that
applies a base race's and any layered templates' ability adjustments, size,
and level adjustment (LA) to a character.

Stacking rules (mirroring the workbook):

* **Ability adjustments** from the base race and from every applied template
  stack *additively* – each contributor's per-ability bonus/penalty is summed.
* **Level adjustment** likewise sums the race's LA with each template's LA to
  give a total LA, which combines with class levels to produce the effective
  character level (ECL = class level + total LA).  Reference: DMG p199.

The functions are deliberately pure – they operate on plain race/template
value objects (anything exposing ``str_adj`` … ``cha_adj`` and
``level_adjustment``), so they have no Qt or database dependencies and the
data-access layer can depend on this module rather than the reverse.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

_ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

# Map each ability key to the adjustment attribute name on race/template rows.
_ADJ_ATTR: Mapping[str, str] = {
    "STR": "str_adj",
    "DEX": "dex_adj",
    "CON": "con_adj",
    "INT": "int_adj",
    "WIS": "wis_adj",
    "CHA": "cha_adj",
}

# Minimum effective ability score after adjustments.  A racial/template penalty
# can lower a score, but never below 1 (mirrors PHB ability-damage flooring).
_MIN_SCORE = 1


class _AbilityAdjustable(Protocol):
    """Anything that carries the six ability-adjustment fields."""

    str_adj: int
    dex_adj: int
    con_adj: int
    int_adj: int
    wis_adj: int
    cha_adj: int


def ability_adjustments(
    race: _AbilityAdjustable | None,
    templates: Sequence[_AbilityAdjustable] | None = None,
) -> dict[str, int]:
    """Return the summed per-ability adjustment from *race* and *templates*.

    The base race and every template stack additively (D&D 3.5 / workbook
    rule), so the result for each ability is the sum of that ability's
    adjustment across all contributors.  Missing contributors contribute ``0``.

    Args:
        race:       The base race (or ``None`` for an unset/custom race).
        templates:  Templates applied on top of the race, in order.

    Returns:
        Mapping of ability key (``"STR"`` …) to total adjustment.
    """
    totals = {ability: 0 for ability in _ABILITIES}
    contributors: list[_AbilityAdjustable] = []
    if race is not None:
        contributors.append(race)
    contributors.extend(templates or [])
    for contributor in contributors:
        for ability, attr in _ADJ_ATTR.items():
            totals[ability] += int(getattr(contributor, attr, 0) or 0)
    return totals


def apply_ability_adjustments(
    base_scores: Mapping[str, int],
    race: _AbilityAdjustable | None,
    templates: Sequence[_AbilityAdjustable] | None = None,
) -> dict[str, int]:
    """Apply racial + template ability adjustments to *base_scores*.

    Each ability's effective score is its base score plus the stacked
    adjustment, floored at :data:`_MIN_SCORE` so a penalty never drives a
    score below 1.  Abilities absent from *base_scores* default to 10.

    Args:
        base_scores: The character's raw (pre-race) ability scores.
        race:        The base race (or ``None``).
        templates:   Applied templates, in order.

    Returns:
        A new mapping of ability key to effective score.
    """
    adjustments = ability_adjustments(race, templates)
    return {
        ability: max(
            _MIN_SCORE,
            int(base_scores.get(ability, 10)) + adjustments[ability],
        )
        for ability in _ABILITIES
    }


class _LevelAdjustable(Protocol):
    """Anything that carries a ``level_adjustment`` field."""

    level_adjustment: int


def total_level_adjustment(
    race: _LevelAdjustable | None,
    templates: Sequence[_LevelAdjustable] | None = None,
) -> int:
    """Return the combined level adjustment of *race* plus *templates*.

    Level adjustments stack additively (DMG p199): the race's LA is summed
    with every template's LA.  Missing contributors contribute ``0``.
    """
    total = 0
    if race is not None:
        total += int(getattr(race, "level_adjustment", 0) or 0)
    for template in templates or []:
        total += int(getattr(template, "level_adjustment", 0) or 0)
    return total


def effective_character_level(
    class_level: int,
    race: _LevelAdjustable | None,
    templates: Sequence[_LevelAdjustable] | None = None,
) -> int:
    """Return the effective character level (ECL).

    ECL is the sum of class levels and the total level adjustment from the
    race and any templates (``ECL = class level + total LA``).  Reference:
    DMG p199.
    """
    return int(class_level) + total_level_adjustment(race, templates)
