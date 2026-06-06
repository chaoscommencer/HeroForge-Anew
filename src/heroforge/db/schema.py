"""SQLite schema definitions for HeroForge-Anew.

All game data and character save tables are defined here.
Call initialize_database() to create a fresh database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# DDL – complete schema
# ---------------------------------------------------------------------------

SCHEMA_SQL: str = """
-- ============================================================
-- Core game data tables
-- ============================================================

CREATE TABLE IF NOT EXISTS races (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    size                TEXT,
    type                TEXT,
    subtype             TEXT,
    base_land_speed     INTEGER,
    base_fly_speed      INTEGER,
    base_swim_speed     INTEGER,
    base_climb_speed    INTEGER,
    base_burrow_speed   INTEGER,
    darkvision          INTEGER DEFAULT 0,
    low_light_vision    INTEGER DEFAULT 0,
    natural_armor       INTEGER DEFAULT 0,
    str_adj             INTEGER DEFAULT 0,
    dex_adj             INTEGER DEFAULT 0,
    con_adj             INTEGER DEFAULT 0,
    int_adj             INTEGER DEFAULT 0,
    wis_adj             INTEGER DEFAULT 0,
    cha_adj             INTEGER DEFAULT 0,
    level_adjustment    INTEGER DEFAULT 0,
    favored_class       TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    cr_adjustment       REAL DEFAULT 0,
    level_adjustment    INTEGER DEFAULT 0,
    type_change         TEXT,
    subtype_added       TEXT,
    str_adj             INTEGER DEFAULT 0,
    dex_adj             INTEGER DEFAULT 0,
    con_adj             INTEGER DEFAULT 0,
    int_adj             INTEGER DEFAULT 0,
    wis_adj             INTEGER DEFAULT 0,
    cha_adj             INTEGER DEFAULT 0,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS classes (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT UNIQUE NOT NULL,
    is_prestige             INTEGER DEFAULT 0,
    hit_die                 INTEGER,
    bab_progression         TEXT,
    fort_progression        TEXT,
    ref_progression         TEXT,
    will_progression        TEXT,
    skill_points_per_level  INTEGER,
    source                  TEXT
);

CREATE TABLE IF NOT EXISTS class_skills (
    id          INTEGER PRIMARY KEY,
    class_name  TEXT NOT NULL,
    skill_name  TEXT NOT NULL,
    UNIQUE(class_name, skill_name)
);

CREATE TABLE IF NOT EXISTS class_abilities (
    id              INTEGER PRIMARY KEY,
    class_name      TEXT NOT NULL,
    level           INTEGER NOT NULL,
    ability_name    TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS class_weapons_armor (
    id              INTEGER PRIMARY KEY,
    class_name      TEXT NOT NULL,
    proficiency     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prestige_class_prerequisites (
    id          INTEGER PRIMARY KEY,
    class_name  TEXT NOT NULL,
    prerequisite TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feats (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    type        TEXT,
    description TEXT,
    benefit     TEXT,
    special     TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS feat_prerequisites (
    id          INTEGER PRIMARY KEY,
    feat_name   TEXT NOT NULL,
    prerequisite TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    key_ability         TEXT NOT NULL,
    trained_only        INTEGER DEFAULT 0,
    armor_check_penalty INTEGER DEFAULT 0,
    description         TEXT
);

CREATE TABLE IF NOT EXISTS skill_synergies (
    id          INTEGER PRIMARY KEY,
    from_skill  TEXT NOT NULL,
    to_skill    TEXT NOT NULL,
    bonus       INTEGER DEFAULT 2,
    condition   TEXT
);

CREATE TABLE IF NOT EXISTS skill_tricks (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    cost            INTEGER DEFAULT 2,
    description     TEXT,
    prerequisite    TEXT
);

CREATE TABLE IF NOT EXISTS spells (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    school          TEXT,
    subschool       TEXT,
    descriptor      TEXT,
    components      TEXT,
    casting_time    TEXT,
    range           TEXT,
    target          TEXT,
    duration        TEXT,
    saving_throw    TEXT,
    spell_resistance TEXT,
    description     TEXT,
    source          TEXT
);

CREATE TABLE IF NOT EXISTS spells_per_day (
    id              INTEGER PRIMARY KEY,
    class_name      TEXT NOT NULL,
    caster_level    INTEGER NOT NULL,
    spell_level     INTEGER NOT NULL,
    slots           INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS spells_known (
    id              INTEGER PRIMARY KEY,
    class_name      TEXT NOT NULL,
    caster_level    INTEGER NOT NULL,
    spell_level     INTEGER NOT NULL,
    count           INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS psionic_powers (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    discipline          TEXT,
    subdiscipline       TEXT,
    descriptor          TEXT,
    power_points        INTEGER,
    manifester_level_min INTEGER,
    description         TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS soulmelds (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    descriptors         TEXT,
    chakra              TEXT,
    essentia_capacity   INTEGER DEFAULT 3,
    bind_dc             INTEGER,
    description         TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS soulmeld_abilities (
    id              INTEGER PRIMARY KEY,
    soulmeld_name   TEXT NOT NULL,
    chakra          TEXT NOT NULL,
    essentia        INTEGER DEFAULT 0,
    description     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incarnum_abilities (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    class_name  TEXT,
    feat_name   TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS variants (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    base_class  TEXT NOT NULL,
    description TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS vestiges (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    level               INTEGER,
    sign                TEXT,
    influence           TEXT,
    granted_abilities   TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS marshal_auras (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT,
    bonus_type  TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS deities (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    alignment       TEXT,
    domains         TEXT,
    favored_weapon  TEXT,
    source          TEXT
);

CREATE TABLE IF NOT EXISTS domains (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    granted_power   TEXT,
    spell_1         TEXT,
    spell_2         TEXT,
    spell_3         TEXT,
    spell_4         TEXT,
    spell_5         TEXT,
    spell_6         TEXT,
    spell_7         TEXT,
    spell_8         TEXT,
    spell_9         TEXT
);

CREATE TABLE IF NOT EXISTS grafts (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT,
    body_slot   TEXT,
    description TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS racial_abilities (
    id              INTEGER PRIMARY KEY,
    race_name       TEXT NOT NULL,
    ability_name    TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS graft_abilities (
    id              INTEGER PRIMARY KEY,
    graft_name      TEXT NOT NULL,
    ability_name    TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS maneuvers (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    discipline          TEXT,
    level               INTEGER,
    type                TEXT,
    initiation_action   TEXT,
    range               TEXT,
    target              TEXT,
    duration            TEXT,
    description         TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS weapons (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    category        TEXT,
    size            TEXT,
    damage_small    TEXT,
    damage_medium   TEXT,
    critical        TEXT,
    range_increment INTEGER DEFAULT 0,
    weight          REAL DEFAULT 0,
    damage_type     TEXT,
    source          TEXT
);

CREATE TABLE IF NOT EXISTS armor (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT UNIQUE NOT NULL,
    type                    TEXT,
    ac_bonus                INTEGER,
    max_dex_bonus           INTEGER,
    check_penalty           INTEGER,
    arcane_spell_failure    INTEGER,
    speed_30                INTEGER,
    speed_20                INTEGER,
    weight                  REAL,
    source                  TEXT
);

CREATE TABLE IF NOT EXISTS magic_enhancements (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    type                TEXT,
    bonus_equivalent    INTEGER,
    description         TEXT,
    source              TEXT
);

CREATE TABLE IF NOT EXISTS magic_equipment (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    slot        TEXT,
    caster_level INTEGER,
    aura        TEXT,
    price_gp    INTEGER,
    weight      REAL,
    description TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS creatures (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    size        TEXT,
    type        TEXT,
    subtype     TEXT,
    hit_dice    TEXT,
    str_score   INTEGER,
    dex_score   INTEGER,
    con_score   INTEGER,
    int_score   INTEGER,
    wis_score   INTEGER,
    cha_score   INTEGER,
    bab         TEXT,
    grapple_mod INTEGER,
    armor_class INTEGER,
    speed       TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS tables (
    id          INTEGER PRIMARY KEY,
    table_name  TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    UNIQUE(table_name, key)
);

CREATE TABLE IF NOT EXISTS languages (
    id                  INTEGER PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    typical_speakers    TEXT,
    script              TEXT
);

CREATE TABLE IF NOT EXISTS traits (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    benefit     TEXT,
    drawback    TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS flaws (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    effect      TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY,
    abbreviation    TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL
);

-- ============================================================
-- Character save tables
-- ============================================================

CREATE TABLE IF NOT EXISTS characters (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    player      TEXT,
    campaign    TEXT,
    alignment   TEXT,
    deity       TEXT,
    homeland    TEXT,
    race        TEXT,
    templates   TEXT,
    gender      TEXT,
    age         INTEGER,
    height      TEXT,
    weight      TEXT,
    eyes        TEXT,
    hair        TEXT,
    skin        TEXT,
    experience  INTEGER DEFAULT 0,
    notes       TEXT,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS character_ability_scores (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    ability         TEXT NOT NULL,
    base_score      INTEGER NOT NULL,
    UNIQUE(character_id, ability)
);

CREATE TABLE IF NOT EXISTS character_classes (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    class_name      TEXT NOT NULL,
    level           INTEGER NOT NULL,
    order_taken     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS character_feats (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    feat_name       TEXT NOT NULL,
    order_taken     INTEGER NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS character_skills (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    skill_name      TEXT NOT NULL,
    ranks           REAL NOT NULL DEFAULT 0,
    UNIQUE(character_id, skill_name)
);

CREATE TABLE IF NOT EXISTS character_spells_prepared (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    class_name      TEXT NOT NULL,
    spell_level     INTEGER NOT NULL,
    spell_name      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_spells_known (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    class_name      TEXT NOT NULL,
    spell_level     INTEGER NOT NULL,
    spell_name      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_soulmelds (
    id                  INTEGER PRIMARY KEY,
    character_id        INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    soulmeld_name       TEXT NOT NULL,
    chakra_bound        TEXT,
    essentia_invested   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS character_equipment (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_name       TEXT NOT NULL,
    quantity        INTEGER DEFAULT 1,
    weight          REAL DEFAULT 0,
    equipped        INTEGER DEFAULT 0,
    slot            TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS character_buffs (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    buff_name       TEXT NOT NULL,
    active          INTEGER DEFAULT 1,
    parameters      TEXT
);

CREATE TABLE IF NOT EXISTS character_languages (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    language        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_traits (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    trait_name      TEXT NOT NULL,
    is_flaw         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS character_maneuvers (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    maneuver_name   TEXT NOT NULL,
    readied         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS character_notes (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    timestamp       TEXT NOT NULL,
    content         TEXT NOT NULL
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_races_name     ON races(name);
CREATE INDEX IF NOT EXISTS idx_classes_name   ON classes(name);
CREATE INDEX IF NOT EXISTS idx_feats_name     ON feats(name);
CREATE INDEX IF NOT EXISTS idx_skills_name    ON skills(name);
CREATE INDEX IF NOT EXISTS idx_spells_name    ON spells(name);
CREATE INDEX IF NOT EXISTS idx_spells_class   ON spells(name);
CREATE INDEX IF NOT EXISTS idx_weapons_name   ON weapons(name);
CREATE INDEX IF NOT EXISTS idx_creatures_name ON creatures(name);
CREATE INDEX IF NOT EXISTS idx_soulmelds_name ON soulmelds(name);
"""


def get_connection(db_path: str | Path = "heroforge.db") -> sqlite3.Connection:
    """Return a SQLite connection with foreign keys enabled and row_factory set.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str | Path = "heroforge.db") -> sqlite3.Connection:
    """Create the database file (if absent) and apply the full schema.

    If the database file already exists and already contains at least one
    user table, this function returns the open connection without applying
    the schema script again.

    Args:
        db_path: Path where the SQLite file will be created/opened.

    Returns:
        An open :class:`sqlite3.Connection` to the initialised database.
    """
    db_path = Path(db_path)
    db_exists = db_path.exists()
    conn = get_connection(db_path)

    if db_exists:
        user_table_row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
        if user_table_row is not None:
            return conn

    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
