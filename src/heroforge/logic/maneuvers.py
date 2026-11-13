"""Martial maneuver/stance mechanics for HeroForge-Anew (Excel tab 8b).

Reference: *Tome of Battle: The Book of Nine Swords* (ToB).

A character's selected maneuvers and stances are persisted on
:attr:`heroforge.models.character.Character.maneuvers` as ``{"maneuver_name",
"readied"}`` entries.  For a stance the ``readied`` flag marks the stance as
*active*; for a (momentary) maneuver it marks the maneuver as *readied*.

The reference workbook (``HeroForge Anew 3.5 v7.4.0.1.xlsm``) only *tracked* the
chosen maneuvers/stances on its *Maneuvers & Stances* sheet — it did not store a
structured table of each stance's mechanical effect, and it never baked stance
bonuses into the character's computed totals.  Mirroring the approach used for
standard familiars (:mod:`heroforge.logic.familiar` and its
``STANDARD_FAMILIAR_BONUSES``), this module is the single structured source of
truth for the *persistent* numeric bonuses a stance grants, so the derived-stats
pipeline can apply them.

Only **unconditional** effects (those active for as long as the stance is held)
feed a computed total.  Stances whose bonus applies only in a specific
circumstance — e.g. *Stonefoot Stance*'s +2 AC that only counts against larger
creatures — carry a non-empty :attr:`StanceEffect.condition` and are therefore
never folded into a derived stat, exactly as the situational Hawk/Owl familiar
bonuses are excluded in :mod:`heroforge.logic.familiar`.

Every effect carries a PHB bonus type, and
:func:`heroforge.logic.derived_stats.compute_derived_stats` stacks the
unconditional ones (see :func:`stance_bonus_specs`) together with active buffs
and equipped magic items (PHB p176), so a stance never adds to a same-type
bonus from another source.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from heroforge.logic import buffs

# Effect categories.  ``ac`` targets Armor Class; ``save`` targets a saving
# throw (``target`` is the save name).
KIND_AC = "ac"
KIND_SAVE = "save"

# Map a saving-throw ``target`` to the short key used by the saving-throw logic
# and the derived-stats pipeline.
_SAVE_KEYS: dict[str, str] = {
    "Fortitude": "fort",
    "Reflex": "ref",
    "Will": "will",
}


@dataclass(frozen=True)
class StanceEffect:
    """A single persistent mechanical effect granted by a stance.

    Attributes:
        stance_name: The stance's name (e.g. ``"Punishing Stance"``).
        value:       Signed size of the effect (e.g. ``-2`` for a penalty).
        kind:        One of :data:`KIND_AC`, :data:`KIND_SAVE`.
        target:      The affected stat: ``"AC"`` for :data:`KIND_AC`, or the
                     saving-throw name (``"Fortitude"``/``"Reflex"``/
                     ``"Will"``) for :data:`KIND_SAVE`.
        condition:   A situational qualifier (e.g. ``"against larger
                     creatures"``).  When non-empty the effect is conditional
                     and is *not* applied mechanically.
        bonus_type:  The PHB p176 bonus type (``"untyped"``, ``"dodge"``,
                     ``"morale"``, …) used to stack the effect with buffs and
                     magic items.
    """

    stance_name: str
    value: int
    kind: str
    target: str = ""
    condition: str = ""
    bonus_type: str = "untyped"

    @property
    def conditional(self) -> bool:
        """Whether the effect only applies under a specific circumstance."""
        return bool(self.condition)


# The canonical Tome of Battle stance effects that touch a tracked derived stat
# (Armor Class or a saving throw).  Conditional entries record the qualifier in
# ``condition`` so they are catalogued but never folded into a total.
STANCE_EFFECTS: tuple[StanceEffect, ...] = (
    # Iron Heart — Punishing Stance (ToB p70): "Attacks deal +1d6 damage, but
    # you have -2 to AC" (workbook Maneuvers & Stances row 88).  The extra 1d6
    # damage is not a tracked derived stat; the −2 AC is always on while the
    # stance is held.  The stance carries no saving-throw penalty.
    StanceEffect("Punishing Stance", -2, KIND_AC, "AC"),
    # Stone Dragon — Stonefoot Stance (ToB p67): +2 AC, but only against
    # creatures larger than you.
    StanceEffect("Stonefoot Stance", 2, KIND_AC, "AC", "against larger creatures"),
    # Stone Dragon — Roots of the Mountain is deliberately absent: its effects
    # ("+10 bonus on checks against bull rush, trip, and others, and gain DR
    # 2/-", workbook row 167) touch neither AC nor a saving throw.
    # Diamond Mind — Stance of Clarity (ToB p62): "Gain +2 AC against one fo[e],
    # -2 against all others" (workbook row 66).  ToB types the bonus as insight.
    StanceEffect(
        "Stance of Clarity",
        2,
        KIND_AC,
        "AC",
        "against one chosen opponent",
        bonus_type="insight",
    ),
    StanceEffect("Stance of Clarity", -2, KIND_AC, "AC", "against all other opponents"),
    # Iron Heart — Absolute Steel Stance (ToB p69): +2 dodge AC, but only while
    # you move at least 10 feet in a round.
    StanceEffect(
        "Absolute Steel Stance",
        2,
        KIND_AC,
        "AC",
        "while moving 10 ft. or more",
        bonus_type="dodge",
    ),
    # White Raven — Bolstering Voice (ToB p84): "Allies gain +2 bonus on Will
    # saves, +4 against fear" (workbook row 211).  It benefits allies, not the
    # initiator, so it is catalogued as conditional and never applied here.
    StanceEffect(
        "Bolstering Voice",
        2,
        KIND_SAVE,
        "Will",
        "for allies only (+4 against fear)",
        bonus_type="morale",
    ),
)


def _catalogue(effects: Iterable[StanceEffect] | None) -> Iterable[StanceEffect]:
    """Return *effects*, or the current :data:`STANCE_EFFECTS` when ``None``."""
    return STANCE_EFFECTS if effects is None else effects


def describe_effect(effect: StanceEffect) -> str:
    """Compose human-readable helper text for *effect*.

    The wording is derived entirely from the structured fields so it always
    reflects the actual numbers and target.

    Args:
        effect: The structured stance effect.

    Returns:
        A sentence such as ``"-2 penalty to AC."`` or
        ``"+2 bonus on Will saves for allies only (+4 against fear)."``.
    """
    sign = "+" if effect.value >= 0 else ""
    word = "bonus" if effect.value >= 0 else "penalty"
    if effect.kind == KIND_SAVE:
        text = f"{sign}{effect.value} {word} on {effect.target} saves"
    else:
        text = f"{sign}{effect.value} {word} to AC"
    if effect.condition:
        text += f" {effect.condition}"
    return text + "."


def active_stance_names(
    maneuvers: Iterable[Mapping[str, object]],
) -> list[str]:
    """Return the names of every stance/maneuver marked active (readied).

    Args:
        maneuvers: The character's ``maneuvers`` collection (each a mapping with
            at least ``maneuver_name`` and ``readied`` keys).

    Returns:
        The readied entries' names, in their stored order (duplicates removed).
    """
    names: list[str] = []
    seen: set[str] = set()
    for entry in maneuvers:
        if not entry.get("readied"):
            continue
        name = str(entry.get("maneuver_name", "")).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def active_stance_effects(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] | None = None,
) -> list[StanceEffect]:
    """Return the catalogued effects of every active stance in *maneuvers*.

    Only stances that are both marked active (``readied``) and present in the
    *effects* catalogue contribute; momentary maneuvers (which grant no
    persistent derived-stat bonus) are therefore ignored.

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search (defaults to
            :data:`STANCE_EFFECTS`).

    Returns:
        The matching :class:`StanceEffect` records (both conditional and
        unconditional).
    """
    active = set(active_stance_names(maneuvers))
    return [effect for effect in _catalogue(effects) if effect.stance_name in active]


def stance_bonus_specs(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] | None = None,
) -> list[dict[str, object]]:
    """Return the active stances' unconditional effects as typed bonus specs.

    Each spec is a ``{"source", "target", "bonus_type", "value"}`` dict in the
    same shape as an equipped magic item's bonus specs
    (:func:`heroforge.logic.equipment.item_bonus_specs`), so
    :func:`heroforge.logic.derived_stats.compute_derived_stats` can stack them
    with active buffs and items by bonus type (PHB p176).  Conditional effects
    are skipped.

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search (defaults to
            :data:`STANCE_EFFECTS`).

    Returns:
        One spec per unconditional effect of every active stance.
    """
    return [
        {
            "source": effect.stance_name,
            "target": effect.target,
            "bonus_type": effect.bonus_type or "untyped",
            "value": effect.value,
        }
        for effect in active_stance_effects(maneuvers, effects)
        if not effect.conditional and effect.kind in (KIND_AC, KIND_SAVE)
    ]


def stance_save_bonuses(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] | None = None,
) -> dict[str, int]:
    """Return the net unconditional saving-throw bonuses from active stances.

    Conditional effects (those with a non-empty ``condition``) are skipped so
    situational bonuses never feed a computed total.  The result is keyed by the
    short save keys (``"fort"``, ``"ref"``, ``"will"``) used by
    :mod:`heroforge.logic.saving_throws` and the derived-stats pipeline.

    This reports the stances on their own; the derived-stats pipeline stacks
    them together with buffs and items instead (see :func:`stance_bonus_specs`).

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search (defaults to
            :data:`STANCE_EFFECTS`).

    Returns:
        Mapping of save key → net bonus (empty when nothing applies).  Several
        active stances' effects on one save combine under the PHB p176 stacking
        rules: same-type bonuses overlap, while penalties and untyped, dodge,
        circumstance and racial bonuses add up.
    """
    records: list[tuple[str, str, str, int]] = []
    for effect in active_stance_effects(maneuvers, effects):
        if effect.kind != KIND_SAVE or effect.conditional:
            continue
        key = _SAVE_KEYS.get(effect.target)
        if key is not None:
            records.append(
                (effect.stance_name, effect.bonus_type, key, int(effect.value))
            )
    return {k: v for k, v in buffs.aggregate_bonuses(records).items() if v}


def stance_ac_bonuses(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] | None = None,
) -> list[tuple[str, int]]:
    """Return the unconditional AC effects from active stances.

    Conditional effects are skipped.  The result is a list of
    ``(bonus_type, value)`` tuples suitable for
    :func:`heroforge.logic.combat.aggregate_armor_class`.

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search (defaults to
            :data:`STANCE_EFFECTS`).

    Returns:
        ``(bonus_type, value)`` tuples (empty when nothing applies).
    """
    return [
        (effect.bonus_type or "untyped", effect.value)
        for effect in active_stance_effects(maneuvers, effects)
        if effect.kind == KIND_AC and not effect.conditional
    ]
