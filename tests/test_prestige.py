"""Tests for heroforge.logic.prestige.

Covers prestige-class prerequisite evaluation, the available-class filter, the
standard prerequisite data, and the custom (homebrew) prestige-class
serialization helpers.

Reference: DMG Chapter 2 (Prestige Classes).
"""

from __future__ import annotations

import json

from heroforge.logic.prestige import (
    CUSTOM_CLASS_CONTENT_TYPE,
    STANDARD_PRESTIGE_PREREQUISITES,
    available_prestige_classes,
    check_prestige_prerequisites,
    custom_class_from_content,
    custom_class_to_content,
    list_custom_classes,
    list_custom_prestige_classes,
)
from heroforge.models.class_ import Class


class TestCheckPrestigePrerequisites:
    def test_empty_prerequisites_are_met(self) -> None:
        assert check_prestige_prerequisites([], 0, {}, {}, [], 1, {}) is True

    def test_blank_strings_are_ignored(self) -> None:
        assert check_prestige_prerequisites(["", "   "], 0, {}, {}, [], 1, {}) is True

    def test_bab_prerequisite_met(self) -> None:
        assert check_prestige_prerequisites(["+6 BAB"], 6, {}, {}, [], 6, {}) is True

    def test_bab_prerequisite_unmet(self) -> None:
        assert check_prestige_prerequisites(["+6 BAB"], 5, {}, {}, [], 5, {}) is False

    def test_feat_prerequisite_met(self) -> None:
        assert (
            check_prestige_prerequisites(["Dodge"], 0, {}, {}, ["Dodge"], 1, {}) is True
        )

    def test_feat_prerequisite_unmet(self) -> None:
        assert check_prestige_prerequisites(["Dodge"], 0, {}, {}, [], 1, {}) is False

    def test_skill_rank_prerequisite_met(self) -> None:
        assert (
            check_prestige_prerequisites(
                ["Hide 8 ranks"], 0, {}, {"Hide": 8.0}, [], 8, {}
            )
            is True
        )

    def test_skill_rank_prerequisite_unmet(self) -> None:
        assert (
            check_prestige_prerequisites(
                ["Hide 8 ranks"], 0, {}, {"Hide": 7.0}, [], 8, {}
            )
            is False
        )

    def test_ability_score_prerequisite(self) -> None:
        assert (
            check_prestige_prerequisites(["STR 13"], 0, {"STR": 13}, {}, [], 1, {})
            is True
        )
        assert (
            check_prestige_prerequisites(["STR 13"], 0, {"STR": 12}, {}, [], 1, {})
            is False
        )

    def test_class_level_prerequisite_met(self) -> None:
        # "Wizard 5" requires at least five Wizard levels.
        assert (
            check_prestige_prerequisites(["Wizard 5"], 0, {}, {}, [], 5, {"Wizard": 5})
            is True
        )

    def test_class_level_prerequisite_unmet(self) -> None:
        assert (
            check_prestige_prerequisites(["Wizard 5"], 0, {}, {}, [], 4, {"Wizard": 4})
            is False
        )

    def test_class_level_prerequisite_is_case_insensitive(self) -> None:
        assert (
            check_prestige_prerequisites(["wizard 3"], 0, {}, {}, [], 5, {"Wizard": 5})
            is True
        )

    def test_class_level_prerequisite_missing_class_fails(self) -> None:
        # A class the character does not have cannot satisfy a level prereq, and
        # is not interpretable as any other supported form, so it fails closed.
        assert (
            check_prestige_prerequisites(["Wizard 5"], 0, {}, {}, [], 5, {"Fighter": 5})
            is False
        )

    def test_multiple_prerequisites_all_required(self) -> None:
        prereqs = ["+6 BAB", "Dodge", "Tumble 5 ranks"]
        assert (
            check_prestige_prerequisites(
                prereqs, 6, {}, {"Tumble": 5.0}, ["Dodge"], 6, {}
            )
            is True
        )
        # Missing the feat fails the whole set.
        assert (
            check_prestige_prerequisites(prereqs, 6, {}, {"Tumble": 5.0}, [], 6, {})
            is False
        )

    def test_unknown_prerequisite_fails_closed(self) -> None:
        assert (
            check_prestige_prerequisites(
                ["ability to cast 3rd-level arcane spells"],
                10,
                {},
                {},
                [],
                10,
                {},
            )
            is False
        )


