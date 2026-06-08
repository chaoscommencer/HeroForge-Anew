"""Tests for structured familiar bonuses: data, text generation, and mechanics.

These cover the single structured source of truth
(:mod:`heroforge.logic.familiar`), its round trip through the database seeder
and repository, and the mechanical application of non-situational saving-throw
benefits via the derived-stats pipeline.
"""

from __future__ import annotations

from pathlib import Path

from heroforge.db.data_access import GameDataRepository
from heroforge.db.schema import initialize_database
from heroforge.db.seed import seed_familiar_bonuses
from heroforge.logic.derived_stats import compute_derived_stats
from heroforge.logic.familiar import (
    STANDARD_FAMILIAR_BONUSES,
    describe_bonus,
    save_bonuses,
    selected_familiar_kind,
)
from heroforge.models.character import Character

# The exact helper text expected for each standard familiar (PHB p52–53).
_EXPECTED_TEXT = {
    "bat": "Master gains +3 bonus on Listen checks.",
    "cat": "Master gains +3 bonus on Move Silently checks.",
    "hawk": "Master gains +3 bonus on Spot checks in daylight.",
    "lizard": "Master gains +3 bonus on Climb checks.",
    "owl": "Master gains +3 bonus on Spot checks in shadows/darkness.",
    "rat": "Master gains +2 bonus on Fortitude saves.",
    "raven": "Master gains +3 bonus on Appraise checks.",
    "snake": "Master gains +3 bonus on Bluff checks.",
    "toad": "Master gains +3 hit points.",
    "weasel": "Master gains +2 bonus on Reflex saves.",
}


def test_generated_text_matches_expected() -> None:
    """``describe_bonus`` reproduces the canonical PHB wording from structure."""
    generated = {
        b.creature_name.lower(): describe_bonus(b) for b in STANDARD_FAMILIAR_BONUSES
    }
    assert generated == _EXPECTED_TEXT


def test_conditional_only_for_hawk_and_owl() -> None:
    """Only the lighting-dependent Spot bonuses are flagged conditional."""
    conditional = {b.creature_name for b in STANDARD_FAMILIAR_BONUSES if b.conditional}
    assert conditional == {"Hawk", "Owl"}


def test_save_bonuses_apply_only_unconditional_saves() -> None:
    """Rat/Weasel yield save bonuses; skills, HP and conditionals do not."""
    bonuses = STANDARD_FAMILIAR_BONUSES
    assert save_bonuses("Rat", bonuses) == {"fort": 2}
    assert save_bonuses("weasel", bonuses) == {"ref": 2}  # case-insensitive
    assert save_bonuses("Bat", bonuses) == {}  # skill bonus
    assert save_bonuses("Toad", bonuses) == {}  # hit points
    assert save_bonuses("Hawk", bonuses) == {}  # conditional Spot
    assert save_bonuses(None, bonuses) == {}
    assert save_bonuses("Unknown", bonuses) == {}


def test_selected_familiar_kind() -> None:
    """The familiar's creature kind is extracted from the companion list."""
    companions = [
        {"companion_type": "animal", "creature": "Wolf"},
        {"companion_type": "familiar", "creature": "Rat"},
    ]
    assert selected_familiar_kind(companions) == "Rat"
    assert selected_familiar_kind([]) is None
    assert selected_familiar_kind([{"companion_type": "familiar"}]) is None


def test_seed_and_repository_round_trip(tmp_path: Path) -> None:
    """Seeded structured rows are read back and regenerated into text."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        seed_familiar_bonuses(conn)
        # Idempotent: a second seeding must not duplicate rows.
        seed_familiar_bonuses(conn)
    finally:
        conn.close()

    repo = GameDataRepository(db_path)
    records = repo.get_familiar_bonus_records()
    assert len(records) == len(STANDARD_FAMILIAR_BONUSES)

    rat = next(r for r in records if r.creature_name == "Rat")
    assert rat.value == 2
    assert rat.kind == "save"
    assert rat.target == "Fortitude"
    assert rat.condition == ""

    assert repo.get_familiar_bonuses() == _EXPECTED_TEXT


def test_derived_stats_apply_familiar_save_bonus() -> None:
    """A familiar's save bonus flows into the derived saving throws."""
    character = Character()
    character.ability_scores = {
        "STR": 10,
        "DEX": 10,
        "CON": 10,
        "INT": 10,
        "WIS": 10,
        "CHA": 10,
    }
    base = compute_derived_stats(character)
    boosted = compute_derived_stats(
        character, save_bonuses=save_bonuses("Rat", STANDARD_FAMILIAR_BONUSES)
    )
    assert boosted.fortitude == base.fortitude + 2
    assert boosted.reflex == base.reflex
    assert boosted.will == base.will


def test_model_derived_stats_apply_selected_familiar(
    qapp: object, tmp_path: Path
) -> None:
    """Selecting a Rat familiar raises the model's derived Fortitude save."""
    from heroforge.ui.main_window import CharacterModel

    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        seed_familiar_bonuses(conn)
    finally:
        conn.close()

    model = CharacterModel(game_data=GameDataRepository(str(db_path)))
    before = model.derived_stats().fortitude
    model.character.companions = [
        {"companion_type": "familiar", "name": "Scratch", "creature": "Rat"}
    ]
    after = model.derived_stats().fortitude
    assert after == before + 2
