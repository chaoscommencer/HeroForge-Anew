"""Source-of-truth game data schema for HeroForge-Anew.

This module defines :data:`GAME_SCHEMA_SQL`, the read-only, ROM-equivalent game
data tables (races, classes, feats, spells, …).  It is applied to
``heroforge.db`` by :func:`heroforge.db.schema.initialize_database` and is only
ever rewritten when the original Excel workbook is re-imported.  It deliberately
contains **no** ``character_*`` save tables; those live in
:mod:`heroforge.db.character_schema` and are written to standalone ``.hfc``
save files.

Keeping the game schema in its own module enforces a clean separation of
concerns between the application's immutable source data and the user's
volatile character data.
"""

from __future__ import annotations

import re

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

CREATE TABLE IF NOT EXISTS psionic_progression (
    id                  INTEGER PRIMARY KEY,
    class_name          TEXT NOT NULL,
    key_ability         TEXT NOT NULL,
    manifester_level    INTEGER NOT NULL,
    power_points        INTEGER NOT NULL,
    powers_known        INTEGER NOT NULL DEFAULT 0,
    UNIQUE(class_name, manifester_level)
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

CREATE TABLE IF NOT EXISTS weapon_damage (
    id              INTEGER PRIMARY KEY,
    step_code       INTEGER NOT NULL,
    size            TEXT NOT NULL,
    damage          TEXT NOT NULL,
    UNIQUE(step_code, size)
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

CREATE TABLE IF NOT EXISTS buffs (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT,
    spell_level INTEGER,
    bonus_type  TEXT,
    description TEXT,
    source      TEXT,
    UNIQUE(name, category)
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
    natural_armor INTEGER,
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

CREATE TABLE IF NOT EXISTS familiar_bonuses (
    id              INTEGER PRIMARY KEY,
    creature_name   TEXT UNIQUE NOT NULL,
    value           INTEGER NOT NULL,
    bonus_kind      TEXT NOT NULL,
    target          TEXT NOT NULL DEFAULT '',
    condition       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS familiar_master_abilities (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    description     TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS companion_progression (
    id                  INTEGER PRIMARY KEY,
    min_level           INTEGER NOT NULL,
    max_level           INTEGER NOT NULL,
    bonus_hd            INTEGER NOT NULL,
    natural_armor       INTEGER NOT NULL,
    ability_adjustment  INTEGER NOT NULL,
    bonus_tricks        INTEGER NOT NULL,
    special             TEXT NOT NULL DEFAULT '',
    sort_order          INTEGER NOT NULL DEFAULT 0,
    UNIQUE(min_level, max_level)
);

CREATE TABLE IF NOT EXISTS companion_progression_labels (
    id          INTEGER PRIMARY KEY,
    field_key   TEXT UNIQUE NOT NULL,
    label       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
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
CREATE INDEX IF NOT EXISTS idx_buffs_name     ON buffs(name);
CREATE INDEX IF NOT EXISTS idx_psionic_progression_class
    ON psionic_progression(class_name);
"""

# Derived at import time so the table/index sets always stay in sync with the
# DDL above.
GAME_TABLES: frozenset[str] = frozenset(
    re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", GAME_SCHEMA_SQL)
)
GAME_INDEXES: frozenset[str] = frozenset(
    re.findall(r"CREATE INDEX IF NOT EXISTS\s+(\w+)", GAME_SCHEMA_SQL)
)