class TestAvailablePrestigeClasses:
    def test_returns_only_qualifying_classes_sorted(self) -> None:
        all_classes = [
            {"name": "Arcane Archer"},
            {"name": "Duelist"},
            {"name": "Shadowdancer"},
        ]
        prereq_map = {
            "Arcane Archer": ["+6 BAB", "Point Blank Shot"],
            "Duelist": ["+6 BAB", "Dodge"],
            "Shadowdancer": ["Hide 10 ranks"],
        }
        result = available_prestige_classes(
            all_classes,
            prereq_map,
            character_bab=6,
            character_ability_scores={},
            character_skills={},
            character_feats=["Point Blank Shot", "Dodge"],
            character_level=6,
            character_classes={},
        )
        # Arcane Archer and Duelist qualify; Shadowdancer (needs Hide 10) does
        # not.  Results are sorted alphabetically.
        assert result == ["Arcane Archer", "Duelist"]

    def test_class_without_prereqs_always_available(self) -> None:
        result = available_prestige_classes(
            [{"name": "Homebrew PrC"}],
            {},
            character_bab=0,
            character_ability_scores={},
            character_skills={},
            character_feats=[],
            character_level=1,
            character_classes={},
        )
        assert result == ["Homebrew PrC"]


class TestStandardPrestigePrerequisites:
    def test_known_classes_present(self) -> None:
        for name in ("Arcane Archer", "Assassin", "Blackguard", "Shadowdancer"):
            assert name in STANDARD_PRESTIGE_PREREQUISITES

    def test_all_entries_are_nonempty_string_tuples(self) -> None:
        for name, prereqs in STANDARD_PRESTIGE_PREREQUISITES.items():
            assert isinstance(name, str) and name
            assert prereqs, f"{name} has no prerequisites"
            assert all(isinstance(p, str) and p.strip() for p in prereqs)


class TestCustomClassContent:
    def test_round_trips_through_content(self) -> None:
        cls = Class(
            name="Spellblade",
            is_prestige=True,
            hit_die=8,
            bab_progression="fast",
            fort_progression="good",
            ref_progression="poor",
            will_progression="good",
            skill_points_per_level=4,
            prerequisites=["+5 BAB", "Spellcraft 8 ranks"],
        )
        entry = custom_class_to_content(cls)
        assert entry["content_type"] == CUSTOM_CLASS_CONTENT_TYPE
        assert entry["name"] == "Spellblade"
        restored = custom_class_from_content(entry)
        assert restored is not None
        assert restored.name == "Spellblade"
        assert restored.is_prestige is True
        assert restored.bab_progression == "fast"
        assert restored.skill_points_per_level == 4
        assert restored.prerequisites == ["+5 BAB", "Spellcraft 8 ranks"]

    def test_from_content_ignores_other_content(self) -> None:
        assert (
            custom_class_from_content({"content_type": "familiar", "name": "X"}) is None
        )
        assert (
            custom_class_from_content(
                {"content_type": CUSTOM_CLASS_CONTENT_TYPE, "name": "  "}
            )
            is None
        )

    def test_from_content_applies_defaults(self) -> None:
        entry = {
            "content_type": CUSTOM_CLASS_CONTENT_TYPE,
            "name": "Barebones",
            "definition": json.dumps({}),
        }
        cls = custom_class_from_content(entry)
        assert cls is not None
        assert cls.is_prestige is False
        assert cls.hit_die == 8
        assert cls.bab_progression == "medium"
        assert cls.skill_points_per_level == 2
        assert cls.prerequisites == []

    def test_list_custom_classes_filters_other_content(self) -> None:
        content = [
            custom_class_to_content(Class(name="Base One", is_prestige=False)),
            custom_class_to_content(Class(name="PrC One", is_prestige=True)),
            {"content_type": "familiar", "name": "Imp"},
        ]
        assert [c.name for c in list_custom_classes(content)] == [
            "Base One",
            "PrC One",
        ]
        assert [c.name for c in list_custom_prestige_classes(content)] == ["PrC One"]
