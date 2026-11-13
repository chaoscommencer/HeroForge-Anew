"""Binder vestige logic for HeroForge-Anew.

Reference: *Tome of Magic* (Pact Magic / the Binder class), Excel tab
``Binder Vestiges`` and the reference workbook's ``Class Abilities`` sheet.

A binder forms a *pact* with one or more vestiges – the remnants of entities
exiled from reality – and gains their granted abilities for as long as the
vestige remains bound.  This module ports the two mechanical halves of that
system that the rest of the application needs:

* **Binder level limits.**  A binder can only bind vestiges whose own level is
  no greater than a maximum that scales with effective binder level, and can
  only hold a limited number of vestiges at once.  Both progressions are ported
  directly from the reference workbook's named ranges ``VestigeMaxLevel``
  (``Class Abilities!E4539``) and ``VestigeCount`` (``Class Abilities!E4540``),
  themselves derived from ``effBinLvl`` (``Class Abilities!E4538``).

* **Granted-ability effects.**  Several vestiges grant a constant, always-on
  numeric bonus to an ability score or to Armor Class while bound.  Those that
  feed the derived-stats pipeline are captured in :data:`STANDARD_VESTIGE_EFFECTS`
  – a single structured source of truth transcribed from the granted-ability
  text on the reference workbook's ``Class Abilities`` sheet (mirroring
  :data:`heroforge.logic.familiar.STANDARD_FAMILIAR_BONUSES`).  Bonuses that are
  situational, activated, or scale with binder level are intentionally excluded
  because they are not always-on and so do not feed a computed total.

The functions here are deliberately pure (no Qt or database dependencies) so the
UI and the derived-stats layer can compose them without duplicating the math.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from heroforge.logic.combat import NATURAL_ARMOR_ENHANCEMENT

if TYPE_CHECKING:
    from heroforge.models.character import Character


@dataclass(frozen=True)
class VestigeEffect:
    """A single always-on numeric benefit a bound vestige grants its binder.

    Attributes:
        vestige_name: The granting vestige's name (e.g. ``"Eligor"``).
        target:       The affected stat, in the vocabulary of a buff's
                      ``target_stat``: an ability key (``"STR"`` …) or ``"AC"``.
        bonus_type:   The PHB p176 bonus type (e.g. ``"untyped"``,
                      :data:`NATURAL_ARMOR_ENHANCEMENT`), which decides how the
                      bonus stacks with buffs, magic items and stances.
        value:        Numeric size of the bonus (e.g. ``4``).
        level_steps:  ``(binder level, value)`` pairs, in ascending level
                      order, for a bonus that grows with binder level: the
                      value of the last step the binder level reaches replaces
                      *value*.
    """

    vestige_name: str
    target: str
    bonus_type: str
    value: int
    level_steps: tuple[tuple[int, int], ...] = ()

    def value_at(self, level: int) -> int:
        """Return the bonus at effective binder level *level*."""
        value = self.value
        for min_level, step_value in self.level_steps:
            if level >= min_level:
                value = step_value
        return value


# The canonical always-on vestige bonuses that feed the derived-stats pipeline,
# transcribed from the granted-ability text on the reference workbook's
# ``Class Abilities`` sheet:
#
#   * Eligor's Strength   (E4587): "+4 bonus to strength".
#   * Eligor's Resiliance [sic] (E4588): "+3 enhancement bonus to natural
#     armor", +4 from binder level 16 and +5 from 20 (also ``Armor!T27``).
#   * Paimon's Dexterity  (E4665): "+4 bonus to Dexterity".
#
# Only constant, unconditional bonuses to an ability score or AC appear here;
# situational or activated abilities are excluded because they are not always
# applied.  The ability bonuses carry no type in the source text, so they are
# untyped and stack with everything (PHB p176).
STANDARD_VESTIGE_EFFECTS: tuple[VestigeEffect, ...] = (
    VestigeEffect("Eligor", "STR", "untyped", 4),
    VestigeEffect(
        "Eligor", "AC", NATURAL_ARMOR_ENHANCEMENT, 3, level_steps=((16, 4), (20, 5))
    ),
    VestigeEffect("Paimon", "DEX", "untyped", 4),
)


# Fallback mapping of vestige name → the vestige's own level (1–8), transcribed
# from the ``Binder Vestiges`` sheet (column ``S``).  The runtime source is the
# seeded ``vestiges`` table via
# :meth:`heroforge.db.data_access.GameDataRepository.list_vestiges`; this table
# is consulted through :func:`vestige_level_for` whenever that source has no
# level for a vestige (an unseeded checkout, or a database whose
# ``vestige_level`` column was migrated in but not yet re-seeded).
STANDARD_VESTIGE_LEVELS: dict[str, int] = {
    "Amon": 1,
    "Aym": 1,
    "Leraje": 1,
    "Naberius": 1,
    "Ronove": 1,
    "Dahlver-Nar": 2,
    "Haagenti": 2,
    "Malphas": 2,
    "Savnok": 2,
    "Andromalius": 3,
    "Focalor": 3,
    "Karsus": 3,
    "Paimon": 3,
    "Primus": 3,
    "Agares": 4,
    "Andras": 4,
    "Arete": 4,
    "Astaroth": 4,
    "Astaroth, Unjustly Fallen": 4,
    "Buer": 4,
    "Cabiri": 4,
    "Eurynome": 4,
    "Kas": 4,
    "Tenebrous": 4,
    "Acererak": 5,
    "Balam": 5,
    "Dantalion": 5,
    "Geryon": 5,
    "Otiax": 5,
    "Chupoclops": 6,
    "Desharis": 6,
    "Haures": 6,
    "Ipos": 6,
    "Shax": 6,
    "The Triad": 6,
    "Zagan": 6,
    "Zceryll": 6,
    "Ansitif": 7,
    "Eligor": 7,
    "Marchosias": 7,
    "Abysm": 8,
    "Ashardalon": 8,
    "Halphax": 8,
    "Orthos": 8,
}

_STANDARD_LEVELS_BY_KEY: dict[str, int] = {
    name.lower(): level for name, level in STANDARD_VESTIGE_LEVELS.items()
}


def vestige_level_for(name: str, catalogue_level: int | None = None) -> int | None:
    """Return the level of the vestige *name*, or ``None`` when it is unknown.

    *catalogue_level* (the seeded catalogue's ``vestige_level``) wins when it is
    set; otherwise the name is looked up, case-insensitively, in
    :data:`STANDARD_VESTIGE_LEVELS`.  A vestige outside that table (e.g. a
    homebrew one) has no known level.
    """
    if catalogue_level:
        return catalogue_level
    return _STANDARD_LEVELS_BY_KEY.get(name.strip().lower())


# Classes whose levels count toward effective binder level.  The Binder is the
# only base pact-making class currently modelled; pact-magic prestige classes
# (Anima Mage, Knight of the Sacred Seal, etc.) are not yet seeded and so are
# not counted here.  Compared case-insensitively.
_BINDING_CLASS_NAMES: frozenset[str] = frozenset({"binder"})

# Feats that grant limited vestige binding to non-binders, ported from the
# ``effBinLvl`` fallback ``1 + 4 * FtImprovedBindVestige`` in the reference
# workbook (``Class Abilities!E4538``).
_BIND_VESTIGE_FEAT = "bind vestige"
_IMPROVED_BIND_VESTIGE_FEAT = "improved bind vestige"

# Effective-binder-level thresholds at which the maximum bindable vestige level
# increases by one (Tome of Magic p25; reference workbook ``VestigeMaxLevel``,
# ``Class Abilities!E4539``).
_MAX_VESTIGE_LEVEL_THRESHOLDS: tuple[int, ...] = (1, 3, 5, 7, 10, 12, 15, 17)


def binder_level(character: Character) -> int:
    """Return the character's effective binder level.

    Sums the levels of any binding class (see :data:`_BINDING_CLASS_NAMES`).
    A non-binder who has taken the *Bind Vestige* feat counts as a 1st-level
    binder (5th with *Improved Bind Vestige*), mirroring the ``effBinLvl``
    fallback in the reference workbook (``Class Abilities!E4538``).
    """
    level = sum(
        lvl
        for name, lvl in character.classes
        if name.strip().lower() in _BINDING_CLASS_NAMES
    )
    if level > 0:
        return level
    feats = {str(f).strip().lower() for f in character.feats}
    if _BIND_VESTIGE_FEAT in feats:
        return 5 if _IMPROVED_BIND_VESTIGE_FEAT in feats else 1
    return 0


def max_vestige_level(level: int) -> int:
    """Return the highest vestige level a binder of effective level *level* may bind.

    Ports ``VestigeMaxLevel`` (``Class Abilities!E4539``): the count of the
    thresholds in :data:`_MAX_VESTIGE_LEVEL_THRESHOLDS` that *level* meets, so a
    1st-level binder may bind 1st-level vestiges, a 3rd-level binder 2nd-level
    vestiges, and so on up to 8th-level vestiges at binder level 17.
    """
    return sum(1 for threshold in _MAX_VESTIGE_LEVEL_THRESHOLDS if level >= threshold)


def max_vestiges_bound(level: int) -> int:
    """Return how many vestiges a binder of effective level *level* may bind at once.

    Ports ``VestigeCount`` (``Class Abilities!E4540``): one vestige at binder
    levels 1–7, two at 8–13, three at 14–19, and four at 20 (Tome of Magic p25).
    Returns ``0`` for a non-binder (level ``0``).
    """
    if level < 1:
        return 0
    # Excel INT() floors toward negative infinity; Python floor division matches.
    return (level - 8) // 6 + 2 + (1 if level == 1 else 0)


def can_bind(vestige_level: int | None, level: int) -> bool:
    """Whether a vestige of level *vestige_level* may be bound at binder level *level*.

    An unknown vestige level (``None``) is treated as bindable so the UI never
    blocks a vestige whose level the data layer did not record.
    """
    if vestige_level is None:
        return level >= 1
    return level >= 1 and vestige_level <= max_vestige_level(level)


def bound_vestige_names(character: Character) -> list[str]:
    """Return the names of the character's currently bound (not suppressed) vestiges."""
    names: list[str] = []
    for entry in character.vestiges:
        if not entry.get("bound", True):
            continue
        name = str(entry.get("vestige_name", "")).strip()
        if name:
            names.append(name)
    return names


def vestige_bonus_specs(
    character: Character,
    effects: Iterable[VestigeEffect] = STANDARD_VESTIGE_EFFECTS,
) -> list[dict[str, object]]:
    """Return the bound vestiges' always-on effects as typed bonus specs.

    Each spec is a ``{"source", "target", "bonus_type", "value"}`` dict in the
    same shape as an active stance's
    (:func:`heroforge.logic.maneuvers.stance_bonus_specs`) and an equipped magic
    item's bonus specs, so
    :func:`heroforge.logic.derived_stats.compute_derived_stats` stacks them with
    buffs, items and stances by bonus type (PHB p176).

    Args:
        character: The character whose ``vestiges`` collection is read.
        effects:   Structured vestige-effect records to search (defaults to
            :data:`STANDARD_VESTIGE_EFFECTS`).

    Returns:
        One spec per effect of every bound vestige, sized for the character's
        binder level.
    """
    bound = {name.lower() for name in bound_vestige_names(character)}
    level = binder_level(character)
    return [
        {
            "source": effect.vestige_name,
            "target": effect.target,
            "bonus_type": effect.bonus_type,
            "value": effect.value_at(level),
        }
        for effect in effects
        if effect.vestige_name.lower() in bound
    ]
