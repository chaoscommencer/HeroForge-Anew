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
            "INSERT INTO psionic_progression "
            "(class_name, key_ability, manifester_level, power_points) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Psion", "INT", 0, 0),
                ("Psion", "INT", 1, 2),
                ("Psion", "INT", 2, 6),
                ("Wilder", "CHA", 0, 0),
                ("Wilder", "CHA", 1, 2),
            ],
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
        conn.executemany(
            "INSERT INTO graft_abilities (graft_name, ability_name, description) "
            "VALUES (?, ?, ?)",
            [
                (
                    "Fiendish Arm",
                    "Claw Attack",
                    "Grants a primary claw attack dealing 1d6 damage.",
                ),
                (
                    "Fiendish Arm",
                    "Strength Boost",
                    "+2 enhancement bonus to Strength.",
                ),
                (
                    "Fiendish Eye",
                    "Darkvision",
                    "Grants darkvision out to 60 feet.",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO classes (name, is_prestige, hit_die, bab_progression, "
            "fort_progression, ref_progression, will_progression, "
            "skill_points_per_level, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Fighter", 0, 10, "fast", "good", "poor", "poor", 2, "PHB"),
                ("Wizard", 0, 4, "slow", "poor", "poor", "good", 2, "PHB"),
                ("Arcane Archer", 1, 8, "fast", "poor", "good", "poor", 4, "DMG"),
            ],
        )
        conn.executemany(
            "INSERT INTO class_skills (class_name, skill_name) VALUES (?, ?)",
            [
                ("Fighter", "Intimidate"),
                ("Fighter", "Climb"),
                ("Wizard", "Spellcraft"),
            ],
        )
        conn.executemany(
            "INSERT INTO class_weapons_armor (class_name, proficiency) VALUES (?, ?)",
            [
                ("Fighter", "All simple weapons"),
                ("Fighter", "All martial weapons"),
                ("Fighter", "Heavy armor"),
            ],
        )
        conn.executemany(
            "INSERT INTO class_abilities (class_name, level, ability_name, "
            "description) VALUES (?, ?, ?, ?)",
            [
                ("Fighter", 1, "Bonus Feat", "A fighter gains a bonus feat."),
                ("Fighter", 2, "Bonus Feat", "A fighter gains a bonus feat."),
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


class TestPsionicProgressions:
    def test_builds_manifester_info_per_class(
        self, seeded_repo: GameDataRepository
    ) -> None:
        progressions = seeded_repo.psionic_progressions()
        assert set(progressions) == {"Psion", "Wilder"}
        assert progressions["Psion"].key_ability == "INT"
        assert progressions["Wilder"].key_ability == "CHA"

    def test_pp_per_day_indexed_by_manifester_level(
        self, seeded_repo: GameDataRepository
    ) -> None:
        psion = seeded_repo.psionic_progressions()["Psion"]
        # Levels 0-2 seeded as 0/2/6, indexed positionally.
        assert psion.pp_per_day == (0, 2, 6)

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.psionic_progressions() == {}


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


class TestGraftAbilities:
    def test_list_all(self, seeded_repo: GameDataRepository) -> None:
        abilities = seeded_repo.list_graft_abilities()
        assert len(abilities) == 3

    def test_filter_by_graft(self, seeded_repo: GameDataRepository) -> None:
        arm = seeded_repo.list_graft_abilities(graft_name="Fiendish Arm")
        assert {a.ability_name for a in arm} == {"Claw Attack", "Strength Boost"}

    def test_description_present(self, seeded_repo: GameDataRepository) -> None:
        eye = seeded_repo.list_graft_abilities(graft_name="Fiendish Eye")
        assert len(eye) == 1
        assert "darkvision" in eye[0].description.lower()

    def test_unknown_graft_returns_empty(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.list_graft_abilities(graft_name="Aboleth Gland") == []

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_graft_abilities() == []


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


@pytest.fixture()
def race_template_repo(tmp_path: Path) -> GameDataRepository:
    """A repository seeded with rich race/template/variant rows."""
    db_path = tmp_path / "rt.db"
    conn = initialize_database(db_path)
    try:
        conn.execute(
            "INSERT INTO races (name, size, type, base_land_speed, dex_adj, "
            "con_adj, level_adjustment, source) "
            "VALUES ('Elf', 'Medium', 'Humanoid', 30, 2, -2, 0, 'PHB')"
        )
        conn.execute(
            "INSERT INTO templates (name, str_adj, con_adj, int_adj, cha_adj, "
            "level_adjustment, type_change, source) "
            "VALUES ('Half-Dragon', 8, 2, 2, 2, 3, 'Dragon', 'MM')"
        )
        conn.executemany(
            "INSERT INTO variants (name, base_class, description, source) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Aquatic Elf", "Elf", "An aquatic subrace.", "MM"),
                ("Wood Elf", "Elf", "A forest subrace.", "UA"),
                ("Whirling Frenzy", "Barbarian", "A rage variant.", "UA"),
            ],
        )
        conn.execute(
            "INSERT INTO racial_abilities (race_name, ability_name, description) "
            "VALUES ('Elf', 'Low-Light Vision', 'See in dim light.')"
        )
        conn.commit()
    finally:
        conn.close()
    return GameDataRepository(db_path)


class TestGetRaceTemplate:
    def test_get_race_returns_full_row(
        self, race_template_repo: GameDataRepository
    ) -> None:
        race = race_template_repo.get_race("Elf")
        assert race is not None
        assert race.name == "Elf"
        assert race.size == "Medium"
        assert race.dex_adj == 2
        assert race.con_adj == -2
        assert race.level_adjustment == 0
        assert race.base_land_speed == 30
        assert race.abilities == ["Low-Light Vision"]

    def test_get_race_unknown_returns_none(
        self, race_template_repo: GameDataRepository
    ) -> None:
        assert race_template_repo.get_race("Nonexistent") is None

    def test_get_template_returns_full_row(
        self, race_template_repo: GameDataRepository
    ) -> None:
        template = race_template_repo.get_template("Half-Dragon")
        assert template is not None
        assert template.str_adj == 8
        assert template.con_adj == 2
        assert template.level_adjustment == 3
        assert template.type_change == "Dragon"

    def test_get_template_case_insensitive(
        self, race_template_repo: GameDataRepository
    ) -> None:
        template = race_template_repo.get_template("half-dragon")
        assert template is not None
        assert template.name == "Half-Dragon"

    def test_get_template_unknown_returns_none(
        self, race_template_repo: GameDataRepository
    ) -> None:
        assert race_template_repo.get_template("Nope") is None

    def test_get_templates_preserves_order_and_skips_unknown(
        self, race_template_repo: GameDataRepository
    ) -> None:
        templates = race_template_repo.get_templates(["Half-Dragon", "Ghost"])
        assert [t.name for t in templates] == ["Half-Dragon"]

    def test_get_templates_case_insensitive_and_preserves_duplicates(
        self, race_template_repo: GameDataRepository
    ) -> None:
        templates = race_template_repo.get_templates(
            ["half-dragon", "GHOST", "HALF-DRAGON"]
        )
        assert [t.name for t in templates] == ["Half-Dragon", "Half-Dragon"]

    def test_list_race_variants(self, race_template_repo: GameDataRepository) -> None:
        variants = race_template_repo.list_race_variants("Elf")
        assert [v.name for v in variants] == ["Aquatic Elf", "Wood Elf"]

    def test_list_race_variants_case_insensitive(
        self, race_template_repo: GameDataRepository
    ) -> None:
        assert [v.name for v in race_template_repo.list_race_variants("elf")] == [
            "Aquatic Elf",
            "Wood Elf",
        ]

    def test_list_race_variants_none_for_unknown(
        self, race_template_repo: GameDataRepository
    ) -> None:
        assert race_template_repo.list_race_variants("Human") == []


class TestClasses:
    def test_list_classes_base_only(self, seeded_repo: GameDataRepository) -> None:
        names = [c.name for c in seeded_repo.list_classes()]
        # Prestige classes are excluded by default.
        assert names == ["Fighter", "Wizard"]

    def test_list_classes_include_prestige(
        self, seeded_repo: GameDataRepository
    ) -> None:
        names = [c.name for c in seeded_repo.list_classes(include_prestige=True)]
        assert names == ["Arcane Archer", "Fighter", "Wizard"]

    def test_list_classes_fields(self, seeded_repo: GameDataRepository) -> None:
        fighter = next(c for c in seeded_repo.list_classes() if c.name == "Fighter")
        assert fighter.is_prestige is False
        assert fighter.hit_die == 10
        assert fighter.bab_progression == "fast"
        assert fighter.fort_progression == "good"
        assert fighter.skill_points_per_level == 2
        assert fighter.source == "PHB"

    def test_list_classes_source_filter(self, seeded_repo: GameDataRepository) -> None:
        # Filtering to PHB keeps the PHB base classes and drops the DMG one.
        names = [
            c.name
            for c in seeded_repo.list_classes(sources=["PHB"], include_prestige=True)
        ]
        assert names == ["Fighter", "Wizard"]

    def test_class_skills(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.class_skills("Fighter") == ["Climb", "Intimidate"]
        assert seeded_repo.class_skills("Wizard") == ["Spellcraft"]

    def test_class_proficiencies(self, seeded_repo: GameDataRepository) -> None:
        profs = seeded_repo.class_proficiencies("Fighter")
        assert profs == [
            "All simple weapons",
            "All martial weapons",
            "Heavy armor",
        ]

    def test_class_abilities(self, seeded_repo: GameDataRepository) -> None:
        abilities = seeded_repo.class_abilities("Fighter")
        assert [(a.level, a.ability_name) for a in abilities] == [
            (1, "Bonus Feat"),
            (2, "Bonus Feat"),
        ]
        assert abilities[0].description == "A fighter gains a bonus feat."

    def test_unknown_class_returns_empty(self, seeded_repo: GameDataRepository) -> None:
        assert seeded_repo.class_skills("Bard") == []
        assert seeded_repo.class_proficiencies("Bard") == []
        assert seeded_repo.class_abilities("Bard") == []

    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_classes() == []


class TestSpellMethods:
    """Tests for list_spell_names, list_domains, get_domain, list_deities."""

    @pytest.fixture()
    def spell_repo(self, tmp_path: Path) -> GameDataRepository:
        """A repository with hand-seeded domain, deity, and spell data."""
        db_path = tmp_path / "spells.db"
        conn = initialize_database(db_path)
        try:
            conn.executemany(
                "INSERT INTO spells (name, school) VALUES (?, ?)",
                [
                    ("Fireball", "Evocation"),
                    ("Cure Light Wounds", "Conjuration"),
                    ("Magic Missile", "Evocation"),
                ],
            )
            conn.executemany(
                "INSERT INTO domains "
                "(name, granted_power, spell_1, spell_2, spell_3, spell_4, spell_5,"
                " spell_6, spell_7, spell_8, spell_9) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "Fire",
                        "Turn or destroy water creatures as a good cleric turns undead.",
                        "Burning Hands",
                        "Produce Flame",
                        "Resist Energy",
                        "Wall of Fire",
                        "Fire Shield",
                        "Fire Seeds",
                        "Fire Storm",
                        "Incendiary Cloud",
                        "Elemental Swarm",
                    ),
                    (
                        "Air",
                        "Turn or destroy earth creatures.",
                        "Obscuring Mist",
                        "Wind Wall",
                        "Gaseous Form",
                        "Air Walk",
                        "Control Winds",
                        "Chain Lightning",
                        "Control Weather",
                        "Whirlwind",
                        "Elemental Swarm",
                    ),
                ],
            )
            conn.executemany(
                "INSERT INTO deities (name, alignment, domains, favored_weapon) "
                "VALUES (?, ?, ?, ?)",
                [
                    ("Pelor", "NG", "Good,Healing,Strength,Sun", "Heavy Mace"),
                    ("Nerull", "NE", "Death,Evil,Trickery", "Scythe"),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        return GameDataRepository(db_path)

    def test_list_spell_names(self, spell_repo: GameDataRepository) -> None:
        names = spell_repo.list_spell_names()
        assert names == ["Cure Light Wounds", "Fireball", "Magic Missile"]

    def test_list_spell_names_empty(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty2.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_spell_names() == []

    def test_list_domains_returns_all(self, spell_repo: GameDataRepository) -> None:
        domains = spell_repo.list_domains()
        assert len(domains) == 2
        names = [d.name for d in domains]
        assert "Air" in names
        assert "Fire" in names

    def test_domain_spells_length(self, spell_repo: GameDataRepository) -> None:
        domains = {d.name: d for d in spell_repo.list_domains()}
        fire = domains["Fire"]
        assert isinstance(fire.domain_spells, tuple)
        assert len(fire.domain_spells) == 9
        assert fire.domain_spells[0] == "Burning Hands"
        assert fire.domain_spells[8] == "Elemental Swarm"

    def test_domain_granted_power(self, spell_repo: GameDataRepository) -> None:
        domains = {d.name: d for d in spell_repo.list_domains()}
        fire = domains["Fire"]
        assert "water creatures" in fire.granted_power

    def test_get_domain_found(self, spell_repo: GameDataRepository) -> None:
        domain = spell_repo.get_domain("Fire")
        assert domain is not None
        assert domain.name == "Fire"
        assert isinstance(domain.domain_spells, tuple)
        assert domain.domain_spells[0] == "Burning Hands"

    def test_get_domain_case_insensitive(self, spell_repo: GameDataRepository) -> None:
        domain = spell_repo.get_domain("fire")
        assert domain is not None
        assert domain.name == "Fire"

    def test_get_domain_not_found(self, spell_repo: GameDataRepository) -> None:
        assert spell_repo.get_domain("Nonexistent") is None

    def test_list_deities(self, spell_repo: GameDataRepository) -> None:
        names = spell_repo.list_deities()
        assert names == ["Nerull", "Pelor"]

    def test_list_deities_empty(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty3.db"
        conn = initialize_database(db_path)
        conn.close()
        repo = GameDataRepository(db_path)
        assert repo.list_deities() == []


class TestSpellcastingClassData:
    """Tests for get_spellcasting_abilities() and get_caster_types().

    Reference: PHB Chapter 3 class descriptions; supplement class entries.
    Spellcasting ability and caster type are stored in the ``classes`` table
    (seeded by seed_class_spellcasting_info) rather than hard-coded in Python.
    """

    @pytest.fixture()
    def spellcasting_repo(self, tmp_path: Path) -> GameDataRepository:
        """A repository seeded with a handful of spellcasting classes."""
        db_path = tmp_path / "spellcasting.db"
        conn = initialize_database(db_path)
        try:
            conn.executemany(
                "INSERT INTO classes "
                "(name, hit_die, bab_progression, fort_progression, "
                "ref_progression, will_progression, skill_points_per_level, "
                "spellcasting_ability, caster_type, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "Wizard",
                        4,
                        "slow",
                        "poor",
                        "poor",
                        "good",
                        2,
                        "INT",
                        "full",
                        "PHB",
                    ),
                    (
                        "Cleric",
                        8,
                        "medium",
                        "good",
                        "poor",
                        "good",
                        2,
                        "WIS",
                        "full",
                        "PHB",
                    ),
                    (
                        "Sorcerer",
                        4,
                        "slow",
                        "poor",
                        "poor",
                        "good",
                        2,
                        "CHA",
                        "full",
                        "PHB",
                    ),
                    (
                        "Bard",
                        6,
                        "medium",
                        "poor",
                        "good",
                        "good",
                        6,
                        "CHA",
                        "three_quarter",
                        "PHB",
                    ),
                    (
                        "Paladin",
                        10,
                        "fast",
                        "good",
                        "poor",
                        "poor",
                        2,
                        "WIS",
                        "half",
                        "PHB",
                    ),
                    (
                        "Ranger",
                        8,
                        "fast",
                        "good",
                        "good",
                        "poor",
                        6,
                        "WIS",
                        "half",
                        "PHB",
                    ),
                    (
                        "Fighter",
                        10,
                        "fast",
                        "good",
                        "poor",
                        "poor",
                        2,
                        None,
                        None,
                        "PHB",
                    ),
                    (
                        "Barbarian",
                        12,
                        "fast",
                        "good",
                        "poor",
                        "poor",
                        4,
                        None,
                        None,
                        "PHB",
                    ),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        return GameDataRepository(db_path)

    def test_spellcasting_abilities_core_casters(
        self, spellcasting_repo: GameDataRepository
    ) -> None:
        abilities = spellcasting_repo.get_spellcasting_abilities()
        assert abilities["Wizard"] == "INT"
        assert abilities["Cleric"] == "WIS"
        assert abilities["Sorcerer"] == "CHA"
        assert abilities["Bard"] == "CHA"
        assert abilities["Paladin"] == "WIS"
        assert abilities["Ranger"] == "WIS"

    def test_non_casters_absent_from_spellcasting_abilities(
        self, spellcasting_repo: GameDataRepository
    ) -> None:
        abilities = spellcasting_repo.get_spellcasting_abilities()
        assert "Fighter" not in abilities
        assert "Barbarian" not in abilities

    def test_caster_types_full(self, spellcasting_repo: GameDataRepository) -> None:
        caster_types = spellcasting_repo.get_caster_types()
        assert caster_types["Wizard"] == "full"
        assert caster_types["Cleric"] == "full"
        assert caster_types["Sorcerer"] == "full"

    def test_caster_types_three_quarter(
        self, spellcasting_repo: GameDataRepository
    ) -> None:
        caster_types = spellcasting_repo.get_caster_types()
        assert caster_types["Bard"] == "three_quarter"

    def test_caster_types_half(self, spellcasting_repo: GameDataRepository) -> None:
        caster_types = spellcasting_repo.get_caster_types()
        assert caster_types["Paladin"] == "half"
        assert caster_types["Ranger"] == "half"

    def test_non_casters_absent_from_caster_types(
        self, spellcasting_repo: GameDataRepository
    ) -> None:
        caster_types = spellcasting_repo.get_caster_types()
        assert "Fighter" not in caster_types
        assert "Barbarian" not in caster_types

    def test_spellcasting_abilities_empty_when_no_db(self, tmp_path: Path) -> None:
        repo = GameDataRepository(tmp_path / "missing.db")
        assert repo.get_spellcasting_abilities() == {}

    def test_caster_types_empty_when_no_db(self, tmp_path: Path) -> None:
        repo = GameDataRepository(tmp_path / "missing.db")
        assert repo.get_caster_types() == {}
