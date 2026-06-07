"""SQLite schema definitions for HeroForge-Anew.

The schema is split into two independent halves so that read-only game data
and volatile, user-owned character data never share a database file:

* :data:`GAME_SCHEMA_SQL` defines the source-of-truth game data tables.  It is
  applied to ``heroforge.db`` by :func:`initialize_database`.  Think of this
  database as ROM: it is only ever rewritten when the original Excel workbook
  is re-imported.
* :data:`CHARACTER_SCHEMA_SQL` defines the per-character save tables.  It is
  applied to a standalone ``.hfc`` save file by
  :func:`initialize_character_database`.  Think of these files as RAM: each one
  holds a single user's volatile character data.

Keeping the two apart protects the application's source data from being
mutated by ordinary character edits.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# DDL – game data schema (source of truth; heroforge.db)
# ---------------------------------------------------------------------------

GAME_SCHEMA_SQL: str = """
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

CREATE TABLE IF NOT EXISTS skill_footnotes (
    id              INTEGER PRIMARY KEY,
    skill_name      TEXT NOT NULL,
    raw_name        TEXT NOT NULL,
    marker          TEXT NOT NULL,
    UNIQUE(skill_name, marker)
);

CREATE TABLE IF NOT EXISTS skill_footnote_definitions (
    id              INTEGER PRIMARY KEY,
    source_sheet    TEXT NOT NULL,
    marker          TEXT NOT NULL,
    description     TEXT NOT NULL,
    UNIQUE(source_sheet, marker)
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
-- Indexes (game data)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_races_name     ON races(name);
CREATE INDEX IF NOT EXISTS idx_classes_name   ON classes(name);
CREATE INDEX IF NOT EXISTS idx_feats_name     ON feats(name);
CREATE INDEX IF NOT EXISTS idx_skills_name    ON skills(name);
CREATE INDEX IF NOT EXISTS idx_spells_name    ON spells(name);
CREATE INDEX IF NOT EXISTS idx_weapons_name   ON weapons(name);
CREATE INDEX IF NOT EXISTS idx_creatures_name ON creatures(name);
CREATE INDEX IF NOT EXISTS idx_soulmelds_name ON soulmelds(name);
"""

# ---------------------------------------------------------------------------
# DDL – character save schema (volatile, per-character .hfc files)
# ---------------------------------------------------------------------------
#
# Character/runtime data is intentionally NOT part of the source-of-truth game
# database.  It lives only in separate per-character ``.hfc`` save files so the
# read-only game data and the user's volatile character data stay cleanly
# separated.

CHARACTER_SCHEMA_SQL: str = """
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

CREATE TABLE IF NOT EXISTS character_grafts (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    graft_name      TEXT NOT NULL,
    body_slot       TEXT,
    notes           TEXT
);
"""

# Backwards-compatible alias: ``heroforge.db`` (the source of truth) only ever
# carries the game data schema.
SCHEMA_SQL: str = GAME_SCHEMA_SQL

# Derived at module load time so the table/index sets always stay in sync with
# the DDL above.
_GAME_TABLES: frozenset[str] = frozenset(
    re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", GAME_SCHEMA_SQL)
)
_GAME_INDEXES: frozenset[str] = frozenset(
    re.findall(r"CREATE INDEX IF NOT EXISTS\s+(\w+)", GAME_SCHEMA_SQL)
)
_CHARACTER_TABLES: frozenset[str] = frozenset(
    re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", CHARACTER_SCHEMA_SQL)
)


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


def _apply_schema_if_needed(
    conn: sqlite3.Connection,
    schema_sql: str,
    expected_tables: frozenset[str],
    expected_indexes: frozenset[str],
) -> None:
    """Apply *schema_sql* to *conn* unless every expected object already exists.

    Every ``CREATE`` statement uses ``IF NOT EXISTS`` so existing tables and
    their data are never affected.
    """
    existing_tables: frozenset[str] = frozenset(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    existing_indexes: frozenset[str] = frozenset(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    if expected_tables.issubset(existing_tables) and expected_indexes.issubset(
        existing_indexes
    ):
        return

    conn.executescript(schema_sql)
    conn.commit()


def initialize_database(db_path: str | Path = "heroforge.db") -> sqlite3.Connection:
    """Create the game database file (if absent) and apply the game schema.

    This is the application's source-of-truth database (``heroforge.db``).  It
    holds **only** game data tables; volatile character data is stored
    separately in ``.hfc`` files (see :func:`initialize_character_database`).

    If the database file already exists and contains all expected game tables,
    this function returns the open connection without re-applying the schema.
    If the file exists but is missing any expected tables (e.g. due to an
    interrupted initialization or corruption), the schema is applied so all
    missing tables are created.  Existing tables and their data are never
    affected because every ``CREATE TABLE`` statement uses ``IF NOT EXISTS``.

    Args:
        db_path: Path where the SQLite file will be created/opened.

    Returns:
        An open :class:`sqlite3.Connection` to the initialised database.
    """
    conn = get_connection(Path(db_path))
    _apply_schema_if_needed(conn, GAME_SCHEMA_SQL, _GAME_TABLES, _GAME_INDEXES)
    return conn


def initialize_character_database(
    db_path: str | Path,
) -> sqlite3.Connection:
    """Create a character save database file (if absent) and apply its schema.

    Character databases (``.hfc`` files) are independent of the source-of-truth
    game database: each one holds a single user's volatile character data and
    carries **only** the ``character_*`` save tables.

    Args:
        db_path: Path where the SQLite save file will be created/opened.

    Returns:
        An open :class:`sqlite3.Connection` to the initialised save database.
    """
    conn = get_connection(Path(db_path))
    _apply_schema_if_needed(conn, CHARACTER_SCHEMA_SQL, _CHARACTER_TABLES, frozenset())
    return conn
