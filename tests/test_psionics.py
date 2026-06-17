"""Unit tests for the psionic power-point / manifester-level calculations.

The expected values are transcribed from the workbook's "Psionic Info" sheet
(Excel tab 7b): class power points by manifester level plus the bonus power
points (``floor(mod x manifester level / 2)``).
"""

from __future__ import annotations

from heroforge.logic.psionics import (
    ManifesterInfo,
    augment_cost,
    compute_psionics,
    manifester_level,
    power_points_per_day,
    psionic_class_levels,
)

# Minimal manifesting-class catalogue used as a test fixture: only the classes
# exercised below, transcribed from the workbook's "Psionic Info" sheet.  At
# runtime the full catalogue is sourced from the seeded ``psionic_progression``
# table via ``GameDataRepository.psionic_progressions``.
_PP_PRIMARY: tuple[int, ...] = (
    0, 2, 6, 11, 17, 25, 35, 46, 58, 72, 88,
    106, 126, 147, 170, 195, 221, 250, 280, 311, 343,
)  # fmt: skip
_PP_PSYCHIC_WARRIOR: tuple[int, ...] = (
    0, 0, 1, 3, 5, 7, 11, 15, 19, 23, 27,
    35, 43, 51, 59, 67, 79, 91, 103, 115, 127,
)  # fmt: skip
MANIFESTING_CLASSES: dict[str, ManifesterInfo] = {
    "Fist of Zuoken": ManifesterInfo("WIS", (0, 1, 3, 6, 10, 15, 23, 31, 43, 55, 71)),
    "Psion": ManifesterInfo("INT", _PP_PRIMARY),
    "Psychic Warrior": ManifesterInfo("WIS", _PP_PSYCHIC_WARRIOR),
    "Wilder": ManifesterInfo("CHA", _PP_PRIMARY),
}


class TestManifesterLevel:
    def test_single_class(self) -> None:
        assert manifester_level({"Psion": 10}) == 10

    def test_highest_class_wins(self) -> None:
        assert manifester_level({"Psion": 5, "Wilder": 8}) == 8

    def test_no_classes(self) -> None:
        assert manifester_level({}) == 0


class TestPowerPointsPerDay:
    def test_class_table_lookup_indexed_by_level(self) -> None:
        # Psion progression: level 5 -> 25 base PP, no ability bonus at mod 0.
        tables = {"Psion": list(MANIFESTING_CLASSES["Psion"].pp_per_day)}
        assert power_points_per_day({"Psion": 5}, 0, tables) == 25

    def test_bonus_power_points_are_half_mod_times_level(self) -> None:
        # Psion 10 with a +5 key ability: 88 base + floor(5 * 10 / 2) = 88 + 25.
        tables = {"Psion": list(MANIFESTING_CLASSES["Psion"].pp_per_day)}
        assert power_points_per_day({"Psion": 10}, 5, tables) == 113

    def test_negative_modifier_grants_no_bonus(self) -> None:
        tables = {"Psion": list(MANIFESTING_CLASSES["Psion"].pp_per_day)}
        assert power_points_per_day({"Psion": 3}, -1, tables) == 11

    def test_level_beyond_table_is_capped(self) -> None:
        # Fist of Zuoken tops out at manifester level 10 (71 PP).
        tables = {
            "Fist of Zuoken": list(MANIFESTING_CLASSES["Fist of Zuoken"].pp_per_day)
        }
        assert power_points_per_day({"Fist of Zuoken": 15}, 0, tables) == 71

    def test_level_beyond_table_caps_bonus_by_capped_manifester_level(self) -> None:
        tables = {
            "Fist of Zuoken": list(MANIFESTING_CLASSES["Fist of Zuoken"].pp_per_day)
        }
        assert power_points_per_day({"Fist of Zuoken": 15}, 4, tables) == 91


class TestPsionicClassLevels:
    def test_filters_to_manifesting_classes(self) -> None:
        levels = psionic_class_levels(
            [("Fighter", 4), ("Psion", 6)], MANIFESTING_CLASSES
        )
        assert levels == {"Psion": 6}

    def test_sums_repeated_entries(self) -> None:
        levels = psionic_class_levels([("Psion", 3), ("Psion", 2)], MANIFESTING_CLASSES)
        assert levels == {"Psion": 5}

    def test_ignores_zero_level_entries(self) -> None:
        assert psionic_class_levels([("Psion", 0)], MANIFESTING_CLASSES) == {}


class TestComputePsionics:
    def test_psion_uses_intelligence(self) -> None:
        summary = compute_psionics([("Psion", 10)], {"INT": 20}, MANIFESTING_CLASSES)
        assert summary.manifester_level == 10
        assert summary.power_points == 113

    def test_wilder_uses_charisma(self) -> None:
        # Wilder 5 (Cha 16, +3): 25 base + floor(3 * 5 / 2) = 25 + 7.
        summary = compute_psionics([("Wilder", 5)], {"CHA": 16}, MANIFESTING_CLASSES)
        assert summary.manifester_level == 5
        assert summary.power_points == 32

    def test_psychic_warrior_uses_wisdom(self) -> None:
        # Psychic Warrior 5 (Wis 14, +2): 7 base + floor(2 * 5 / 2) = 7 + 5.
        summary = compute_psionics(
            [("Psychic Warrior", 5)], {"WIS": 14}, MANIFESTING_CLASSES
        )
        assert summary.manifester_level == 5
        assert summary.power_points == 12

    def test_multiclass_sums_per_ability(self) -> None:
        # Psion 5 (Int 16) -> 25 + 7; Psychic Warrior 5 (Wis 14) -> 7 + 5.
        summary = compute_psionics(
            [("Psion", 5), ("Psychic Warrior", 5)],
            {"INT": 16, "WIS": 14},
            MANIFESTING_CLASSES,
        )
        assert summary.manifester_level == 5
        assert summary.power_points == 44

    def test_non_manifester_yields_zero(self) -> None:
        summary = compute_psionics([("Fighter", 20)], {"INT": 20}, MANIFESTING_CLASSES)
        assert summary.manifester_level == 0
        assert summary.power_points == 0

    def test_missing_ability_defaults_to_ten(self) -> None:
        # No INT supplied -> modifier 0 -> only base PP for Psion 3 (11).
        summary = compute_psionics([("Psion", 3)], {}, MANIFESTING_CLASSES)
        assert summary.power_points == 11


class TestAugmentCost:
    def test_augment_cost(self) -> None:
        assert augment_cost(3, 2, 2) == 7
