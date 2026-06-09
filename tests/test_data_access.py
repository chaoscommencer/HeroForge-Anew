"""Tests for the read-only game data-access layer (heroforge.db.data_access)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from heroforge.db.data_access import GameDataRepository
from heroforge.db.schema import get_connection, initialize_database


@pytest.fixture()
def seeded_repo(tmp_path: Path) -> GameDataRepository:
    """A repository over a small, hand-seeded game database."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.execute(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            ("PHB", "Player's Handbook"),
        )
        conn.execute(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            ("CAr", "Complete Arcane"),
        )
        conn.executemany(
            "INSERT INTO feats (name, type, description, benefit, source) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("Power Attack", "General", "Trade accuracy for damage.", "", "PHB"),
                ("Empower Spell", "Metamagic", "Boost spell effect.", "", "CAr"),
                ("Toughness", "General", "+3 hit points.", "", None),
            ],
        )
        conn.executemany(
            "INSERT INTO races (name, source) VALUES (?, ?)",
            [("Human", "PHB"), ("Elf", "PHB")],
        )
        conn.executemany(
            "INSERT INTO templates (name, source) VALUES (?, ?)",
            [("Celestial", "PHB"), ("Fiendish", "PHB")],
        )
        conn.executemany(
            "INSERT INTO spells_per_day (class_name, caster_level, spell_level, slots) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Wizard", 1, 0, 3),
                ("Wizard", 1, 1, 1),
                ("Cleric", 1, 0, 3),
            ],
        )
        conn.executemany(
            "INSERT INTO spells_known (class_name, caster_level, spell_level, count) "
            "VALUES (?, ?, ?, ?)",
            [("Sorcerer", 1, 0, 4), ("Sorcerer", 1, 1, 2)],
        )
        conn.executemany(
            "INSERT INTO incarnum_abilities (name, description) VALUES (?, ?)",
            [
                ("Airstep Sandals", "You may step through air."),
                ("Dissolving Spittle", "Spit acid as a ranged touch attack."),
            ],
        )
        conn.executemany(
            "INSERT INTO vestiges (name, level, source) VALUES (?, ?, ?)",
            [
                ("Acererak", 8, "ToM"),
                ("Aym", 4, "ToM"),
                ("Leraje", 3, None),
            ],
        )
        conn.executemany(
            "INSERT INTO marshal_auras (name, type) VALUES (?, ?)",
            [
                ("Motivate Dexterity", "Minor"),
                ("Motivate Strength", "Minor"),
                ("Demand Fortitude", "Major"),
            ],
        )
        conn.executemany(
            "INSERT INTO racial_abilities (race_name, ability_name, description) "
            "VALUES (?, ?, ?)",
            [
                ("Dwarf", "Darkvision", "Can see 60 ft. in total darkness."),
                ("Dwarf", "Stonecunning", "+2 bonus on checks for unusual stonework."),
                (
                    "Elf",
                    "Low-Light Vision",
                    "Can see twice as far as humans in dim light.",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return GameDataRepository(db_path)


class TestAvailability:
    def test_missing_db_is_unavailable(self, tmp_path: Path) -> None:
        repo = GameDataRepository(tmp_path / "does_not_exist.db")
        assert repo.available is False
        assert repo.list_feats() == []
        assert repo.list_sources() == []

    def test_none_db_is_unavailable(self) -> None:
        repo = GameDataRepository(None)
        assert repo.available is False
        assert repo.list_caster_classes() == []


class TestSources:
    def test_list_sources(self, seeded_repo: GameDataRepository) -> None:
        sources = seeded_repo.list_sources()
        assert [s.abbreviation for s in sources] == ["CAr", "PHB"]
        assert sources[1].label == "PHB – Player's Handbook"


class TestFeats:
    def test_list_all_feats(self, seeded_repo: GameDataRepository) -> None:
        names = [f.name for f in seeded_repo.list_feats()]
        assert names == ["Empower Spell", "Power Attack", "Toughness"]

    def test_source_filter_includes_unsourced(
        self, seeded_repo: GameDataRepository
    ) -> None:
        # Filtering to PHB keeps PHB feats and the NULL-source feat, but drops CAr.
        names = [f.name for f in seeded_repo.list_feats(sources=["PHB"])]
        assert names == ["Power Attack", "Toughness"]

    def test_empty_source_filter_returns_all(
        self, seeded_repo: GameDataRepository
    ) -> None:
        assert len(seeded_repo.list_feats(sources=[])) == 3


class TestRacesTemplates:
    def test_list_races(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_races() == ["Elf", "Human"]

    def test_list_templates(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_templates() == ["Celestial", "Fiendish"]


class TestSpells:
    def test_caster_classes_union(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_caster_classes() == ["Cleric", "Sorcerer", "Wizard"]

    def test_spells_per_day(self, seeded_repo: GameDataRepository) -> None:
        slots = seeded_repo.spells_per_day("Wizard")
        assert [(s.spell_level, s.count) for s in slots] == [(0, 3), (1, 1)]

    def test_spells_known(self, seeded_repo: GameDataRepository) -> None:
        known = seeded_repo.spells_known("Sorcerer")
        assert [(s.spell_level, s.count) for s in known] == [(0, 4), (1, 2)]


class TestIncarnumAbilities:
    def test_list_all(self, seeded_repo: GameDataRepository) -> None:
        abilities = seeded_repo.list_incarnum_abilities()
        assert [a.name for a in abilities] == ["Airstep Sandals", "Dissolving Spittle"]

    def test_description_present(self, seeded_repo: GameDataRepository) -> None:
        abilities = seeded_repo.list_incarnum_abilities()
        assert abilities[0].description == "You may step through air."

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_incarnum_abilities() == []


class TestVestiges:
    def test_list_all(self, seeded_repo: GameDataRepository) -> None:
        vestiges = seeded_repo.list_vestiges()
        assert [v.name for v in vestiges] == ["Acererak", "Aym", "Leraje"]

    def test_level_and_source(self, seeded_repo: GameDataRepository) -> None:
        vestiges = seeded_repo.list_vestiges()
        acererak = next(v for v in vestiges if v.name == "Acererak")
        assert acererak.level == 8
        assert acererak.source == "ToM"

    def test_null_source_is_none(self, seeded_repo: GameDataRepository) -> None:
        vestiges = seeded_repo.list_vestiges()
        leraje = next(v for v in vestiges if v.name == "Leraje")
        assert leraje.source is None

    def test_null_source_included_in_filter(
        self, seeded_repo: GameDataRepository
    ) -> None:
        # Leraje has NULL source; it must appear when filtering by "ToM".
        vestiges = seeded_repo.list_vestiges(sources=["ToM"])
        names = [v.name for v in vestiges]
        assert "Leraje" in names
        assert "Acererak" in names

    def test_unmatched_source_filter_returns_only_null_sourced(
        self, seeded_repo: GameDataRepository
    ) -> None:
        # Filtering by a source that no vestige has keeps only NULL-sourced rows.
        vestiges = seeded_repo.list_vestiges(sources=["PHB"])
        names = [v.name for v in vestiges]
        assert names == ["Leraje"]
        assert "Acererak" not in names
        assert "Aym" not in names

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_vestiges() == []


class TestMarshalAuras:
    def test_list_all(self, seeded_repo: GameDataRepository) -> None:
        auras = seeded_repo.list_marshal_auras()
        assert len(auras) == 3

    def test_filter_by_type(self, seeded_repo: GameDataRepository) -> None:
        minor = seeded_repo.list_marshal_auras(aura_type="Minor")
        assert all(a.aura_type == "Minor" for a in minor)
        assert {a.name for a in minor} == {"Motivate Dexterity", "Motivate Strength"}

    def test_filter_major(self, seeded_repo: GameDataRepository) -> None:
        major = seeded_repo.list_marshal_auras(aura_type="Major")
        assert [a.name for a in major] == ["Demand Fortitude"]

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_marshal_auras() == []


class TestRacialAbilities:
    def test_list_all(self, seeded_repo: GameDataRepository) -> None:
        abilities = seeded_repo.list_racial_abilities()
        assert len(abilities) == 3

    def test_filter_by_race(self, seeded_repo: GameDataRepository) -> None:
        dwarf = seeded_repo.list_racial_abilities(race_name="Dwarf")
        assert {a.ability_name for a in dwarf} == {"Darkvision", "Stonecunning"}

    def test_description_present(self, seeded_repo: GameDataRepository) -> None:
        elf = seeded_repo.list_racial_abilities(race_name="Elf")
        assert len(elf) == 1
        assert "dim light" in elf[0].description

    def test_unknown_race_returns_empty(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_racial_abilities(race_name="Gnome") == []

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_racial_abilities() == []


def test_repository_is_read_only(
    seeded_repo: GameDataRepository, tmp_path: Path
) -> None:
    """Listing data must never mutate the backing database."""
    assert seeded_repo.db_path is not None
    conn = get_connection(seeded_repo.db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM feats").fetchone()[0]
    finally:
        conn.close()
    seeded_repo.list_feats()
    seeded_repo.list_races()
    conn = get_connection(seeded_repo.db_path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM feats").fetchone()[0]
    finally:
        conn.close()
    assert before == after == 3


def test_query_tolerates_missing_table(tmp_path: Path) -> None:
    """A database file without the expected tables yields empty results."""
    db_path = tmp_path / "bare.db"
    sqlite3.connect(db_path).close()  # empty file, no schema
    repo = GameDataRepository(db_path)
    assert repo.list_feats() == []
    assert repo.list_caster_classes() == []


class TestAvailability:
    def test_missing_db_is_unavailable(self, tmp_path: Path) -> None:
        repo = GameDataRepository(tmp_path / "does_not_exist.db")
        assert repo.available is False
        assert repo.list_feats() == []
        assert repo.list_sources() == []

    def test_none_db_is_unavailable(self) -> None:
        repo = GameDataRepository(None)
        assert repo.available is False
        assert repo.list_caster_classes() == []


class TestSources:
    def test_list_sources(self, seeded_repo: GameDataRepository) -> None:
        sources = seeded_repo.list_sources()
        assert [s.abbreviation for s in sources] == ["CAr", "PHB"]
        assert sources[1].label == "PHB – Player's Handbook"


class TestFeats:
    def test_list_all_feats(self, seeded_repo: GameDataRepository) -> None:
        names = [f.name for f in seeded_repo.list_feats()]
        assert names == ["Empower Spell", "Power Attack", "Toughness"]

    def test_source_filter_includes_unsourced(
        self, seeded_repo: GameDataRepository
    ) -> None:
        # Filtering to PHB keeps PHB feats and the NULL-source feat, but drops CAr.
        names = [f.name for f in seeded_repo.list_feats(sources=["PHB"])]
        assert names == ["Power Attack", "Toughness"]

    def test_empty_source_filter_returns_all(
        self, seeded_repo: GameDataRepository
    ) -> None:
        assert len(seeded_repo.list_feats(sources=[])) == 3


class TestRacesTemplates:
    def test_list_races(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_races() == ["Elf", "Human"]

    def test_list_templates(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_templates() == ["Celestial", "Fiendish"]


class TestSpells:
    def test_caster_classes_union(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_caster_classes() == ["Cleric", "Sorcerer", "Wizard"]

    def test_spells_per_day(self, seeded_repo: GameDataRepository) -> None:
        slots = seeded_repo.spells_per_day("Wizard")
        assert [(s.spell_level, s.count) for s in slots] == [(0, 3), (1, 1)]

    def test_spells_known(self, seeded_repo: GameDataRepository) -> None:
        known = seeded_repo.spells_known("Sorcerer")
        assert [(s.spell_level, s.count) for s in known] == [(0, 4), (1, 2)]


class TestHitDiceAndProfiles:
    """Coverage for the HP / AC / ECL accessors added for the Stats tab."""

    def _repo(self, tmp_path: Path) -> GameDataRepository:
        db_path = tmp_path / "profiles.db"
        conn = initialize_database(db_path)
        try:
            conn.executemany(
                "INSERT INTO classes (name, hit_die) VALUES (?, ?)",
                [("Fighter", 10), ("Wizard", 4), ("Mystery", None)],
            )
            conn.execute(
                "INSERT INTO races (name, size, natural_armor, level_adjustment) "
                "VALUES (?, ?, ?, ?)",
                ("Lizardfolk", "Medium", 5, 1),
            )
            conn.execute(
                "INSERT INTO templates (name, level_adjustment) VALUES (?, ?)",
                ("Half-Dragon", 3),
            )
            conn.commit()
        finally:
            conn.close()
        return GameDataRepository(db_path)

    def test_class_hit_dice_skips_null(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        assert repo.class_hit_dice() == {"Fighter": 10, "Wizard": 4}

    def test_get_race_profile(self, tmp_path: Path) -> None:
        profile = self._repo(tmp_path).get_race_profile("Lizardfolk")
        assert profile is not None
        assert profile.size == "Medium"
        assert profile.natural_armor == 5
        assert profile.level_adjustment == 1

    def test_get_race_profile_unknown(self, tmp_path: Path) -> None:
        assert self._repo(tmp_path).get_race_profile("Nobody") is None

    def test_template_level_adjustment(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        assert repo.template_level_adjustment("Half-Dragon") == 3
        assert repo.template_level_adjustment("Unknown") == 0
