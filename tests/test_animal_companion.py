"""Tests for the animal companion level-based stat progression.

These cover the canonical PHB p36 progression table, the effective-druid-level
calculation (Druid/Ranger contributions plus the Natural Bond feat and the
character-level cap), and the application of the progression to a companion's
base creature stats.
"""

from __future__ import annotations

from pathlib import Path

from heroforge.logic.animal_companion import (
    STANDARD_COMPANION_PROGRESSION,
    adjust_hit_dice,
    apply_progression,
    companion_progression,
    cumulative_special_qualities,
    effective_druid_level,
)


def test_progression_table_matches_phb() -> None:
    """The seven tiers reproduce the PHB p36 standard-companion table."""
    rows = [
        (
            t.min_level,
            t.max_level,
            t.bonus_hd,
            t.natural_armor,
            t.ability_adjustment,
            t.bonus_tricks,
        )
        for t in STANDARD_COMPANION_PROGRESSION
    ]
    assert rows == [
        (1, 2, 0, 0, 0, 1),
        (3, 5, 2, 2, 1, 2),
        (6, 8, 4, 4, 2, 3),
        (9, 11, 6, 6, 3, 4),
        (12, 14, 8, 8, 4, 5),
        (15, 17, 10, 10, 5, 6),
        (18, 20, 12, 12, 6, 7),
    ]


def test_companion_progression_lookup_by_level() -> None:
    """Each effective level maps to the correct tier; clamps at the extremes."""
    assert companion_progression(0) is None
    assert companion_progression(1).bonus_hd == 0
    assert companion_progression(2).bonus_tricks == 1
    assert companion_progression(5).natural_armor == 2
    assert companion_progression(7).ability_adjustment == 2
    assert companion_progression(11).bonus_hd == 6
    assert companion_progression(20).bonus_hd == 12
    # Above the table (e.g. epic levels) clamps to the final 18th–20th tier.
    assert companion_progression(25).bonus_hd == 12


def test_cumulative_special_qualities() -> None:
    """Special qualities accumulate across tiers in acquisition order."""
    assert cumulative_special_qualities(0) == ()
    assert cumulative_special_qualities(1) == ("Link", "Share Spells")
    assert cumulative_special_qualities(5) == ("Link", "Share Spells", "Evasion")
    assert cumulative_special_qualities(9) == (
        "Link",
        "Share Spells",
        "Evasion",
        "Devotion",
        "Multiattack",
    )
    # 12th–14th adds nothing new; Improved Evasion appears at 15th.
    assert cumulative_special_qualities(13) == cumulative_special_qualities(11)
    assert "Improved Evasion" in cumulative_special_qualities(15)


def test_effective_druid_level_full_druid() -> None:
    """A pure druid uses its full level."""
    assert effective_druid_level([("Druid", 10)]) == 10
    assert effective_druid_level([("Druid", 1)]) == 1


def test_effective_druid_level_ranger_half() -> None:
    """A ranger counts half its level, rounded down (PHB p47)."""
    assert effective_druid_level([("Ranger", 4)]) == 2
    assert effective_druid_level([("Ranger", 5)]) == 2
    assert effective_druid_level([("Ranger", 8)]) == 4


def test_effective_druid_level_ignores_other_classes() -> None:
    """Classes without an animal companion contribute nothing."""
    assert effective_druid_level([("Fighter", 6)]) == 0
    assert effective_druid_level([("Wizard", 5), ("Druid", 3)]) == 3


def test_effective_druid_level_natural_bond_capped() -> None:
    """Natural Bond adds +3 but never exceeds the character's total level."""
    # Druid 5 in a 10th-level character (e.g. Druid 5 / Fighter 5) → 5 + 3 = 8,
    # under the character-level cap of 10.
    assert effective_druid_level([("Druid", 5), ("Fighter", 5)], ["Natural Bond"]) == 8
    # Pure Druid 5: character level is 5, so Natural Bond is capped at 5.
    assert effective_druid_level([("Druid", 5)], ["Natural Bond"]) == 5
    # Druid 2 / Ranger 4 (effective 2 + 2 = 4) + Natural Bond → 7, capped at 6.
    assert (
        effective_druid_level(
            [("Druid", 2), ("Ranger", 4)], ["Natural Bond"], character_level=6
        )
        == 6
    )


def test_adjust_hit_dice_adds_d8_and_recomputes_modifier() -> None:
    """Bonus HD add d8 dice and recompute the flat modifier from Constitution."""
    # Wolf: 2d8+4 (Con 15 → +2 each HD). +2 bonus HD → 4d8+8.
    assert adjust_hit_dice("2d8+4", 2, con_score=15) == "4d8+8"
    # No Con supplied: keep the existing modifier, just add dice.
    assert adjust_hit_dice("2d8+4", 2) == "4d8+4"
    # Zero bonus HD leaves the count unchanged.
    assert adjust_hit_dice("3d8+3", 0) == "3d8+3"
    # Negative Con modifier yields a negative flat modifier.
    assert adjust_hit_dice("1d8", 1, con_score=8) == "2d8-2"
    # Catalogue creature HD is often a plain count (for example, "2" for Wolf).
    assert adjust_hit_dice("2", 2, con_score=15) == "4d8+8"
    # Without a Con score, count-only HD still scales and keeps no flat modifier.
    assert adjust_hit_dice("2", 2) == "4d8"
    # Unparsable strings are returned unchanged.
    assert adjust_hit_dice("special", 2) == "special"


