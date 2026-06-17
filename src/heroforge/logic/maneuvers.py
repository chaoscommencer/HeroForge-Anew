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
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Effect categories.  ``ac`` targets Armor Class (``target`` is the AC bonus
# type used by :func:`heroforge.logic.combat.aggregate_ac_bonuses`); ``save``
# targets a saving throw (``target`` is the save name).
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
        target:      For :data:`KIND_SAVE` the saving-throw name
                     (``"Fortitude"``/``"Reflex"``/``"Will"``); for
                     :data:`KIND_AC` the AC bonus type (``"dodge"``,
                     ``"untyped"``, …).
        condition:   A situational qualifier (e.g. ``"against larger
                     creatures"``).  When non-empty the effect is conditional
                     and is *not* applied mechanically.
    """

    stance_name: str
    value: int
    kind: str
    target: str = ""
    condition: str = ""

    @property
    def conditional(self) -> bool:
        """Whether the effect only applies under a specific circumstance."""
        return bool(self.condition)


# The canonical Tome of Battle stance effects that touch a tracked derived stat
# (Armor Class or a saving throw).  Conditional entries record the qualifier in
# ``condition`` so they are catalogued but never folded into a total.
STANCE_EFFECTS: tuple[StanceEffect, ...] = (
    # Iron Heart — Punishing Stance (ToB p70): trade defence for offence.  The
    # extra 1d6 damage is not a tracked derived stat, but the −2 AC and −2 on
    # Reflex saves are always-on while the stance is held.
    StanceEffect("Punishing Stance", -2, KIND_AC, "untyped"),
    StanceEffect("Punishing Stance", -2, KIND_SAVE, "Reflex"),
    # Stone Dragon — Stonefoot Stance (ToB p67): +2 AC, but only against
    # creatures larger than you.
    StanceEffect("Stonefoot Stance", 2, KIND_AC, "untyped", "against larger creatures"),
    # Stone Dragon — Roots of the Mountain (ToB p66): +2 AC and +2 on saves, but
    # only to resist bull rush, trip, grapple and overrun attempts.
    StanceEffect(
        "Roots of the Mountain",
        2,
        KIND_AC,
        "untyped",
        "against bull rush, trip, grapple and overrun",
    ),
    # Diamond Mind — Stance of Clarity (ToB p62): +2 dodge AC, but only against a
    # single chosen opponent.
    StanceEffect(
        "Stance of Clarity", 2, KIND_AC, "dodge", "against one chosen opponent"
    ),
    # Iron Heart — Absolute Steel Stance (ToB p69): +2 dodge AC, but only while
    # you move at least 10 feet in a round.
    StanceEffect(
        "Absolute Steel Stance", 2, KIND_AC, "dodge", "while moving 10 ft. or more"
    ),
    # White Raven — Bolstering Voice (ToB p84): +2 morale bonus on saves, but
    # only against fear and charm effects.
    StanceEffect(
        "Bolstering Voice", 2, KIND_SAVE, "Will", "against fear and charm effects"
    ),
)


def describe_effect(effect: StanceEffect) -> str:
    """Compose human-readable helper text for *effect*.

    The wording is derived entirely from the structured fields so it always
    reflects the actual numbers and target.

    Args:
        effect: The structured stance effect.

    Returns:
        A sentence such as ``"-2 penalty to AC."`` or
        ``"+2 bonus on Will saves against fear and charm effects."``.
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
    effects: Iterable[StanceEffect] = STANCE_EFFECTS,
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
    return [effect for effect in effects if effect.stance_name in active]


def stance_save_bonuses(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] = STANCE_EFFECTS,
) -> dict[str, int]:
    """Return the unconditional saving-throw bonuses from active stances.

    Conditional effects (those with a non-empty ``condition``) are skipped so
    situational bonuses never feed a computed total.  The result is keyed by the
    short save keys (``"fort"``, ``"ref"``, ``"will"``) used by
    :mod:`heroforge.logic.saving_throws` and the derived-stats pipeline.

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search.

    Returns:
        Mapping of save key → net bonus (empty when nothing applies).  Values
        accumulate additively when several active stances share a save target.
    """
    result: dict[str, int] = {}
    for effect in active_stance_effects(maneuvers, effects):
        if effect.kind != KIND_SAVE or effect.conditional:
            continue
        key = _SAVE_KEYS.get(effect.target)
        if key is not None:
            result[key] = result.get(key, 0) + effect.value
    return result


def stance_ac_bonuses(
    maneuvers: Iterable[Mapping[str, object]],
    effects: Iterable[StanceEffect] = STANCE_EFFECTS,
) -> list[tuple[str, int]]:
    """Return the unconditional AC effects from active stances.

    Conditional effects are skipped.  The result is a list of
    ``(bonus_type, value)`` tuples suitable for
    :func:`heroforge.logic.combat.aggregate_armor_class` (and hence the
    ``ac_bonuses`` argument of
    :func:`heroforge.logic.derived_stats.compute_derived_stats`).

    Args:
        maneuvers: The character's ``maneuvers`` collection.
        effects:   Structured stance-effect records to search.

    Returns:
        ``(bonus_type, value)`` tuples (empty when nothing applies).
    """
    result: list[tuple[str, int]] = []
    for effect in active_stance_effects(maneuvers, effects):
        if effect.kind != KIND_AC or effect.conditional:
            continue
        result.append((effect.target or "untyped", effect.value))
    return result
