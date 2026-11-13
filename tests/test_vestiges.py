"""Tests for binder vestige logic (Tome of Magic; Excel tab 8d)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from heroforge.db.schema import initialize_database
from heroforge.logic import vestiges
from heroforge.logic.derived_stats import compute_derived_stats
from heroforge.models.character import Character


@pytest.fixture()
def vestige_db(tmp_path: Path) -> Path:
    """Return a game database whose vestige catalogue has some unknown levels."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    conn.executemany(
        "INSERT INTO vestiges (name, level, vestige_level) VALUES (?, ?, ?)",
        [
            ("Amon", 20, None),
            ("Leraje", 20, 1),
            ("Paimon", 26, 3),
            ("Eligor", 30, None),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def model(qapp: object, vestige_db: Path) -> Any:
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(str(vestige_db)))


def _capture_picker(monkeypatch: pytest.MonkeyPatch, choice: str | None) -> list[str]:
    """Replace the tab's catalogue picker; return the list it was offered."""
    from heroforge.ui.tabs import binder_vestiges as tab_module

    offered: list[str] = []

    def fake_pick(_parent: object, _title: str, _label: str, options: Any) -> Any:
        offered.extend(options)
        return choice

    monkeypatch.setattr(tab_module, "pick_from_catalog", fake_pick)
    return offered


class TestBinderLevel:
    def test_sums_binder_class_levels(self) -> None:
        char = Character(classes=[("Binder", 5), ("Fighter", 2)])
        assert vestiges.binder_level(char) == 5

    def test_case_insensitive_class_name(self) -> None:
        char = Character(classes=[("binder", 3)])
        assert vestiges.binder_level(char) == 3

    def test_non_binder_without_feat_is_zero(self) -> None:
        char = Character(classes=[("Fighter", 10)])
        assert vestiges.binder_level(char) == 0

    def test_bind_vestige_feat_grants_level_one(self) -> None:
        char = Character(classes=[("Fighter", 10)], feats=["Bind Vestige"])
        assert vestiges.binder_level(char) == 1

    def test_improved_bind_vestige_feat_grants_level_five(self) -> None:
        char = Character(
            classes=[("Fighter", 10)],
            feats=["Bind Vestige", "Improved Bind Vestige"],
        )
        assert vestiges.binder_level(char) == 5

    def test_binder_levels_outrank_feat_fallback(self) -> None:
        char = Character(classes=[("Binder", 4)], feats=["Bind Vestige"])
        assert vestiges.binder_level(char) == 4


class TestMaxVestigeLevel:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, 0),
            (1, 1),
            (2, 1),
            (3, 2),
            (5, 3),
            (7, 4),
            (10, 5),
            (12, 6),
            (15, 7),
            (17, 8),
            (20, 8),
        ],
    )
    def test_progression(self, level: int, expected: int) -> None:
        assert vestiges.max_vestige_level(level) == expected


class TestMaxVestigesBound:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            (0, 0),
            (1, 1),
            (7, 1),
            (8, 2),
            (13, 2),
            (14, 3),
            (19, 3),
            (20, 4),
        ],
    )
    def test_progression(self, level: int, expected: int) -> None:
        assert vestiges.max_vestiges_bound(level) == expected


class TestCanBind:
    def test_within_limit(self) -> None:
        assert vestiges.can_bind(1, 1) is True

    def test_above_limit(self) -> None:
        # A 2nd-level vestige needs binder level 3.
        assert vestiges.can_bind(2, 1) is False
        assert vestiges.can_bind(2, 3) is True

    def test_unknown_level_allowed_for_binder(self) -> None:
        assert vestiges.can_bind(None, 1) is True
        assert vestiges.can_bind(None, 0) is False


class TestBoundVestigeNames:
    def test_only_bound_entries(self) -> None:
        char = Character(
            vestiges=[
                {"vestige_name": "Eligor", "level": 7, "bound": True},
                {"vestige_name": "Paimon", "level": 3, "bound": False},
                {"vestige_name": "", "level": 1, "bound": True},
            ]
        )
        assert vestiges.bound_vestige_names(char) == ["Eligor"]

    def test_missing_bound_key_defaults_true(self) -> None:
        char = Character(vestiges=[{"vestige_name": "Paimon", "level": 3}])
        assert vestiges.bound_vestige_names(char) == ["Paimon"]


def _bound(*names: str, binder: int = 15, **kwargs: object) -> Character:
    """Return a Binder of level *binder* with every vestige in *names* bound."""
    return Character(
        classes=[("Binder", binder)] if binder else [],
        vestiges=[
            {"vestige_name": name, "level": None, "bound": True} for name in names
        ],
        **kwargs,  # type: ignore[arg-type]
    )


