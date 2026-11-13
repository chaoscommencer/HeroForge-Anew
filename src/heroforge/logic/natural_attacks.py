"""Natural attacks (claws, bites, slams …) of creature forms.

Reference: MM p312 (natural attacks; primary and secondary attacks), MM p304
(Multiattack), DMG p28 Table 2-2 and MM p296 (damage by size).

The seeded ``CreatureInfo.csv`` "Natural Attacks" column encodes each attack
the way the workbook parses it in ``'Class Weapons & Armor'!AQ8:BK20``::

    [count ]Name+RR+OO+SS[,…]

* ``count`` – number of such attacks (``"2 Claws"``), 1 when omitted;
* ``RR``    – row of the damage-by-size table (``TblWeaponDamage``,
  :data:`DAMAGE_BY_SIZE`);
* ``OO``    – size-column offset applied to the creature's size (an Earth
  elemental's slam uses the column one size smaller);
* ``SS``    – Strength-to-damage code indexing ``TblStrengthBonusToDamage``
  after adding 2: ``-1`` none, ``0`` half (a secondary attack), ``1`` full,
  ``2`` one and a half (a sole attack), ``3`` double.

Everything here is data plus pure functions, so the derived-stats pipeline can
turn a form's attacks into display lines without any Qt dependency.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from heroforge.logic.combat import format_attack_line, weapon_damage

#: Size categories in the column order of :data:`DAMAGE_BY_SIZE`.
SIZES: tuple[str, ...] = (
    "Fine",
    "Diminutive",
    "Tiny",
    "Small",
    "Medium",
    "Large",
    "Huge",
    "Gargantuan",
    "Colossal",
)

#: Natural weapon damage by size (workbook ``TblWeaponDamage``,
#: ``'Class Weapons & Armor'!K4:S19``).  Row *n* of the encoded attack is
#: ``DAMAGE_BY_SIZE[n - 1]``; ``""`` means no damage at that size.
DAMAGE_BY_SIZE: tuple[tuple[str, ...], ...] = (
    ("", "", "", "", "1", "1d2", "1d3", "1d4", "1d6"),
    ("", "", "", "1", "1d2", "1d3", "1d4", "1d6", "1d8"),
    ("", "", "1", "1d2", "1d3", "1d4", "1d6", "1d8", "2d6"),
    ("", "1", "1d2", "1d3", "1d4", "1d6", "1d8", "2d6", "3d6"),
    ("1", "1d2", "1d3", "1d4", "1d6", "1d8", "2d6", "3d6", "4d6"),
    ("1d2", "1d3", "1d4", "1d6", "1d8", "2d6", "3d6", "4d6", "6d6"),
    ("1d3", "1d4", "1d6", "1d8", "1d10", "2d8", "3d8", "4d8", "6d8"),
    ("1d4", "1d6", "1d8", "1d10", "1d12", "3d6", "4d6", "6d6", "8d6"),
    ("1d2", "1d3", "1d4", "1d6", "2d4", "2d6", "3d6", "4d6", "6d6"),
    ("1d4", "1d6", "1d8", "1d10", "2d6", "3d6", "4d6", "6d6", "8d6"),
    ("1d6", "1d8", "1d10", "2d6", "2d8", "3d8", "4d8", "6d8", "8d8"),
    ("1d8", "1d10", "2d6", "2d8", "2d10", "4d8", "6d8", "8d8", "12d8"),
    ("1d2", "1d3", "1d4", "1d6", "1d8", "1d10", "1d12", "3d6", "4d6"),
    ("1d2", "1d3", "1d4", "1d6", "1d8", "2d6", "2d8", "3d8", "4d8"),
    ("1", "1d2", "1d3", "1d4", "1d6", "2d4", "2d6", "3d6", "4d6"),
    ("1d6", "1d8", "1d10", "2d6", "2d8", "2d10", "2d12", "6d6", "8d6"),
)

#: Strength-to-damage codes (workbook ``Tables!B2:B6`` minus 2).
STRENGTH_NONE = -1
STRENGTH_HALF = 0
STRENGTH_FULL = 1
STRENGTH_ONE_AND_HALF = 2
STRENGTH_DOUBLE = 3

#: Attack penalty of a secondary natural attack, and with Multiattack (MM p304).
SECONDARY_PENALTY = -5
MULTIATTACK_SECONDARY_PENALTY = -2

_ENTRY_RE = re.compile(
    r"^\s*(?:(?P<count>\d+)\s+)?(?P<name>[^+\-;]*?)\s*"
    r"(?P<row>[+-]\d+)(?P<offset>[+-]\d+)(?P<strength>[+-]\d+)\s*$"
)
_NAME_RE = re.compile(r"^\s*(?:(?P<count>\d+)\s+)?(?P<name>[^+;]*)")


@dataclass(frozen=True)
class NaturalAttack:
    """One encoded natural attack of a creature (e.g. ``2 Claws+15+0+1``).

    ``damage_row`` is ``None`` when the source text carries no damage code
    (some catalogue rows only name the attack, e.g. ``"Bite;"``).
    """

    name: str
    count: int = 1
    damage_row: int | None = None
    size_offset: int = 0
    strength: int = STRENGTH_FULL

    @property
    def secondary(self) -> bool:
        """``True`` for a secondary attack (half Strength to damage, MM p312)."""
        return self.strength == STRENGTH_HALF


@dataclass(frozen=True)
class NaturalAttackLine:
    """A natural attack resolved for display: bonus and damage computed."""

    name: str
    count: int
    attack_bonus: int
    damage: str
    secondary: bool

    @property
    def label(self) -> str:
        """``"2 Claws"`` style label."""
        return f"{self.count} {self.name}" if self.count > 1 else self.name

    @property
    def attack_text(self) -> str:
        """Signed attack bonus, e.g. ``"+7"``."""
        return format_attack_line([self.attack_bonus])


def parse_natural_attacks(text: str) -> list[NaturalAttack]:
    """Parse a catalogue "Natural Attacks" value into :class:`NaturalAttack`.

    Entries that carry no damage code keep their name with no damage; empty
    entries and entries without a name are dropped.
    """
    attacks: list[NaturalAttack] = []
    for raw in re.split(r"[,;]", text or ""):
        if not raw.strip():
            continue
        match = _ENTRY_RE.match(raw)
        if match and match.group("name").strip():
            attacks.append(
                NaturalAttack(
                    name=match.group("name").strip(),
                    count=int(match.group("count") or 1),
                    damage_row=int(match.group("row")),
                    size_offset=int(match.group("offset")),
                    strength=int(match.group("strength")),
                )
            )
            continue
        loose = _NAME_RE.match(raw)
        name = loose.group("name").strip() if loose else ""
        if name:
            count = int(loose.group("count") or 1) if loose else 1
            attacks.append(NaturalAttack(name=name, count=count))
    return attacks


def natural_attack_dice(attack: NaturalAttack, size: str) -> str:
    """Return *attack*'s damage dice for a creature of *size* (``""`` if none)."""
    if attack.damage_row is None or not 1 <= attack.damage_row <= len(
        DAMAGE_BY_SIZE
    ):
        return ""
    try:
        column = SIZES.index(size) + attack.size_offset
    except ValueError:
        column = SIZES.index("Medium") + attack.size_offset
    column = min(max(column, 0), len(SIZES) - 1)
    return DAMAGE_BY_SIZE[attack.damage_row - 1][column]