def test_apply_progression_below_first_tier_is_unchanged() -> None:
    """An effective level below 1 leaves the base stats untouched."""
    scores = {"STR": 13, "DEX": 15, "CON": 15, "INT": 2, "WIS": 12, "CHA": 6}
    result = apply_progression(scores, 2, "2d8+4", 0)
    assert result.ability_scores == scores
    assert result.natural_armor == 2
    assert result.hit_dice == "2d8+4"
    assert result.bonus_hd == 0
    assert result.bonus_tricks == 0
    assert result.special_qualities == ()


def test_apply_progression_scales_stats() -> None:
    """At effective level 9 the Wolf gains +3 Str/Dex, +6 NA and +6 HD."""
    scores = {"STR": 13, "DEX": 15, "CON": 15, "INT": 2, "WIS": 12, "CHA": 6}
    result = apply_progression(scores, 2, "2d8+4", 9)
    assert result.ability_scores["STR"] == 16
    assert result.ability_scores["DEX"] == 18
    # Con unchanged by the standard table.
    assert result.ability_scores["CON"] == 15
    assert result.natural_armor == 8  # base 2 + tier 6
    assert result.bonus_hd == 6
    # 2 base + 6 bonus = 8 HD; Con 15 → +2 each → +16.
    assert result.hit_dice == "8d8+16"
    assert result.bonus_tricks == 4
    assert "Multiattack" in result.special_qualities


def test_apply_progression_does_not_mutate_input() -> None:
    """The base score mapping passed in is not modified in place."""
    scores = {"STR": 13, "DEX": 15, "CON": 15}
    apply_progression(scores, 0, "1d8+1", 6)
    assert scores == {"STR": 13, "DEX": 15, "CON": 15}


# ---------------------------------------------------------------------------
# UI integration: the Animal Companion tab applies the progression
# automatically based on the master's effective druid level.
# ---------------------------------------------------------------------------


def test_tab_applies_progression_on_species_and_relevel(qapp: object) -> None:
    """Selecting a species applies the progression, and re-levelling updates it."""
    import json

    from heroforge.ui.main_window import CharacterModel
    from heroforge.ui.tabs.animal_companion import AnimalCompanionTab

    model = CharacterModel()
    model.character.classes = [("Druid", 9)]
    tab = AnimalCompanionTab(model=model)

    # Simulate a catalogue selection by recording a base species, then apply.
    tab._base = {
        "scores": {"STR": 13, "DEX": 15, "CON": 15, "INT": 2, "WIS": 12, "CHA": 6},
        "natural_armor": 2,
        "hd": "2d8+4",
    }
    tab._name_edit.setText("Rex")
    tab._species_edit.setText("Wolf")
    tab._apply_progression()
    tab._sync_to_model()

    # Effective druid level 9 → +3 Str/Dex, +6 natural armor, +6 HD.
    assert tab._ability_spins["STR"].value() == 16
    assert tab._ability_spins["DEX"].value() == 18
    assert tab._na_spin.value() == 8
    assert tab._hd_edit.text() == "8d8+16"
    assert tab._eff_level_label.text() == "9"
    assert "Multiattack" in tab._special_label.text()

    # The base species is persisted so the progression survives save/load.
    entry = next(
        c for c in model.character.companions if c["companion_type"] == "animal"
    )
    assert "base" in json.loads(entry["notes"])

    # Re-levelling the druid recomputes the companion's stats automatically.
    model.character.classes = [("Druid", 3)]
    model.class_levels_changed.emit()
    assert tab._ability_spins["STR"].value() == 14  # base 13 + tier 1
    assert tab._hd_edit.text() == "4d8+8"  # 2 base + 2 bonus HD
    assert tab._eff_level_label.text() == "3"


def test_tab_manual_entry_not_overwritten_by_progression(qapp: object) -> None:
    """Without a recorded base species, manual stats are left untouched."""
    from heroforge.ui.main_window import CharacterModel
    from heroforge.ui.tabs.animal_companion import AnimalCompanionTab

    model = CharacterModel()
    model.character.classes = [("Druid", 9)]
    tab = AnimalCompanionTab(model=model)

    tab._ability_spins["STR"].setValue(20)
    tab._apply_progression()  # no base recorded → only labels refresh

    assert tab._ability_spins["STR"].value() == 20
    # The read-only summary still reflects the effective druid level.
    assert tab._eff_level_label.text() == "9"
    assert tab._bonus_hd_label.text() == "+6"


