"""Tests for heroforge.logic.saving_throws.

Reference: PHB p141.
"""

from __future__ import annotations

from heroforge.logic.saving_throws import base_save, fortitude, reflex, will


class TestBaseSave:
    def test_good_progression(self) -> None:
        # Cleric 4, fort=good: 2 + 4//2 = 4
        classes = {"Cleric": 4}
        progressions = {"Cleric": {"fort": "good", "ref": "poor", "will": "good"}}
        assert base_save(classes, "fort", progressions) == 4

    def test_poor_progression(self) -> None:
        # Cleric 4, ref=poor: 4//3 = 1
        classes = {"Cleric": 4}
        progressions = {"Cleric": {"fort": "good", "ref": "poor", "will": "good"}}
        assert base_save(classes, "ref", progressions) == 1

    def test_multiclass(self) -> None:
        # Fighter 5 (fort=good: 2+2=4) + Wizard 5 (fort=poor: 1) = 5
        classes = {"Fighter": 5, "Wizard": 5}
        progressions = {
            "Fighter": {"fort": "good"},
            "Wizard": {"fort": "poor"},
        }
        assert base_save(classes, "fort", progressions) == 5

    def test_empty_classes(self) -> None:
        assert base_save({}, "fort", {}) == 0

    def test_level_1_good(self) -> None:
        # Level 1 good: 2 + 0 = 2
        classes = {"Paladin": 1}
        progressions = {"Paladin": {"fort": "good"}}
        assert base_save(classes, "fort", progressions) == 2

    def test_level_1_poor(self) -> None:
        # Level 1 poor: 1//3 = 0
        classes = {"Wizard": 1}
        progressions = {"Wizard": {"fort": "poor"}}
        assert base_save(classes, "fort", progressions) == 0


class TestFortitude:
    def test_basic(self) -> None:
        assert fortitude(4, 2) == 6

    def test_with_misc(self) -> None:
        assert fortitude(3, 1, misc=2) == 6

    def test_negative_con(self) -> None:
        assert fortitude(2, -2) == 0


class TestReflex:
    def test_basic(self) -> None:
        assert reflex(3, 4) == 7

    def test_negative_dex(self) -> None:
        assert reflex(2, -1) == 1


class TestWill:
    def test_basic(self) -> None:
        assert will(5, 3) == 8

    def test_with_misc(self) -> None:
        assert will(4, 2, misc=1) == 7