def strength_damage(str_mod: int, strength: int) -> int:
    """Return the Strength damage for a natural attack's strength code.

    Follows the workbook's ``TblStrengthBonusToDamage``: half and one and a
    half apply only to a bonus (a penalty applies in full), double doubles
    either (PHB p134, MM p312).
    """
    if strength == STRENGTH_NONE:
        return 0
    if strength == STRENGTH_HALF:
        return str_mod // 2 if str_mod > 0 else str_mod
    if strength == STRENGTH_ONE_AND_HALF:
        return str_mod + str_mod // 2 if str_mod > 0 else str_mod
    if strength == STRENGTH_DOUBLE:
        return 2 * str_mod
    return str_mod


def natural_attack_lines(
    attacks: Sequence[NaturalAttack],
    *,
    size: str,
    melee_attack: int,
    str_mod: int,
    feats: Iterable[str] = (),
) -> list[NaturalAttackLine]:
    """Resolve *attacks* into display lines for a creature of *size*.

    A primary attack uses the full melee attack bonus (BAB, Strength, size and
    typed melee bonuses); a secondary attack takes -5, or -2 with the
    Multiattack feat (MM p304, p312).  Damage is the size-adjusted dice plus
    the coded share of Strength.

    Args:
        attacks:      Parsed attacks of the form.
        size:         The form's size category.
        melee_attack: The derived melee attack bonus in the form.
        str_mod:      The Strength modifier in the form.
        feats:        The character's feats (for Multiattack).
    """
    multiattack = any(str(f).strip().lower() == "multiattack" for f in feats)
    penalty = MULTIATTACK_SECONDARY_PENALTY if multiattack else SECONDARY_PENALTY
    lines: list[NaturalAttackLine] = []
    for attack in attacks:
        dice = natural_attack_dice(attack, size)
        damage = ""
        if dice:
            bonus = strength_damage(str_mod, attack.strength)
            # A flat "1" has no NdM dice for weapon_damage to recombine.
            damage = (
                weapon_damage(dice, bonus)
                if "d" in dice
                else str(max(1, int(dice) + bonus))
            )
        lines.append(
            NaturalAttackLine(
                name=attack.name,
                count=attack.count,
                attack_bonus=melee_attack + (penalty if attack.secondary else 0),
                damage=damage,
                secondary=attack.secondary,
            )
        )
    return lines


def format_natural_attacks(attacks: Sequence[NaturalAttack]) -> str:
    """Return a short ``"2 Claws, Bite"`` summary of *attacks*."""
    return ", ".join(f"{a.count} {a.name}" if a.count > 1 else a.name for a in attacks)