# ---------------------------------------------------------------------------
# Database seeding: the progression table and row headings live in the game DB
# and are read back through the repository rather than hardcoded at runtime.
# ---------------------------------------------------------------------------


def test_progression_parsed_from_workbook(tmp_path: Path) -> None:
    """The progression is read from the workbook, not from the in-code constant.

    Seeding from the reference workbook must reproduce the canonical PHB p36
    tiers, proving the data is sourced from the *Animal Companion* sheet rather
    than hardcoded.
    """
    from heroforge.db.seed import _DEFAULT_WORKBOOK, _read_companion_progression

    if not _DEFAULT_WORKBOOK.exists():
        import pytest

        pytest.skip("reference workbook not available")

    parsed = _read_companion_progression(_DEFAULT_WORKBOOK)
    assert parsed == STANDARD_COMPANION_PROGRESSION


def test_progression_falls_back_when_workbook_missing(tmp_path: Path) -> None:
    """A missing workbook falls back to the in-code transcription."""
    from heroforge.db.seed import _read_companion_progression

    missing = tmp_path / "does-not-exist.xlsm"
    assert _read_companion_progression(missing) == STANDARD_COMPANION_PROGRESSION


def test_progression_parser_handles_float_levels_and_blank_rows(tmp_path: Path) -> None:
    """Workbook parsing tolerates float level cells and blank spacer rows."""
    import openpyxl

    from heroforge.db.seed import _COMPANION_SHEET, _read_companion_progression

    workbook = tmp_path / "companion.xlsm"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _COMPANION_SHEET
    ws.append(
        [
            "Level",
            "Bonus HD",
            "Bonus Nat Armor",
            "Str/Dex adjust",
            "Abilities",
        ]
    )
    ws.append([None, None, None, None, None])
    for level in range(1, 21):
        tier = companion_progression(level)
        assert tier is not None
        ws.append(
            [
                float(level),
                tier.bonus_hd,
                tier.natural_armor,
                tier.ability_adjustment,
                tier.special,
            ]
        )
    wb.save(workbook)
    wb.close()

    assert _read_companion_progression(workbook) == STANDARD_COMPANION_PROGRESSION


def test_seed_and_repository_round_trip(tmp_path: Path) -> None:
    """Seeded progression tiers and labels are read back via the repository."""
    from heroforge.db.data_access import GameDataRepository
    from heroforge.db.schema import initialize_database
    from heroforge.db.seed import seed_companion_progression
    from heroforge.logic.animal_companion import COMPANION_PROGRESSION_LABELS

    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        seed_companion_progression(conn)
        # Idempotent: a second seeding must not duplicate rows.
        seed_companion_progression(conn)
    finally:
        conn.close()

    repo = GameDataRepository(db_path)
    records = repo.get_companion_progression_records()
    assert tuple(records) == STANDARD_COMPANION_PROGRESSION

    labels = repo.get_companion_progression_labels()
    assert labels == {e.field_key: e.label for e in COMPANION_PROGRESSION_LABELS}


def test_repository_empty_when_unseeded(tmp_path: Path) -> None:
    """An unseeded database yields empty results so callers fall back."""
    from heroforge.db.data_access import GameDataRepository
    from heroforge.db.schema import initialize_database

    db_path = tmp_path / "game.db"
    initialize_database(db_path).close()

    repo = GameDataRepository(db_path)
    assert repo.get_companion_progression_records() == []
    assert repo.get_companion_progression_labels() == {}


def test_tab_reads_progression_and_labels_from_db(qapp: object, tmp_path: Path) -> None:
    """The tab sources its progression table and row headings from the DB."""
    from heroforge.db.data_access import GameDataRepository
    from heroforge.db.schema import initialize_database
    from heroforge.db.seed import seed_companion_progression
    from heroforge.ui.main_window import CharacterModel
    from heroforge.ui.tabs.animal_companion import AnimalCompanionTab

    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        seed_companion_progression(conn)
    finally:
        conn.close()

    model = CharacterModel(game_data=GameDataRepository(db_path))
    model.character.classes = [("Druid", 9)]
    tab = AnimalCompanionTab(model=model)

    # Loaded from the seeded database, not the in-code constant.
    assert tab._progression == STANDARD_COMPANION_PROGRESSION
    assert tab._labels["effective_druid_level"] == "Effective Druid Level"

    # Progression still applies correctly when driven by the DB-loaded table.
    tab._base = {
        "scores": {"STR": 13, "DEX": 15, "CON": 15, "INT": 2, "WIS": 12, "CHA": 6},
        "natural_armor": 2,
        "hd": "2d8+4",
    }
    tab._apply_progression()
    assert tab._ability_spins["STR"].value() == 16
    assert tab._na_spin.value() == 8
