"""Per-character save schema for HeroForge-Anew.

This module defines :data:`CHARACTER_SCHEMA_SQL`, the volatile, user-owned
``character_*`` save tables.  It is applied to standalone ``.hfc`` save files by
:func:`heroforge.db.schema.initialize_character_database`.  Think of these files
as RAM: each one holds a single user's character and never touches the
source-of-truth game database (see :mod:`heroforge.db.game_schema`).

Every per-character selectable feature and choice surfaced by the original Excel
workbook has an equivalent table here so that character state round-trips
without loss:

* core fields (``characters``), ability scores, class levels, feats, skills;
* spells known/prepared and psionic powers known;
* incarnum soulmelds, martial maneuvers/stances, and binder vestiges;
* cleric domains, marshal auras, class/racial variants, and skill tricks;
* equipment, buffs, languages, grafts, traits/flaws;
* animal companions/familiars and timestamped game-log notes.

Keeping the character schema in its own module enforces a clean separation of
concerns between the user's volatile character data and the application's
immutable source data.
"""

from __future__ import annotations

import re

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

CREATE TABLE IF NOT EXISTS character_variants (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    variant_name    TEXT NOT NULL,
    class_name      TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS character_domains (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    domain_name     TEXT NOT NULL,
    slot            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS character_vestiges (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    vestige_name    TEXT NOT NULL,
    level           INTEGER DEFAULT 0,
    bound           INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS character_marshal_auras (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    aura_name       TEXT NOT NULL,
    aura_type       TEXT,
    active          INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS character_skill_tricks (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    trick_name      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_psionic_powers (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    class_name      TEXT NOT NULL,
    power_level     INTEGER NOT NULL DEFAULT 0,
    power_name      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_companions (
    id              INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    companion_type  TEXT NOT NULL,
    name            TEXT,
    creature        TEXT,
    notes           TEXT
);
"""

# Derived at import time so the table set always stays in sync with the DDL.
CHARACTER_TABLES: frozenset[str] = frozenset(
    re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", CHARACTER_SCHEMA_SQL)
)
