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
    STANDARD_FAMILIAR_MASTER_ABILITIES,
    describe_bonus,
    familiar_natural_link,
    save_bonuses,
    selected_familiar_kind,
    skill_bonuses,
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


def test_save_bonuses_double_with_natural_link() -> None:
    """Natural Link doubles a familiar's unconditional save bonus."""
    bonuses = STANDARD_FAMILIAR_BONUSES
    assert save_bonuses("Rat", bonuses, natural_link=True) == {"fort": 4}
    assert save_bonuses("Weasel", bonuses, natural_link=True) == {"ref": 4}
    # No familiar → nothing to double.
    assert save_bonuses(None, bonuses, natural_link=True) == {}


def test_skill_bonuses_include_creature_and_alertness() -> None:
    """Creature skill bonus and the universal Alertness +2 Spot/Listen combine."""
    bonuses = STANDARD_FAMILIAR_BONUSES
    # Bat: +3 Listen creature bonus stacks with Alertness's +2 Listen, plus the
    # universal +2 Spot from Alertness.
    assert skill_bonuses("Bat", bonuses) == {"Listen": 5, "Spot": 2}
    # Cat: +3 Move Silently plus the universal Alertness bonuses.
    assert skill_bonuses("Cat", bonuses) == {
        "Move Silently": 3,
        "Listen": 2,
        "Spot": 2,
    }
    # A familiar with no skill bonus (Rat) still grants Alertness.
    assert skill_bonuses("Rat", bonuses) == {"Listen": 2, "Spot": 2}
    # No familiar → no skill bonuses at all.
    assert skill_bonuses(None, bonuses) == {}


def test_skill_bonuses_skip_conditional_spot() -> None:
    """The Hawk/Owl situational Spot bonus never feeds the computed total."""
    bonuses = STANDARD_FAMILIAR_BONUSES
    # Only Alertness's +2 Spot applies; the conditional +3 is excluded.
    assert skill_bonuses("Hawk", bonuses) == {"Listen": 2, "Spot": 2}
    assert skill_bonuses("Owl", bonuses) == {"Listen": 2, "Spot": 2}


def test_skill_bonuses_double_with_natural_link() -> None:
    """Natural Link doubles every combined skill bonus."""
    bonuses = STANDARD_FAMILIAR_BONUSES
    assert skill_bonuses("Bat", bonuses, natural_link=True) == {
        "Listen": 10,
        "Spot": 4,
    }


def test_familiar_natural_link_reads_companion_notes() -> None:
    """The Natural Link flag is parsed from the familiar's JSON notes blob."""
    import json

    on = [
        {
            "companion_type": "familiar",
            "creature": "Rat",
            "notes": json.dumps({"natural_link": True}),
        }
    ]
    off = [
        {
            "companion_type": "familiar",
            "creature": "Rat",
            "notes": json.dumps({"natural_link": False}),
        }
    ]
    assert familiar_natural_link(on) is True
    assert familiar_natural_link(off) is False
    # Missing flag, malformed notes, or no familiar all default to False.
    assert familiar_natural_link([{"companion_type": "familiar"}]) is False
    assert (
        familiar_natural_link([{"companion_type": "familiar", "notes": "not-json"}])
        is False
    )
    assert familiar_natural_link([]) is False


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


def test_master_abilities_constant_matches_workbook_source() -> None:
    """The canonical universal benefits mirror Class Abilities!A162:A164."""
    names = [a.name for a in STANDARD_FAMILIAR_MASTER_ABILITIES]
    assert names == ["Alertness", "Scry on Familiar (Sp)", "Natural Link (Su)"]
    alertness = STANDARD_FAMILIAR_MASTER_ABILITIES[0]
    assert "+2 to Spot & Listen checks" in alertness.description


def test_master_abilities_repository_round_trip(tmp_path: Path) -> None:
    """Seeded master-ability rows are read back in declared display order."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.executemany(
            "INSERT INTO familiar_master_abilities "
            "(name, description, sort_order) VALUES (?, ?, ?)",
            [
                (a.name, a.description, i)
                for i, a in enumerate(STANDARD_FAMILIAR_MASTER_ABILITIES)
            ],
        )
        conn.commit()
    finally:
        conn.close()

    repo = GameDataRepository(db_path)
    abilities = repo.get_familiar_master_abilities()
    assert abilities == list(STANDARD_FAMILIAR_MASTER_ABILITIES)


def test_master_abilities_empty_when_unseeded(tmp_path: Path) -> None:
    """An unseeded table yields an empty list so callers can fall back."""
    db_path = tmp_path / "game.db"
    initialize_database(db_path).close()
    repo = GameDataRepository(db_path)
    assert repo.get_familiar_master_abilities() == []


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


def test_model_derived_stats_apply_selected_familiar_when_unseeded(
    qapp: object, tmp_path: Path
) -> None:
    """Fallback familiar save bonuses still apply when the DB table is unseeded."""
    from heroforge.ui.main_window import CharacterModel

    db_path = tmp_path / "game.db"
    initialize_database(db_path).close()

    model = CharacterModel(game_data=GameDataRepository(str(db_path)))
    before = model.derived_stats().fortitude
    model.character.companions = [
        {"companion_type": "familiar", "name": "Scratch", "creature": "Rat"}
    ]
    after = model.derived_stats().fortitude
    assert after == before + 2


def test_model_derived_stats_apply_selected_familiar_without_game_db(
    qapp: object,
) -> None:
    """Fallback familiar save bonuses still apply without a game DB path."""
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    before = model.derived_stats().fortitude
    model.character.companions = [
        {"companion_type": "familiar", "name": "Scratch", "creature": "Rat"}
    ]
    after = model.derived_stats().fortitude
    assert after == before + 2


def test_model_derived_stats_double_with_natural_link(
    qapp: object, tmp_path: Path
) -> None:
    """A Rat familiar with Natural Link active doubles the Fortitude bonus."""
    import json

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
        {
            "companion_type": "familiar",
            "name": "Scratch",
            "creature": "Rat",
            "notes": json.dumps({"natural_link": True}),
        }
    ]
    after = model.derived_stats().fortitude
    assert after == before + 4