class TestVestigeBonusSpecs:
    def test_eligor_and_paimon_specs(self) -> None:
        specs = vestiges.vestige_bonus_specs(_bound("Eligor", "Paimon"))
        assert {(s["target"], s["bonus_type"], s["value"]) for s in specs} == {
            ("STR", "untyped", 4),
            ("AC", "natural", 3),
            ("DEX", "untyped", 4),
        }
        assert {s["source"] for s in specs} == {"Eligor", "Paimon"}

    def test_case_insensitive(self) -> None:
        specs = vestiges.vestige_bonus_specs(_bound("eligor"))
        assert ("STR", 4) in {(s["target"], s["value"]) for s in specs}

    def test_suppressed_vestige_has_no_effect(self) -> None:
        char = Character(
            classes=[("Binder", 15)],
            vestiges=[{"vestige_name": "Eligor", "level": 7, "bound": False}],
        )
        assert vestiges.vestige_bonus_specs(char) == []

    def test_unknown_vestige_has_no_effect(self) -> None:
        assert vestiges.vestige_bonus_specs(_bound("Amon")) == []


class TestEffectsFeedDerivedStats:
    def test_ability_bonus_changes_modifier(self) -> None:
        stats = compute_derived_stats(
            _bound("Eligor", ability_scores={"STR": 10, "DEX": 14})
        )
        # +4 STR raises STR to 14 (+2 modifier) from the baseline +0.
        assert stats.effective_ability_scores["STR"] == 14
        assert stats.ability_modifiers["STR"] == 2

    def test_untyped_bonus_stacks_with_enhancement_buff(self) -> None:
        # Eligor's untyped +4 stacks with Bull's Strength's +4 enhancement
        # (PHB p176), through the same typed-bonus path as buffs and items.
        buff = {
            "id": "b1",
            "bonus_type": "enhancement",
            "target_stat": "STR",
            "amount": 4,
        }
        stats = compute_derived_stats(
            _bound("Eligor", ability_scores={"STR": 10}, buffs=[buff])
        )
        assert stats.effective_ability_scores["STR"] == 18

    def test_natural_armor_bonus_raises_ac(self) -> None:
        without = compute_derived_stats(_bound(ability_scores={"DEX": 10}))
        with_vestige = compute_derived_stats(
            _bound("Eligor", ability_scores={"DEX": 10})
        )
        assert with_vestige.armor_class == without.armor_class + 3
        assert with_vestige.touch_ac == without.touch_ac


class TestVestigeLevelFallback:
    def test_catalogue_level_wins(self) -> None:
        assert vestiges.vestige_level_for("Eligor", 5) == 5

    def test_falls_back_to_standard_level(self) -> None:
        assert vestiges.vestige_level_for("Eligor", None) == 7
        assert vestiges.vestige_level_for(" eligor ", None) == 7

    def test_unknown_vestige_has_no_level(self) -> None:
        assert vestiges.vestige_level_for("Homebrew", None) is None

    def test_picker_filters_unknown_catalogue_levels_by_standard_level(
        self, model: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from heroforge.ui.tabs.binder_vestiges import BinderVestigesTab

        model.character.classes = [("Binder", 1)]
        tab = BinderVestigesTab(model)
        offered = _capture_picker(monkeypatch, "Amon")
        tab._add()
        # Eligor (7th level, NULL in the catalogue) is not offered at level 1.
        assert offered == ["Amon", "Leraje"]
        assert model.character.vestiges == [
            {"vestige_name": "Amon", "level": 1, "bound": True}
        ]

    def test_loaded_entry_without_level_shows_standard_level(self, model: Any) -> None:
        from heroforge.ui.tabs.binder_vestiges import BinderVestigesTab

        model.character.classes = [("Binder", 15)]
        model.character.vestiges = [
            {"vestige_name": "Eligor", "level": None, "bound": True}
        ]
        tab = BinderVestigesTab(model)
        item = tab._list.item(0)
        assert item is not None
        assert item.text() == "Eligor  (level 7)"

    def test_save_tolerates_unknown_level(self, tmp_path: Path) -> None:
        from heroforge.db.character_repo import (
            load_character_from_file,
            save_character_to_file,
        )

        char = Character(
            name="Binder",
            vestiges=[{"vestige_name": "Homebrew", "level": None, "bound": True}],
        )
        path = tmp_path / "binder.hfc"
        save_character_to_file(char, path)
        assert load_character_from_file(path).vestiges == char.vestiges
