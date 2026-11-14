"""Spell calculations for HeroForge-Anew.

Reference: PHB Chapter 10 (magic), p178–183.
"""

from __future__ import annotations


def caster_level(
    class_levels: dict[str, int],
    class_caster_types: dict[str, str],
) -> int:
    """Calculate effective caster level for spellcasting purposes.

    Caster type multipliers (approximate):
    - ``'full'``: level × 1
    - ``'three_quarter'``: level × 3 // 4
    - ``'half'``: level // 2

    Reference: PHB p180 (various class descriptions).

    Args:
        class_levels:       Mapping of class name → levels taken.
        class_caster_types: Mapping of class name → caster type string.

    Returns:
        Total effective caster level.
    """
    total = 0
    for cls, lvl in class_levels.items():
        ctype = class_caster_types.get(cls, "none").lower()
        if ctype in ("full", "full_caster"):
            total += lvl
        elif ctype in ("three_quarter", "3/4", "three-quarter"):
            total += lvl * 3 // 4
        elif ctype in ("half", "1/2"):
            total += lvl // 2
        # "none" and unknown types contribute 0
    return total


def spells_per_day(base_slots: list[int], ability_mod: int) -> list[int]:
    """Adjust base spell slots by high-ability bonus slots.

    For each spell level N (0-indexed), a caster with a high key ability score
    gains additional spell slots according to the bonus spell table (PHB p8):

    - Modifier 1 → +1 to spell level 1
    - Modifier 2 → +1 to spell levels 1–2
    - …and so on (one extra slot per spell level up to modifier).

    Reference: PHB p8 (Ability Modifiers and Bonus Spells table).

    Args:
        base_slots:  List of base spell slots indexed by spell level (0 = cantrips).
        ability_mod: Relevant ability modifier (INT for Wizard, WIS for Cleric, etc.).

    Returns:
        New list of spell slots with bonus spells added.
    """
    result = list(base_slots)
    if ability_mod <= 0:
        return result

    # Bonus spells are granted for spell levels 1 through ability_mod
    for spell_level in range(1, ability_mod + 1):
        if spell_level < len(result):
            result[spell_level] += 1

    return result


def arcane_spell_failure(armor_pieces: list[int]) -> int:
    """Calculate total arcane spell failure chance.

    The total ASF is the sum of all worn armour/shield ASF percentages.

    Reference: PHB p123 (Arcane Spell Failure column of armor table).

    Args:
        armor_pieces: List of ASF percentages (integers, e.g. 5, 15, 25).

    Returns:
        Total arcane spell failure percentage.
    """
    return sum(armor_pieces)


def spell_save_dc(spell_level: int, ability_mod: int, misc: int = 0) -> int:
    """Calculate the saving throw DC for a spell.

    Reference: PHB p152.

    DC = 10 + spell_level + ability_modifier + misc

    Args:
        spell_level: Level of the spell (0–9).
        ability_mod: Spellcasting ability modifier (INT/WIS/CHA).
        misc:        Miscellaneous bonuses (Spell Focus feat, etc.).

    Returns:
        Spell save DC.
    """
    return 10 + spell_level + ability_mod + misc
