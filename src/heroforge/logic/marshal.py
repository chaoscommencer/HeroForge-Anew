"""Marshal aura mechanics and effect application for HeroForge-Anew.

Reference: *Miniatures Handbook* p11–12 (the Marshal base class and its minor
and major auras), with the *Draconic* auras drawn from *Dragon Magic* p20.

A marshal projects an *aura* that grants a bonus to himself and to every ally
within 60 feet:

* **Minor auras** grant a bonus equal to the marshal's Charisma bonus (a
  non-positive Charisma modifier confers no benefit).
* **Major auras** grant a bonus equal to one-half the marshal's marshal level
  (rounded down, minimum +1).

In the reference workbook (``HeroForge Anew 3.5 v7.4.0.1.xlsm``) the *Marshal
Auras* sheet stores only the aura **names** and whether each is *Minor* or
*Major* (columns ``B`` and ``E``).  The *mechanical* effect of each aura — which
roll or statistic it modifies — is not present in that data table; it lived in
the workbook's calculation formulas instead.  Following the same convention used
for the standard familiars (:data:`heroforge.logic.familiar.STANDARD_FAMILIAR_BONUSES`),
this module captures that mechanical mapping once, as a structured
:class:`MarshalAura` catalogue, and is the single source of truth used by

* the database seeder (to enrich the ``marshal_auras`` table's ``bonus_type`` and
  ``description`` columns, which the workbook leaves blank), and
* the derived-stats pipeline, which applies the bonuses of the character's
  *active* auras.

Only the auras whose effect maps onto a value the application currently derives
(saving throws, Armor Class, and melee/ranged attack) contribute a numeric
bonus; the remaining auras affect rolls the derived-stats snapshot does not yet
model (damage, speed, ability checks, skill checks, situational defences) and are
catalogued for display and selection only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

#: The two aura categories from the *Miniatures Handbook*.
MINOR = "Minor"
MAJOR = "Major"

# Machine-readable effect targets.  ``""`` marks an aura whose effect the
# derived-stats snapshot does not (yet) model; such auras contribute no numeric
# bonus but remain selectable and described.
TARGET_FORT = "fort"
TARGET_REF = "ref"
TARGET_WILL = "will"
TARGET_SAVES = "saves"  # all three saving throws
TARGET_AC = "ac"
TARGET_MELEE = "melee"
TARGET_RANGED = "ranged"
TARGET_NONE = ""


@dataclass(frozen=True)
class MarshalAura:
    """A single marshal aura and the statistic it modifies.

    Attributes:
        name:        The aura's name (its selectable identifier), matching the
                     *Marshal Auras* sheet of the reference workbook.
        aura_type:   :data:`MINOR` or :data:`MAJOR`.
        target:      Machine-readable effect key (one of the ``TARGET_*``
                     constants).  :data:`TARGET_NONE` for auras whose effect the
                     derived-stats snapshot does not model.
        bonus_type:  The D&D bonus type for stacking purposes.  Marshal auras are
                     untyped (empty string), so they stack with typed bonuses.
        description: Human-readable rules text shown in the UI and seeded into the
                     ``marshal_auras`` table's ``description`` column.
    """

    name: str
    aura_type: str
    target: str = TARGET_NONE
    bonus_type: str = ""
    description: str = ""

    @property
    def affects_derived_stats(self) -> bool:
        """Whether this aura contributes a bonus the derived stats model."""
        return self.target != TARGET_NONE


# The canonical aura catalogue.  Names and Minor/Major typing mirror the
# workbook's *Marshal Auras* sheet; the ``target`` and ``description`` capture
# the *Miniatures Handbook* (and *Dragon Magic*) rules text for each aura.
STANDARD_MARSHAL_AURAS: tuple[MarshalAura, ...] = (
    # --- Minor auras (bonus = marshal's Charisma modifier) -----------------
    MarshalAura(
        "Accurate Strike",
        MINOR,
        TARGET_NONE,
        description="Bonus on rolls made to confirm critical hits.",
    ),
    MarshalAura(
        "Art of War",
        MINOR,
        TARGET_NONE,
        description="Bonus on bull rush, disarm, feint, overrun, sunder, "
        "and trip attempts.",
    ),
    MarshalAura(
        "Demand Fortitude",
        MINOR,
        TARGET_FORT,
        description="Bonus on Fortitude saves.",
    ),
    MarshalAura(
        "Determined Caster",
        MINOR,
        TARGET_NONE,
        description="Bonus on caster level checks to overcome spell resistance.",
    ),
    MarshalAura(
        "Force of Will",
        MINOR,
        TARGET_WILL,
        description="Bonus on Will saves.",
    ),
    MarshalAura(
        "Master of Opportunity",
        MINOR,
        TARGET_NONE,
        description="Bonus to Armor Class against attacks of opportunity.",
    ),
    MarshalAura(
        "Master of Tactics",
        MINOR,
        TARGET_NONE,
        description="Bonus on damage rolls when flanking an opponent.",
    ),
    MarshalAura(
        "Motivate Charisma",
        MINOR,
        TARGET_NONE,
        description="Bonus on Charisma checks and Charisma-based skill checks.",
    ),
    MarshalAura(
        "Motivate Constitution",
        MINOR,
        TARGET_NONE,
        description="Bonus on Constitution checks.",
    ),
    MarshalAura(
        "Motivate Dexterity",
        MINOR,
        TARGET_NONE,
        description="Bonus on Dexterity checks and Dexterity-based skill checks.",
    ),
    MarshalAura(
        "Motivate Intelligence",
        MINOR,
        TARGET_NONE,
        description="Bonus on Intelligence checks and Intelligence-based "
        "skill checks.",
    ),
    MarshalAura(
        "Motivate Strength",
        MINOR,
        TARGET_NONE,
        description="Bonus on Strength checks and Strength-based skill checks.",
    ),
    MarshalAura(
        "Motivate Wisdom",
        MINOR,
        TARGET_NONE,
        description="Bonus on Wisdom checks and Wisdom-based skill checks.",
    ),
    MarshalAura(
        "Over the Top",
        MINOR,
        TARGET_NONE,
        description="Bonus on damage rolls made when charging.",
    ),
    MarshalAura(
        "Watchful Eye",
        MINOR,
        TARGET_REF,
        description="Bonus on Reflex saves.",
    ),
    # --- Major auras (bonus = half marshal level, minimum +1) --------------
    MarshalAura(
        "Hardy Soldiers",
        MAJOR,
        TARGET_NONE,
        description="Grants damage reduction against weapon attacks.",
    ),
    MarshalAura(
        "Motivate Ardor",
        MAJOR,
        TARGET_NONE,
        description="Bonus on damage rolls.",
    ),
    MarshalAura(
        "Motivate Attack",
        MAJOR,
        TARGET_MELEE,
        description="Bonus on melee attack rolls.",
    ),
    MarshalAura(
        "Motivate Care",
        MAJOR,
        TARGET_AC,
        description="Bonus to Armor Class.",
    ),
    MarshalAura(
        "Motivate Urgency",
        MAJOR,
        TARGET_NONE,
        description="Increases base land speed.",
    ),
    MarshalAura(
        "Resilient Troops",
        MAJOR,
        TARGET_SAVES,
        description="Bonus on all saving throws.",
    ),
    MarshalAura(
        "Steady Hand",
        MAJOR,
        TARGET_RANGED,
        description="Bonus on ranged attack rolls.",
    ),
    # --- Draconic auras (Dragon Magic) -------------------------------------
    MarshalAura(
        "Energy (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on damage rolls with energy attacks.",
    ),
    MarshalAura(
        "Insight (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on Knowledge checks.",
    ),
    MarshalAura(
        "Power (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on Strength checks and Strength-based skill checks.",
    ),
    MarshalAura(
        "Presence (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on Charisma-based skill checks.",
    ),
    MarshalAura(
        "Resistance (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on saving throws against a chosen energy type.",
    ),
    MarshalAura(
        "Resolve (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on saving throws against fear and mind-affecting "
        "effects.",
    ),
    MarshalAura(
        "Senses (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on Listen and Spot checks.",
    ),
    MarshalAura(
        "Stamina (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Bonus on Fortitude saves against fatigue, exhaustion, "
        "and similar effects.",
    ),
    MarshalAura(
        "Swiftness (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Increases base land speed.",
    ),
    MarshalAura(
        "Toughness (Draconic)",
        MAJOR,
        TARGET_NONE,
        description="Grants temporary hit points.",
    ),
)


#: Fast name → :class:`MarshalAura` lookup over :data:`STANDARD_MARSHAL_AURAS`.
_BY_NAME: dict[str, MarshalAura] = {a.name: a for a in STANDARD_MARSHAL_AURAS}


def get_aura(name: str) -> MarshalAura | None:
    """Return the catalogued :class:`MarshalAura` for *name*, or ``None``."""
    return _BY_NAME.get(name)


def minor_aura_value(charisma_modifier: int) -> int:
    """Return a minor aura's bonus for the given Charisma modifier.

    A minor aura grants a bonus equal to the marshal's Charisma bonus; a
    non-positive Charisma modifier confers no benefit (*Miniatures Handbook*
    p11).
    """
    return max(0, charisma_modifier)


def major_aura_value(marshal_level: int) -> int:
    """Return a major aura's bonus for the given marshal class level.

    A major aura grants a bonus equal to one-half the marshal's marshal level,
    rounded down, with a minimum of +1 (*Miniatures Handbook* p12).
    """
    return max(1, marshal_level // 2)


def aura_value(aura: MarshalAura, charisma_modifier: int, marshal_level: int) -> int:
    """Return the numeric bonus *aura* grants for the supplied character values."""
    if aura.aura_type == MINOR:
        return minor_aura_value(charisma_modifier)
    return major_aura_value(marshal_level)


@dataclass(frozen=True)
class AuraBonuses:
    """The derived-stat bonuses contributed by a character's active auras.

    Attributes:
        save_bonuses:   Saving-throw bonuses keyed by the short save keys
                        ``"fort"``, ``"ref"``, ``"will"`` (the same keys the
                        derived-stats pipeline expects).
        ac_bonuses:     ``(bonus_type, value)`` Armor Class sources.
        attack_bonuses: Attack-roll bonuses keyed ``"melee"`` and ``"ranged"``.
    """

    save_bonuses: Mapping[str, int] = field(default_factory=dict)
    ac_bonuses: tuple[tuple[str, int], ...] = ()
    attack_bonuses: Mapping[str, int] = field(default_factory=dict)


def apply_aura_bonuses(
    active_auras: Iterable[str],
    charisma_modifier: int,
    marshal_level: int,
    *,
    catalog: Iterable[MarshalAura] = STANDARD_MARSHAL_AURAS,
) -> AuraBonuses:
    """Compute the derived-stat bonuses from a character's active auras.

    Args:
        active_auras:      Names of the auras the character is currently
                           projecting (its *active* selections).
        charisma_modifier: The marshal's Charisma modifier, sizing minor auras.
        marshal_level:     The marshal's marshal class level, sizing major auras.
        catalog:           The aura catalogue to resolve names against.

    Returns:
        An :class:`AuraBonuses` aggregating every active aura whose effect the
        derived-stats pipeline models.  Auras that are unknown or whose effect is
        not modelled (:data:`TARGET_NONE`) contribute nothing.

    Reference: *Miniatures Handbook* p11–12.
    """
    by_name = {a.name: a for a in catalog}
    saves: dict[str, int] = {}
    ac: list[tuple[str, int]] = []
    attacks: dict[str, int] = {}

    for name in active_auras:
        aura = by_name.get(name)
        if aura is None or not aura.affects_derived_stats:
            continue
        value = aura_value(aura, charisma_modifier, marshal_level)
        if value == 0:
            continue
        target = aura.target
        if target == TARGET_SAVES:
            for key in (TARGET_FORT, TARGET_REF, TARGET_WILL):
                saves[key] = saves.get(key, 0) + value
        elif target in (TARGET_FORT, TARGET_REF, TARGET_WILL):
            saves[target] = saves.get(target, 0) + value
        elif target == TARGET_AC:
            ac.append((aura.bonus_type, value))
        elif target in (TARGET_MELEE, TARGET_RANGED):
            attacks[target] = attacks.get(target, 0) + value

    return AuraBonuses(
        save_bonuses=saves,
        ac_bonuses=tuple(ac),
        attack_bonuses=attacks,
    )
