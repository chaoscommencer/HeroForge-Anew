"""Unit tests for incarnum (Magic of Incarnum) calculations.

Reference values are drawn from the workbook's "Soulmelds" sheet (Excel tab 8)
and the Magic of Incarnum sourcebook.
"""

from __future__ import annotations

from heroforge.logic.incarnum import (
    IncarnumProgression,
    chakra_binds_available,
    compute_incarnum,
    essentia_pool,
    meldshaper_level,
    soulmeld_capacity,
    soulmelds_shapeable,
    unlocked_chakras,
)


class TestEssentiaPool:
    def test_incarnate_level_9(self) -> None:
        # Incarnate essentia at level 9 is 9 (workbook TblClassEssentia).
        assert essentia_pool({"Incarnate": 9}) == 9

    def test_incarnate_level_20(self) -> None:
        # Incarnate essentia tops out at 26 at level 20.
        assert essentia_pool({"Incarnate": 20}) == 26

    def test_feat_bonus_added(self) -> None:
        # Bonus Essentia feat grants +1 essentia (MoI p41).
        assert essentia_pool({"Incarnate": 9}, feat_bonus=1) == 10

    def test_multiclass_sums(self) -> None:
        # Essentia from multiple meldshaping classes stacks.
        assert essentia_pool({"Incarnate": 9, "Totemist": 9}) == 9 + 6

    def test_non_meldshaper_contributes_nothing(self) -> None:
        assert essentia_pool({"Fighter": 20}) == 0

    def test_zero_level_is_zero(self) -> None:
        assert essentia_pool({"Incarnate": 0}) == 0


class TestSoulmeldCapacity:
    def test_capacity_by_character_level(self) -> None:
        # 1 at 1st-5th, 2 at 6th-11th, 3 at 12th-17th, 4 at 18th+.
        assert soulmeld_capacity(1) == 1
        assert soulmeld_capacity(5) == 1
        assert soulmeld_capacity(6) == 2
        assert soulmeld_capacity(11) == 2
        assert soulmeld_capacity(12) == 3
        assert soulmeld_capacity(17) == 3
        assert soulmeld_capacity(18) == 4
        assert soulmeld_capacity(20) == 4

    def test_zero_level(self) -> None:
        assert soulmeld_capacity(0) == 0


class TestSoulmeldsShapeable:
    def test_incarnate_level_1(self) -> None:
        assert soulmelds_shapeable({"Incarnate": 1}) == 2

    def test_incarnate_level_20(self) -> None:
        assert soulmelds_shapeable({"Incarnate": 20}) == 9


class TestMeldshaperLevel:
    def test_highest_single_class(self) -> None:
        assert meldshaper_level({"Incarnate": 9, "Totemist": 4}) == 9

    def test_ignores_non_meldshaping(self) -> None:
        assert meldshaper_level({"Fighter": 20}) == 0


class TestChakraBinds:
    def test_incarnate_level_9_unlocks(self) -> None:
        # Crown(2), Feet(4), Hands(4), Arms(9), Brow(9), Shoulders(9) = 6.
        chakras = unlocked_chakras({"Incarnate": 9})
        assert chakras == {"Crown", "Feet", "Hands", "Arms", "Brow", "Shoulders"}
        assert chakra_binds_available({"Incarnate": 9}) == 6

    def test_incarnate_level_20_unlocks_all_ten(self) -> None:
        assert chakra_binds_available({"Incarnate": 20}) == 10

    def test_totemist_totem_chakra_at_level_2(self) -> None:
        assert "Totem" in unlocked_chakras({"Totemist": 2})

    def test_multiclass_union(self) -> None:
        # Incarnate 9 (6 chakras) union Totemist 9 (Totem + 5 shared) = 7.
        assert chakra_binds_available({"Incarnate": 9, "Totemist": 9}) == 7

    def test_no_binds_below_threshold(self) -> None:
        assert chakra_binds_available({"Incarnate": 1}) == 0


class TestComputeIncarnum:
    def test_single_class_summary(self) -> None:
        summary = compute_incarnum([("Incarnate", 9)], character_level=9)
        assert summary.meldshaper_level == 9
        assert summary.essentia_pool == 9
        assert summary.soulmeld_capacity == 2
        assert summary.chakra_binds_available == 6

    def test_capped_character_summary(self) -> None:
        summary = compute_incarnum([("Incarnate", 20)], character_level=20)
        assert summary.essentia_pool == 26
        assert summary.soulmeld_capacity == 4
        assert summary.chakra_binds_available == 10

    def test_non_meldshaper_yields_zero(self) -> None:
        summary = compute_incarnum([("Fighter", 20)], character_level=20)
        assert summary.essentia_pool == 0
        assert summary.chakra_binds_available == 0
        assert summary.meldshaper_level == 0

    def test_explicit_progressions_override(self) -> None:
        progressions = {
            "Custom": IncarnumProgression(
                essentia=(0, 5, 10),
                soulmelds=(0, 1, 2),
                chakra_unlocks={"Crown": 1, "Feet": 2},
            )
        }
        summary = compute_incarnum(
            [("Custom", 2)], character_level=2, progressions=progressions
        )
        assert summary.essentia_pool == 10
        assert summary.soulmelds_shapeable == 2
        assert summary.chakra_binds_available == 2
        assert summary.meldshaper_level == 2
