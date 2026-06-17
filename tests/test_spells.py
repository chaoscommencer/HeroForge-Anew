"""Tests for heroforge.logic.spells.

Reference: PHB Chapter 10.
"""

from __future__ import annotations

from heroforge.logic.spells import (
    CASTER_TYPES,
    SPELLCASTING_ABILITIES,
    arcane_spell_failure,
    caster_level,
    spell_save_dc,
    spells_per_day,
)


class TestCasterLevel:
    def test_full_caster(self) -> None:
        assert caster_level({"Wizard": 10}, {"Wizard": "full"}) == 10

    def test_three_quarter_caster(self) -> None:
        # Bard 4 → 4*3//4 = 3
        assert caster_level({"Bard": 4}, {"Bard": "three_quarter"}) == 3

    def test_half_caster(self) -> None:
        # Paladin 6 → 6//2 = 3
        assert caster_level({"Paladin": 6}, {"Paladin": "half"}) == 3

    def test_non_caster(self) -> None:
        assert caster_level({"Fighter": 10}, {"Fighter": "none"}) == 0

    def test_multiclass(self) -> None:
        # Wizard 5 (full=5) + Paladin 4 (half=2) = 7
        result = caster_level(
            {"Wizard": 5, "Paladin": 4},
            {"Wizard": "full", "Paladin": "half"},
        )
        assert result == 7

    def test_empty(self) -> None:
        assert caster_level({}, {}) == 0


class TestSpellsPerDay:
    def test_no_bonus_ability(self) -> None:
        base = [4, 2, 1, 0]
        assert spells_per_day(base, 0) == [4, 2, 1, 0]

    def test_ability_mod_1(self) -> None:
        # +1 mod → +1 slot to spell level 1
        base = [4, 2, 1]
        result = spells_per_day(base, 1)
        assert result == [4, 3, 1]

    def test_ability_mod_3(self) -> None:
        # +3 mod → +1 to levels 1, 2, 3
        base = [4, 3, 2, 1, 0]
        result = spells_per_day(base, 3)
        assert result == [4, 4, 3, 2, 0]

    def test_negative_ability_no_change(self) -> None:
        base = [4, 2, 1]
        assert spells_per_day(base, -1) == [4, 2, 1]

    def test_mod_exceeds_known_levels(self) -> None:
        # Ability mod 5 but only 3 spell levels → no out-of-range error
        base = [4, 2, 1]
        result = spells_per_day(base, 5)
        assert result == [4, 3, 2]


class TestArcaneSpellFailure:
    def test_no_armor(self) -> None:
        assert arcane_spell_failure([]) == 0

    def test_single_armor(self) -> None:
        assert arcane_spell_failure([25]) == 25

    def test_armor_and_shield(self) -> None:
        # Mithral full plate 15% + heavy shield 15%
        assert arcane_spell_failure([15, 15]) == 30

    def test_multiple_pieces(self) -> None:
        assert arcane_spell_failure([10, 5, 5]) == 20


class TestSpellSaveDC:
    def test_cantrip(self) -> None:
        # DC = 10 + 0 + 3 = 13
        assert spell_save_dc(0, 3) == 13

    def test_level_5_spell(self) -> None:
        # Fireball (level 3 for Wizard) with INT +4: 10+3+4=17
        assert spell_save_dc(3, 4) == 17

    def test_with_spell_focus(self) -> None:
        # +1 from Spell Focus feat
        assert spell_save_dc(3, 4, misc=1) == 18

    def test_level_9_spell_high_ability(self) -> None:
        assert spell_save_dc(9, 5) == 24

    def test_zero_everything(self) -> None:
        assert spell_save_dc(0, 0) == 10


class TestSpellcastingAbilities:
    """Reference: PHB Chapter 3 (class descriptions) and PHB p. 8."""

    def test_core_full_casters_present(self) -> None:
        for cls in ("Wizard", "Sorcerer", "Cleric", "Druid"):
            assert cls in SPELLCASTING_ABILITIES, f"{cls} missing"

    def test_partial_casters_present(self) -> None:
        for cls in ("Bard", "Paladin", "Ranger"):
            assert cls in SPELLCASTING_ABILITIES, f"{cls} missing"

    def test_wizard_uses_int(self) -> None:
        assert SPELLCASTING_ABILITIES["Wizard"] == "INT"

    def test_cleric_uses_wis(self) -> None:
        assert SPELLCASTING_ABILITIES["Cleric"] == "WIS"

    def test_sorcerer_uses_cha(self) -> None:
        assert SPELLCASTING_ABILITIES["Sorcerer"] == "CHA"

    def test_bard_uses_cha(self) -> None:
        assert SPELLCASTING_ABILITIES["Bard"] == "CHA"

    def test_paladin_uses_wis(self) -> None:
        assert SPELLCASTING_ABILITIES["Paladin"] == "WIS"


class TestCasterTypes:
    """Reference: PHB Chapter 3 (class descriptions)."""

    def test_core_casters_present(self) -> None:
        for cls in (
            "Wizard",
            "Sorcerer",
            "Cleric",
            "Druid",
            "Bard",
            "Paladin",
            "Ranger",
        ):
            assert cls in CASTER_TYPES, f"{cls} missing"

    def test_wizard_is_full(self) -> None:
        assert CASTER_TYPES["Wizard"] == "full"

    def test_paladin_is_half(self) -> None:
        assert CASTER_TYPES["Paladin"] == "half"

    def test_bard_is_three_quarter(self) -> None:
        assert CASTER_TYPES["Bard"] == "three_quarter"

    def test_caster_level_uses_types_correctly(self) -> None:
        # Wizard 5 (full=5) + Paladin 4 (half=2) using CASTER_TYPES
        result = caster_level(
            {"Wizard": 5, "Paladin": 4},
            CASTER_TYPES,
        )
        assert result == 7
