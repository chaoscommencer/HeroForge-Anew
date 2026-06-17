"""Standard familiar master-bonus data, text generation, and mechanics.

Reference: PHB p52–53 (the "Familiars" sidebar of the Wizard class feature).

In the original Excel source (``HeroForge Anew 3.5 v7.4.0.1.xlsm``) the standard
familiars were not stored in a flat "bonus text" table.  Instead the bonus was
both *applied mechanically* and *described* by formulas on the calculation
sheets, keyed on the familiar's creature name (``FamiliarEquivType``):

* Saving throws – ``CS Calc.!B38`` adds ``(FamiliarEquivType="Rat")`` to
  Fortitude and ``CS Calc.!C38`` adds ``(FamiliarEquivType="Weasel")`` to
  Reflex (each multiplied by 2).
* Skills – the ``Skills`` sheet adds ``3*(FamiliarEquivType="Bat")`` to Listen,
  ``"Cat"`` to Move Silently, ``"Lizard"`` to Climb and ``"Raven"`` to Appraise.
* Hit points – ``Classes!H63`` adds ``3*(FamiliarEquivType="Toad")``.

The Hawk and Owl bonuses (Spot, but only under specific lighting) are
*situational* and were therefore never baked into a total by the workbook.

Every familiar additionally grants its master a set of *universal* benefits
(Alertness, Scry on Familiar and Natural Link).  In the workbook these are the
indented lines beneath the ``× Familiar`` entry in the Character Sheet's
*Special Abilities* section (``Class Abilities!A162:A164``); they are captured
here as :class:`FamiliarMasterAbility` records and seeded into the
``familiar_master_abilities`` table.

Two of those universal benefits are mechanical and feed computed totals:

* **Alertness** grants the master +2 on Spot and Listen checks while a familiar
  is present (the workbook's ``2*OR(HasFamiliar, …)`` Skills-sheet term); see
  :func:`skill_bonuses`.
* **Natural Link** doubles the master's familiar bonuses while the familiar is
  within arm's reach.  Because that proximity is situational it is an opt-in
  flag (see :func:`familiar_natural_link`) honoured by :func:`skill_bonuses`
  and :func:`save_bonuses`.

This module captures that data once, as structured :class:`FamiliarBonus`
records, and is the single source of truth used by

* the database seeder (:mod:`heroforge.db.seed`),
* the read-only repository (:class:`heroforge.db.data_access.GameDataRepository`),
* the Familiar tab's offline fallback, and
* the derived-stats pipeline, which applies the non-situational bonuses.

Keeping a single structured definition means the human-readable helper text can
never drift out of sync with the actual bonus: the text is *generated* from the
same numbers that drive the mechanics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Bonus categories.  ``skill`` and ``save`` carry a ``target`` (the skill or
# saving-throw name); ``hp`` targets the character's hit points directly.
KIND_SKILL = "skill"
KIND_SAVE = "save"
KIND_HP = "hp"

# Map a saving-throw ``target`` to the short key used by the saving-throw logic
# and the derived-stats pipeline.
_SAVE_KEYS: dict[str, str] = {
    "Fortitude": "fort",
    "Reflex": "ref",
    "Will": "will",
}

# The Alertness benefit every familiar grants its master while the familiar is
# nearby (PHB p52): a +2 bonus on Spot and Listen checks.  In the reference
# workbook this is applied as ``2*OR(HasFamiliar, …)`` on the Skills sheet — i.e.
# it is gated solely on *having* a familiar, independent of the creature's kind.
ALERTNESS_BONUS = 2
ALERTNESS_SKILLS: tuple[str, ...] = ("Listen", "Spot")


@dataclass(frozen=True)
class FamiliarBonus:
    """A single standard-familiar benefit granted to the master.

    Attributes:
        creature_name: The familiar's creature name (e.g. ``"Bat"``).
        value:         Numeric size of the bonus (e.g. ``3``).
        kind:          One of :data:`KIND_SKILL`, :data:`KIND_SAVE`,
                       :data:`KIND_HP`.
        target:        The affected skill or saving throw (empty for ``hp``).
        condition:     A situational qualifier (e.g. ``"in daylight"``).  When
                       non-empty the bonus is conditional and is *not* applied
                       mechanically.
    """

    creature_name: str
    value: int
    kind: str
    target: str = ""
    condition: str = ""

    @property
    def conditional(self) -> bool:
        """Whether the bonus only applies under a specific circumstance."""
        return bool(self.condition)


# The canonical PHB p52–53 standard-familiar table.  Values, targets and the
# conditional flags mirror the original workbook's mechanical treatment.
STANDARD_FAMILIAR_BONUSES: tuple[FamiliarBonus, ...] = (
    FamiliarBonus("Bat", 3, KIND_SKILL, "Listen"),
    FamiliarBonus("Cat", 3, KIND_SKILL, "Move Silently"),
    FamiliarBonus("Hawk", 3, KIND_SKILL, "Spot", "in daylight"),
    FamiliarBonus("Lizard", 3, KIND_SKILL, "Climb"),
    FamiliarBonus("Owl", 3, KIND_SKILL, "Spot", "in shadows/darkness"),
    FamiliarBonus("Rat", 2, KIND_SAVE, "Fortitude"),
    FamiliarBonus("Raven", 3, KIND_SKILL, "Appraise"),
    FamiliarBonus("Snake", 3, KIND_SKILL, "Bluff"),
    FamiliarBonus("Toad", 3, KIND_HP),
    FamiliarBonus("Weasel", 2, KIND_SAVE, "Reflex"),
)


@dataclass(frozen=True)
class FamiliarMasterAbility:
    """A universal benefit every standard familiar grants its master.

    Unlike :class:`FamiliarBonus` (which varies by creature), these benefits are
    common to *all* familiars.  In the original Excel source they are the
    indented lines that appear immediately beneath the
    ``× Familiar: You have called a <creature> …`` line in the Character Sheet's
    *Special Abilities* section, generated from ``Class Abilities!A162:A164``.

    Attributes:
        name:        The benefit's name (e.g. ``"Alertness"``).
        description: The descriptive text shown to the user.
    """

    name: str
    description: str


# The universal familiar master benefits, common to every standard familiar.
# Mirrors ``Class Abilities!A162:A164`` of the reference workbook and is used as
# the offline fallback when the ``familiar_master_abilities`` table has not been
# seeded (see :meth:`heroforge.db.data_access.GameDataRepository`).
STANDARD_FAMILIAR_MASTER_ABILITIES: tuple[FamiliarMasterAbility, ...] = (
    FamiliarMasterAbility(
        "Alertness",
        "While the familiar is within arms reach; you gain the Alertness feat "
        "(+2 to Spot & Listen checks).",
    ),
    FamiliarMasterAbility(
        "Scry on Familiar (Sp)",
        "You may scry on your familiar once per day.",
    ),
    FamiliarMasterAbility(
        "Natural Link (Su)",
        "When your familiar is within arms reach, your bonus on skills, saves, "
        "or hit points doubles. Your familiar does not have the ability to "
        "deliver touch spells or speak with animals of its kind.",
    ),
)


# The ``content_type`` used for homebrew familiars stored on a character's
# ``custom_content`` list (see :class:`heroforge.models.character.Character`).
# This mirrors the workbook's *Custom Familiar* sheet (Excel tab 9c).
CUSTOM_FAMILIAR_CONTENT_TYPE = "familiar"


@dataclass(frozen=True)
class CustomFamiliar:
    """A homebrew familiar defined by the user via the Custom Familiar dialog.

    Custom familiars are persisted on a character's ``custom_content`` list (one
    ``{content_type, name, definition}`` entry per familiar, where ``definition``
    is a JSON blob) so they round-trip through save/load and become selectable on
    the Familiar tab.  This mirrors the workbook's *Custom Familiar* sheet
    (Excel tab 9c).

    Attributes:
        name:          The familiar's unique name (its selectable identifier).
        kind:          The creature kind/species (free text, e.g. ``"Pseudodragon"``).
        special_bonus: Free-text description of the bonus granted to the master.
        intelligence:  The familiar's Intelligence score.
        natural_armor: The familiar's natural-armor bonus.
    """

    name: str
    kind: str = ""
    special_bonus: str = ""
    intelligence: int = 6
    natural_armor: int = 0

    def to_content(self) -> dict[str, object]:
        """Serialise to a ``character.custom_content`` entry.

        Returns:
            A ``{content_type, name, definition}`` mapping whose ``definition``
            is a JSON string capturing the remaining fields.
        """
        return {
            "content_type": CUSTOM_FAMILIAR_CONTENT_TYPE,
            "name": self.name,
            "definition": json.dumps(
                {
                    "kind": self.kind,
                    "special_bonus": self.special_bonus,
                    "intelligence": self.intelligence,
                    "natural_armor": self.natural_armor,
                }
            ),
        }


def _coerce_int(value: object, default: int) -> int:
    """Return *value* as an ``int``, falling back to *default* when invalid."""
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


def custom_familiar_from_content(
    entry: Mapping[str, object],
) -> CustomFamiliar | None:
    """Reconstruct a :class:`CustomFamiliar` from a ``custom_content`` entry.

    Args:
        entry: A single ``{content_type, name, definition}`` mapping.

    Returns:
        The decoded :class:`CustomFamiliar`, or ``None`` when *entry* is not a
        named familiar definition.
    """
    if entry.get("content_type") != CUSTOM_FAMILIAR_CONTENT_TYPE:
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

    def _str_field(value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    return CustomFamiliar(
        name=name,
        kind=_str_field(data.get("kind")),
        special_bonus=_str_field(data.get("special_bonus")),
        intelligence=_coerce_int(data.get("intelligence"), 6),
        natural_armor=_coerce_int(data.get("natural_armor"), 0),
    )


def list_custom_familiars(
    custom_content: Iterable[Mapping[str, object]],
) -> list[CustomFamiliar]:
    """Return every custom familiar stored on a character's ``custom_content``.

    Args:
        custom_content: The character's ``custom_content`` collection.

    Returns:
        The decoded custom familiars in their stored order (named entries only).
    """
    result: list[CustomFamiliar] = []
    for entry in custom_content:
        familiar = custom_familiar_from_content(entry)
        if familiar is not None:
            result.append(familiar)
    return result


def describe_bonus(bonus: FamiliarBonus) -> str:
    """Compose the human-readable helper text for *bonus*.

    The wording is derived entirely from the structured fields, so it always
    reflects the actual numbers and target.

    Args:
        bonus: The structured familiar benefit.

    Returns:
        A sentence such as ``"Master gains +3 bonus on Listen checks."``.
    """
    if bonus.kind == KIND_HP:
        return f"Master gains +{bonus.value} hit points."
    if bonus.kind == KIND_SAVE:
        return f"Master gains +{bonus.value} bonus on {bonus.target} saves."
    # Default: a skill bonus, optionally qualified by a condition.
    text = f"Master gains +{bonus.value} bonus on {bonus.target} checks"
    if bonus.condition:
        text += f" {bonus.condition}"
    return text + "."


def selected_familiar_kind(
    companions: Iterable[Mapping[str, object]],
) -> str | None:
    """Return the creature kind of the character's familiar, if any.

    Args:
        companions: The character's ``companions`` collection (each a mapping
            with at least ``companion_type`` and ``creature`` keys).

    Returns:
        The familiar's creature name, or ``None`` when no familiar is set.
    """
    for entry in companions:
        if entry.get("companion_type") != "familiar":
            continue
        creature = str(entry.get("creature", "")).strip()
        return creature or None
    return None


def familiar_natural_link(
    companions: Iterable[Mapping[str, object]],
) -> bool:
    """Return whether the character's familiar has Natural Link active.

    The Natural Link benefit (PHB p52, as treated by the reference workbook)
    doubles a familiar's mechanical bonuses while the familiar is within arm's
    reach.  Because that proximity is situational it is stored as an opt-in flag
    on the familiar's companion entry (the ``natural_link`` key inside the JSON
    ``notes`` blob written by the Familiar tab).

    Args:
        companions: The character's ``companions`` collection.

    Returns:
        ``True`` when a familiar is present and its ``natural_link`` flag is set,
        otherwise ``False``.
    """
    for entry in companions:
        if entry.get("companion_type") != "familiar":
            continue
        raw = entry.get("notes")
        if isinstance(raw, str) and raw:
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                return False
            return bool(data.get("natural_link", False))
        return False
    return False


def _doubled(values: dict[str, int], active: bool) -> dict[str, int]:
    """Return *values* with each entry doubled when *active* (Natural Link)."""
    if not active:
        return values
    return {key: value * 2 for key, value in values.items()}


def save_bonuses(
    creature_name: str | None,
    bonuses: Iterable[FamiliarBonus],
    *,
    natural_link: bool = False,
) -> dict[str, int]:
    """Return the non-situational saving-throw bonuses for *creature_name*.

    Only unconditional ``save`` bonuses are returned, so situational benefits
    (e.g. Hawk/Owl) never feed a computed total.  The result is keyed by the
    short save keys (``"fort"``, ``"ref"``, ``"will"``) used by
    :mod:`heroforge.logic.saving_throws`.

    Args:
        creature_name: The selected familiar's creature name (case-insensitive),
            or ``None``.
        bonuses:       Structured familiar-bonus records to search.
        natural_link:  When ``True`` the master's familiar bonuses double
            (Natural Link, PHB p52).

    Returns:
        Mapping of save key → bonus value (empty when nothing applies).
        Values accumulate additively when several unconditional save bonuses
        share a target, so custom multi-bonus familiars are summed correctly;
        the standard PHB familiars each define a single save bonus.
    """
    if not creature_name:
        return {}
    name = creature_name.strip().lower()
    result: dict[str, int] = {}
    for bonus in bonuses:
        if bonus.creature_name.lower() != name:
            continue
        if bonus.kind != KIND_SAVE or bonus.conditional:
            continue
        key = _SAVE_KEYS.get(bonus.target)
        if key is not None:
            result[key] = result.get(key, 0) + bonus.value
    return _doubled(result, natural_link)


def skill_bonuses(
    creature_name: str | None,
    bonuses: Iterable[FamiliarBonus],
    *,
    natural_link: bool = False,
) -> dict[str, int]:
    """Return the non-situational skill bonuses a familiar grants its master.

    Two sources are combined, keyed by skill name:

    * the creature-specific unconditional skill bonus (e.g. a Bat's +3 Listen),
      and
    * the universal Alertness benefit (+2 to Spot and Listen), which every
      familiar grants regardless of kind.

    Situational bonuses (e.g. the Hawk/Owl lighting-dependent Spot bonus) are
    skipped so they never feed a computed total.  When *natural_link* is set the
    combined bonuses double (Natural Link, PHB p52).

    Args:
        creature_name: The selected familiar's creature name (case-insensitive),
            or ``None``.
        bonuses:       Structured familiar-bonus records to search.
        natural_link:  When ``True`` the master's familiar bonuses double.

    Returns:
        Mapping of skill name → bonus value (empty when no familiar is set).
    """
    if not creature_name:
        return {}
    name = creature_name.strip().lower()
    result: dict[str, int] = {}
    for bonus in bonuses:
        if bonus.creature_name.lower() != name:
            continue
        if bonus.kind != KIND_SKILL or bonus.conditional or not bonus.target:
            continue
        result[bonus.target] = result.get(bonus.target, 0) + bonus.value
    # Alertness: every familiar grants its master +2 Spot & Listen.
    for skill in ALERTNESS_SKILLS:
        result[skill] = result.get(skill, 0) + ALERTNESS_BONUS
    return _doubled(result, natural_link)
