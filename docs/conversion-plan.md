# HeroForge Anew – Excel-to-Python Conversion Plan

This document describes the strategy and step-by-step plan for converting the HeroForge Anew D&D 3.5 character builder from its Excel/VBA implementation (`HeroForge Anew 3.5 v7.4.0.1.xlsm`) to a modern Python application backed by SQLite and a PyQt6 user interface.

---

## Table of Contents

1. [Goals](#1-goals)
2. [Technology Stack](#2-technology-stack)
3. [Repository Layout (Target State)](#3-repository-layout-target-state)
4. [Phase Overview](#4-phase-overview)
5. [Phase 1 – Project Scaffolding](#5-phase-1--project-scaffolding)
6. [Phase 2 – Data Migration](#6-phase-2--data-migration)
7. [Phase 3 – Logic / Macro Conversion](#7-phase-3--logic--macro-conversion)
8. [Phase 4 – UI Implementation](#8-phase-4--ui-implementation)
9. [Phase 5 – Integration & QA](#9-phase-5--integration--qa)
10. [Phase 6 – Packaging & Release](#10-phase-6--packaging--release)
11. [Workbook Sheet Inventory](#11-workbook-sheet-inventory)
12. [VBA Macro / Function Inventory](#12-vba-macro--function-inventory)
13. [Data File Inventory](#13-data-file-inventory)
14. [Risk Register](#14-risk-register)

---

## 1. Goals

| Goal | Description |
|---|---|
| **Feature parity** | Every capability of the Excel workbook must be available in the Python application. |
| **Data integrity** | All game data currently embedded in worksheets or CSV/XLSX files must be migrated without loss. |
| **Maintainability** | New code must be testable, typed, and structured so that adding new source material is straightforward. |
| **Cross-platform** | The application must run on Windows, macOS, and Linux without OS-specific dependencies. |
| **Save compatibility** | Existing `.hfg` save files should be loadable in v8.0+, with migration to a new save format. |

---

## 2. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Modern language features; rich ecosystem |
| GUI framework | PyQt6 | Mature, cross-platform; direct Qt API access |
| Database | SQLite via `sqlite3` stdlib | Zero-dependency, file-based, sufficient for this use case |
| ORM (optional) | SQLAlchemy Core | Cleaner SQL generation; can be added incrementally |
| Data models | `dataclasses` / `pydantic` | Type-safe, self-documenting |
| Testing | pytest + pytest-qt | Unit and widget tests |
| Linting/formatting | Ruff + Black | Fast, opinionated |
| Type checking | mypy (strict) | Catches class of bugs early |
| Build/packaging | pyproject.toml (PEP 517/518) | Standard tooling |
| CI | GitHub Actions | Already in use for the repository |

---

## 3. Repository Layout (Target State)

```
HeroForge-Anew/
├── docs/
│   └── conversion-plan.md        ← this file
├── data/                          ← source data (read-only reference)
│   ├── ClassInfo.xlsx
│   ├── CreatureInfo.csv
│   ├── Tables.csv
│   └── WeaponInfo.csv
├── src/
│   ├── main.py                    ← application entry point
│   └── heroforge/
│       ├── __init__.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.py          ← CREATE TABLE statements / SQLAlchemy metadata
│       │   └── seed.py            ← import data/ and workbook sheets → heroforge.db
│       ├── models/
│       │   ├── __init__.py
│       │   ├── character.py       ← Character dataclass
│       │   ├── race.py
│       │   ├── class_.py
│       │   ├── feat.py
│       │   ├── skill.py
│       │   ├── spell.py
│       │   └── ...
│       ├── logic/
│       │   ├── __init__.py
│       │   ├── ability_scores.py  ← STR/DEX/CON/INT/WIS/CHA modifiers
│       │   ├── combat.py          ← BAB, AC, grapple, initiative
│       │   ├── saving_throws.py   ← Fort/Ref/Will
│       │   ├── skills.py          ← skill ranks, synergies, class-skill bonus
│       │   ├── feats.py           ← prerequisite checking, feat effects
│       │   ├── spells.py          ← spells per day, spells known, caster level
│       │   ├── psionics.py        ← power points, manifester level
│       │   ├── incarnum.py        ← essentia, soulmelds, chakra binds
│       │   ├── wild_shape.py      ← form selection, stat replacement
│       │   ├── buffs.py           ← buff stacking rules
│       │   ├── equipment.py       ← armor, weapons, enhancement bonuses
│       │   ├── prestige.py        ← prestige class prerequisites
│       │   ├── experience.py      ← XP tables, level-up logic
│       │   └── export.py          ← character sheet export (PDF / plain text)
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py     ← QMainWindow + QTabWidget
│           ├── styles/
│           │   └── default.qss    ← application-wide stylesheet
│           ├── dialogs/
│           │   ├── options.py
│           │   ├── source_select.py
│           │   └── template_info.py
│           └── tabs/
│               ├── stats_and_character_details.py
│               ├── race_and_templates.py
│               ├── prestige_classes.py
│               ├── skills.py
│               ├── skill_tricks.py
│               ├── languages.py
│               ├── grafts.py
│               ├── traits_and_flaws.py
│               ├── maneuvers_and_stances.py
│               ├── feats.py
│               ├── armor.py
│               ├── attacks.py
│               ├── enhancements.py
│               ├── magic_equipment.py
│               ├── buffs.py
│               ├── soulmelds.py
│               ├── spells.py
│               ├── psionics.py
│               ├── animal_companion.py
│               ├── familiar.py
│               ├── character_sheet.py  ← read-only summary (replaces CS I–V)
│               ├── game_log.py
│               └── initiative_card.py
├── tests/
│   ├── conftest.py
│   ├── test_ability_scores.py
│   ├── test_combat.py
│   ├── test_saving_throws.py
│   ├── test_skills.py
│   ├── test_feats.py
│   ├── test_spells.py
│   └── ...
├── heroforge.db                   ← generated; in .gitignore
├── pyproject.toml
└── README.md
```

---

## 4. Phase Overview

| Phase | Name | Key Deliverables |
|---|---|---|
| 1 | Project Scaffolding | `pyproject.toml`, package skeleton, CI pipeline |
| 2 | Data Migration | SQLite schema, seed script, all game data imported |
| 3 | Logic Conversion | All VBA macros ported to typed Python functions with tests |
| 4 | UI Implementation | All PyQt6 tabs implemented and wired to logic layer |
| 5 | Integration & QA | End-to-end testing, save/load, regression suite |
| 6 | Packaging & Release | Installers for Windows/macOS/Linux, documentation |

---

## 5. Phase 1 – Project Scaffolding

### 5.1 Tasks

- [ ] Create `pyproject.toml` with `[project]`, `[build-system]`, `[tool.black]`, `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` sections.
- [ ] Create `src/heroforge/__init__.py` and all sub-package `__init__.py` files.
- [ ] Create `src/main.py` entry point that launches the Qt application.
- [ ] Add `.gitignore` entries for `heroforge.db`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `dist/`, `build/`.
- [ ] Set up GitHub Actions workflow (`.github/workflows/ci.yml`) running lint + type-check + tests on push/PR.
- [ ] Write `README.md` with developer setup instructions (install deps, generate DB, run app).

### 5.2 Acceptance Criteria

- `python -m heroforge` opens an empty main window without errors.
- `pytest` exits 0 (no tests yet, but the suite must be discoverable).
- `ruff check src/` and `mypy src/` both exit 0.

---

## 6. Phase 2 – Data Migration

### 6.1 Strategy

All game data currently stored in worksheet data tables or the existing `data/` CSV/XLSX files must be imported into a single SQLite database (`heroforge.db`). The database is the **single source of truth** at runtime; the Excel files become a read-only migration source.

### 6.2 SQLite Schema (table-by-table)

The following tables map directly from workbook sheets or existing data files. Column names are converted to `snake_case`.

#### Core Game Data

| SQLite Table | Source Sheet / File | Notes |
|---|---|---|
| `races` | Race Info sheet + `CreatureInfo.csv` | Merges race and creature data |
| `templates` | Template Info sheet | Includes CR adjustment, LA |
| `classes` | Class Info sheet + `ClassInfo.xlsx` | Base classes and prestige classes |
| `class_skills` | Class Info sheet | Many-to-many: class ↔ skill |
| `class_abilities` | Class Abilities sheet | Per-class, per-level abilities |
| `class_weapons_armor` | Class Weapons & Armor sheet | Proficiency grants |
| `prestige_class_prerequisites` | Prestige Classes I/II/III sheets | Parsed prerequisite expressions |
| `feats` | Feats sheet + Tables sheet | Including epic and fighter bonus feats |
| `feat_prerequisites` | Feats sheet | Parsed prerequisite tree |
| `skills` | Skills sheet | Skill name, key ability, trained-only flag |
| `skill_synergies` | Tables sheet | Pairs of (skill, skill, bonus) |
| `skill_tricks` | Skill Tricks sheet | Cost, description, prerequisites |
| `spells` | Spell Info sheet | All spells across all classes |
| `spells_per_day` | Spells per Day sheet | By class and level |
| `spells_known` | Spells Known sheet | For spontaneous casters |
| `psionic_powers` | Psionic Info sheet | Power point costs, manifester requirements |
| `soulmelds` | SoulmeldsInfo sheet | Shape, descriptors, bind DC |
| `soulmeld_abilities` | SoulmeldAbilities sheet | Per-chakra abilities |
| `incarnum_abilities` | Incarnum Abilities sheet | Non-soulmeld essentia receptacles |
| `variants` | Variants sheet | Class/racial variants |
| `vestiges` | Binder Vestiges sheet | Binder vestige abilities |
| `marshal_auras` | Marshal Auras sheet | Aura bonuses |
| `deities` | Deities sheet | Deity name, domains, alignment |
| `domains` | Domains sheet | Domain powers, spells |
| `grafts` | Grafts sheet | Graft type, body slot, abilities |
| `racial_abilities` | Racial Abilities sheet | Per-race special abilities |
| `graft_abilities` | Graft Abilities sheet | Per-graft ability details |
| `maneuvers` | Maneuvers & Stances sheet | Discipline, level, type |
| `weapons` | `WeaponInfo.csv` | Size, damage, crit, range, weight |
| `armor` | Armor sheet | AC bonus, check penalty, spell failure |
| `magic_enhancements` | Enhancements sheet | Weapon/armor enhancement properties |
| `magic_equipment` | Magic Equipment sheet | Wondrous items, rings, rods, etc. |
| `creatures` | `CreatureInfo.csv` | Wild Shape and Animal Companion targets |
| `tables` | `Tables.csv` | XP table, carry weight, point buy, etc. |
| `languages` | Languages sheet + Tables | Available languages per race |
| `traits` | Traits sheet | Character traits and their effects |
| `flaws` | Flaws sheet | Character flaws and their effects |
| `sources` | Sources sheet | Sourcebook identifiers and full names |

#### Character Save Data

These tables store per-character data (written on save, read on load).  They
are **not** part of the source-of-truth `heroforge.db`; that database is
treated as read-only ROM that only changes when the Excel workbook is
re-imported.  Each character is instead persisted to its own standalone
`.hfc` save file (a SQLite database carrying only these `character_*` tables),
keeping the user's volatile, runtime data cleanly separated from the
application's source data.

To enforce this separation of concerns at the source level, the two schemas
live in dedicated modules: `db/game_schema.py` defines `GAME_SCHEMA_SQL` (the
ROM game data) and `db/character_schema.py` defines `CHARACTER_SCHEMA_SQL` (the
RAM save tables).  `db/schema.py` only provides the shared connection and
initialisation plumbing (`initialize_database` /
`initialize_character_database`).  Every per-character selectable feature and
choice exposed by the Excel workbook has an equivalent save table:

| SQLite Table | Contents |
|---|---|
| `characters` | Top-level character record (name, player, campaign, etc.) |
| `character_ability_scores` | Base scores for each of the six abilities |
| `character_classes` | Ordered list of class levels taken |
| `character_feats` | Feats selected, in order taken |
| `character_skills` | Ranks assigned per skill |
| `character_spells_prepared` | Spells prepared (for prepared casters) |
| `character_spells_known` | Spells known (for spontaneous casters) |
| `character_psionic_powers` | Psionic powers known (for manifesters) |
| `character_soulmelds` | Soulmelds selected, chakra binds |
| `character_maneuvers` | Maneuvers and stances known |
| `character_vestiges` | Binder vestiges bound, with effective level |
| `character_domains` | Cleric (etc.) domains chosen, in slot order |
| `character_marshal_auras` | Marshal minor/major auras selected |
| `character_variants` | Class/racial variants selected |
| `character_skill_tricks` | Skill tricks selected |
| `character_equipment` | Inventory and equipped items |
| `character_buffs` | Active buffs and their parameters |
| `character_languages` | Languages known |
| `character_traits` | Traits and flaws selected |
| `character_grafts` | Grafts attached, with body slot |
| `character_companions` | Animal companions / familiars |
| `character_notes` | Free-text game-log entries (replaces Game Log) |

### 6.3 Seed Script (`src/heroforge/db/seed.py`)

The seed script must:

1. Accept `--db` argument (default: `heroforge.db` at project root).
2. Read each source (CSV, XLSX, or workbook sheet via `openpyxl`) in dependency order.
3. Normalise and clean data (strip whitespace, cast types, handle blank rows).
4. Insert rows inside SQLite transactions (one transaction per table).
5. Log progress and any rows skipped due to validation errors.
6. Be idempotent: running twice must not duplicate rows (use `INSERT OR REPLACE`).

### 6.4 Indexes

```sql
CREATE INDEX idx_races_name            ON races(name);
CREATE INDEX idx_classes_name          ON classes(name);
CREATE INDEX idx_feats_name            ON feats(name);
CREATE INDEX idx_skills_name           ON skills(name);
CREATE INDEX idx_spells_name           ON spells(name);
CREATE INDEX idx_spells_class          ON spells(class_name);
CREATE INDEX idx_weapons_name          ON weapons(name);
CREATE INDEX idx_creatures_name        ON creatures(name);
CREATE INDEX idx_soulmelds_name        ON soulmelds(name);
CREATE INDEX idx_prestige_class_name   ON classes(name) WHERE is_prestige = 1;
```

### 6.5 Acceptance Criteria

- `python -m heroforge.db.seed` completes without errors on a clean checkout.
- Row counts in `heroforge.db` match row counts in source files (verified by an automated test).
- No game data exists in Python source files.

---

## 7. Phase 3 – Logic / Macro Conversion

### 7.1 Strategy

Each VBA function or macro is converted to a standalone, pure Python function in the appropriate `logic/` module. Functions must:

- Accept strongly-typed arguments (dataclasses or primitives).
- Return typed results.
- Have a docstring referencing the D&D 3.5 rulebook, page number, and/or original workbook sheet/cell.
- Be covered by at least one pytest unit test using representative data drawn from the workbook.

### 7.2 Module Breakdown

#### `logic/ability_scores.py`

| Function | Description | Source |
|---|---|---|
| `ability_modifier(score)` | Compute standard modifier: `(score - 10) // 2` | PHB p8 |
| `apply_ability_drain(score, drain)` | Reduce score by drain amount | PHB p307 |
| `apply_ability_damage(score, damage)` | Temporary score reduction | PHB p307 |
| `point_buy_cost(score)` | Cost in point-buy system | DMG p169 |

#### `logic/combat.py`

| Function | Description | Source |
|---|---|---|
| `base_attack_bonus(class_levels)` | Sum BAB across all class levels | PHB p22 |
| `armor_class(dex_mod, armor, shield, size, natural, deflect, dodge, misc)` | Full AC calculation | PHB p136 |
| `touch_ac(...)` | AC ignoring armor and natural armor | PHB p136 |
| `flat_footed_ac(...)` | AC ignoring Dex and dodge | PHB p136 |
| `grapple_modifier(bab, str_mod, size_mod)` | Grapple check modifier | PHB p155 |
| `initiative(dex_mod, feat_bonus, misc)` | Initiative modifier | PHB p136 |
| `melee_attack(bab, str_mod, size_mod, misc)` | Melee attack roll modifier | PHB p124 |
| `ranged_attack(bab, dex_mod, size_mod, misc)` | Ranged attack roll modifier | PHB p124 |
| `damage_bonus(str_mod, weapon_type, two_handed)` | Damage modifier for melee | PHB p113 |
| `carrying_capacity(str_score)` | Light/medium/heavy load thresholds | PHB p162 |

#### `logic/saving_throws.py`

| Function | Description | Source |
|---|---|---|
| `base_save(class_levels, save_type)` | Sum base save across class levels | PHB p22 |
| `fortitude(base, con_mod, misc)` | Fortitude save total | PHB p139 |
| `reflex(base, dex_mod, misc)` | Reflex save total | PHB p139 |
| `will(base, wis_mod, misc)` | Will save total | PHB p139 |

#### `logic/skills.py`

| Function | Description | Source |
|---|---|---|
| `max_ranks(character_level, is_class_skill)` | Maximum ranks purchasable | PHB p62 |
| `skill_modifier(ranks, ability_mod, class_skill, misc)` | Total skill check modifier | PHB p62 |
| `cross_class_rank_cost()` | Always 2 skill points per rank | PHB p62 |
| `skill_synergy_bonus(skills_at_5_ranks)` | +2 bonus from qualifying synergies | PHB p65 |
| `skill_points_per_level(class_, int_mod, is_first_level)` | Points gained on level-up | PHB p62 |

#### `logic/feats.py`

| Function | Description | Source |
|---|---|---|
| `check_prerequisites(feat, character)` | Return `True` if all prerequisites are met | PHB feat entries |
| `available_feats(character)` | List of feats the character qualifies for | — |
| `feat_slots_available(character)` | Count of unspent feat slots | PHB p58 |
| `apply_feat_effects(feat, character)` | Mutate character state with feat bonuses | — |

#### `logic/spells.py`

| Function | Description | Source |
|---|---|---|
| `caster_level(class_levels, class_name)` | Effective caster level | PHB class entries |
| `spells_per_day(class_, caster_level, ability_mod)` | Spell slots per level | PHB p157 |
| `spells_known(class_, caster_level)` | Spells known for spontaneous casters | PHB class entries |
| `arcane_spell_failure(armor_pieces)` | Total ASF chance | PHB p123 |
| `spell_save_dc(spell_level, ability_mod, misc)` | Save DC for a spell | PHB p152 |

#### `logic/psionics.py`

| Function | Description | Source |
|---|---|---|
| `power_points_per_day(class_levels, key_ability_mod)` | PP pool | XPH p20 |
| `manifester_level(class_levels)` | Effective manifester level | XPH p20 |
| `augment_cost(power, augment_count)` | PP cost after augmentation | XPH p29 |

#### `logic/incarnum.py`

| Function | Description | Source |
|---|---|---|
| `essentia_pool(class_levels, feat_bonus)` | Total essentia available | MoI p49 |
| `meldshaper_level(class_levels)` | Effective meldshaper level | MoI p49 |
| `soulmeld_capacity(meldshaper_level)` | Max essentia in a single meld | MoI p49 |
| `chakra_binds_available(class_, level)` | Number of chakra bind slots | MoI class entries |

#### `logic/wild_shape.py`

| Function | Description | Source |
|---|---|---|
| `available_forms(character)` | Creatures the character can wild shape into | PHB p37 |
| `apply_wild_shape(character, creature)` | Replace relevant stats with creature stats | PHB p37 |
| `revert_wild_shape(character)` | Restore original stats | PHB p37 |

#### `logic/buffs.py`

| Function | Description | Source |
|---|---|---|
| `apply_buff(character, buff)` | Apply buff bonuses, respecting stacking rules | PHB p176 |
| `remove_buff(character, buff)` | Remove buff bonuses | PHB p176 |
| `stacks_with(bonus_type_a, bonus_type_b)` | Determine if two bonus types stack | PHB p176 |
| `temporary_hp_total(buffs)` | Sum temporary HP from active buffs | PHB p146 |

#### `logic/equipment.py`

| Function | Description | Source |
|---|---|---|
| `total_weight(inventory)` | Sum of carried item weights | PHB p144 |
| `encumbrance_category(total_weight, capacity)` | Light / Medium / Heavy | PHB p162 |
| `armor_check_penalty(armor, shield)` | Combined ACP | PHB p123 |
| `enhancement_bonus(weapon_or_armor)` | +N enhancement bonus | DMG p224 |

#### `logic/prestige.py`

| Function | Description | Source |
|---|---|---|
| `check_prestige_prerequisites(pc, character)` | Evaluate all prerequisites for a prestige class | Relevant sourcebooks |
| `available_prestige_classes(character)` | List prestige classes the character qualifies for | — |

#### `logic/experience.py`

| Function | Description | Source |
|---|---|---|
| `xp_for_level(level)` | XP required to reach a given level | PHB p22 |
| `level_for_xp(xp)` | Current level from XP total | PHB p22 |
| `encounter_xp(character_level, cr)` | XP awarded for defeating a creature | DMG p36 |

#### `logic/export.py`

| Function | Description |
|---|---|
| `export_character_sheet_text(character)` | Plain-text character sheet |
| `export_character_sheet_pdf(character, path)` | PDF character sheet via `reportlab` |

### 7.3 Acceptance Criteria

- Every function in `logic/` has at least one passing pytest test.
- `mypy --strict src/heroforge/logic/` exits 0.
- Calculation results match the Excel workbook for a set of reference characters.

---

## 8. Phase 4 – UI Implementation

### 8.1 Strategy

Each tab in the Excel workbook maps to a `QWidget` subclass in `src/heroforge/ui/tabs/`. All tabs are hosted by the `QTabWidget` in `MainWindow`. The UI must be reactive: changes in one tab automatically update dependent tabs via Qt signals/slots, replicating the automatic recalculation behaviour of Excel.

### 8.2 Tab Mapping

| Excel Sheet | PyQt Tab Class | Module |
|---|---|---|
| Stats & Character Details | `StatsAndCharacterDetailsTab` | `tabs/stats_and_character_details.py` |
| Race & Templates | `RaceAndTemplatesTab` | `tabs/race_and_templates.py` |
| Prestige Classes I/II/III | `PrestigeClassesTab` | `tabs/prestige_classes.py` |
| Skills | `SkillsTab` | `tabs/skills.py` |
| Skill Tricks | `SkillTricksTab` | `tabs/skill_tricks.py` |
| Languages | `LanguagesTab` | `tabs/languages.py` |
| Grafts | `GraftsTab` | `tabs/grafts.py` |
| Traits / Flaws | `TraitsAndFlawsTab` | `tabs/traits_and_flaws.py` |
| Maneuvers & Stances | `ManeuversAndStancesTab` | `tabs/maneuvers_and_stances.py` |
| Feats | `FeatsTab` | `tabs/feats.py` |
| Armor | `ArmorTab` | `tabs/armor.py` |
| Attacks | `AttacksTab` | `tabs/attacks.py` |
| Enhancements | `EnhancementsTab` | `tabs/enhancements.py` |
| Magic Equipment | `MagicEquipmentTab` | `tabs/magic_equipment.py` |
| Buffs | `BuffsTab` | `tabs/buffs.py` |
| Soulmelds | `SoulmeldsTab` | `tabs/soulmelds.py` |
| Spells per Day / Known | `SpellsTab` | `tabs/spells.py` |
| Psionic Info | `PsionicsTab` | `tabs/psionics.py` |
| Animal Companion | `AnimalCompanionTab` | `tabs/animal_companion.py` |
| Familiar | `FamiliarTab` | `tabs/familiar.py` |
| Character Sheet I–V | `CharacterSheetTab` | `tabs/character_sheet.py` |
| Game Log | `GameLogTab` | `tabs/game_log.py` |
| Initiative Card | `InitiativeCardTab` | `tabs/initiative_card.py` |

> **Note:** The ExportSheet, CS Calc., and internal data sheets (Race Info, Class Info, etc.) have no direct UI tab equivalent; they are replaced by the database layer and logic modules.

### 8.3 Custom / Options Dialogs

| Excel Sheet | Dialog Class | Module |
|---|---|---|
| Options | `OptionsDialog` | `dialogs/options.py` |
| Sources | `SourceSelectDialog` | `dialogs/source_select.py` |
| Template Info | `TemplateInfoDialog` | `dialogs/template_info.py` |
| Custom Race | `CustomRaceDialog` | `dialogs/custom_race.py` |
| Custom Template | `CustomTemplateDialog` | `dialogs/custom_template.py` |
| Custom Class | `CustomClassDialog` | `dialogs/custom_class.py` |
| Custom Familiar | `CustomFamiliarDialog` | `dialogs/custom_familiar.py` |

### 8.4 Signal / Slot Architecture

```
CharacterModel (QObject)
  signals:
    ability_score_changed(ability: str, value: int)
    class_levels_changed()
    feat_added(feat_name: str)
    skill_ranks_changed(skill_name: str, ranks: int)
    buff_toggled(buff_name: str, active: bool)
    character_loaded(character: Character)
    character_reset()

Each tab widget connects to relevant signals and recalculates its
displayed values when those signals fire.
```

### 8.5 Style

- Application-wide stylesheet in `src/heroforge/ui/styles/default.qss`.
- Tab icons (optional) stored in `src/heroforge/ui/resources/`.
- All user-visible strings defined as module-level constants or in a `strings.py` resource file.

### 8.6 Acceptance Criteria

- All tabs listed in §8.2 are present and navigable in the main window.
- Changing ability scores on the Stats tab updates dependent values (skills, saves, attacks) in real time.
- Source-book selection filters available races, classes, feats, and spells appropriately.
- Custom race/template/class/familiar dialogs accept and persist user input.
- `pytest-qt` smoke tests pass for each tab (widget constructs without errors).

---

## 9. Phase 5 – Integration & QA

### 9.1 Tasks

- [ ] Build a set of reference characters using the Excel workbook and export their stats to a machine-readable format (JSON).
- [ ] Write integration tests that create the same characters in the Python app and assert that all calculated values match.
- [x] Test the save/load cycle: create a character, save it, reload it, assert identity.
- [x] Test loading of legacy `.hfg` save files.
- [ ] Manual QA walkthrough against the Excel workbook checklist.
- [ ] Performance profiling: DB queries, logic recalculation, and UI paint times.

### 9.2 Regression Test Characters

| Character | Classes | Race | Purpose |
|---|---|---|---|
| Simple Fighter | Fighter 5 | Human | Basic BAB, feat, and skill checks |
| Multiclass Wizard/Sorcerer | Wizard 3 / Sorcerer 2 | Elf | Spells per day, spells known |
| Druid Wild Shaper | Druid 10 | Half-Elf | Wild Shape, animal companion |
| Incarnate Meldshaper | Incarnate 5 | Human | Essentia, soulmelds, chakra binds |
| Binder | Binder 8 | Human | Vestige binding, suppress/expel |
| Prestige Heavy | Fighter 2 / Wizard 5 / Eldritch Knight 5 | Human | Prestige prerequisites, BAB stacking |
| Psion | Psion 10 | Human | Power points, manifester level |
| Lycanthrope | Fighter 4 / Ranger 2 | Werewolf (Human) | Template application |

---

## 10. Phase 6 – Packaging & Release

### 10.1 Tasks

- [ ] Create `pyinstaller` or `cx_Freeze` spec to bundle the application as a single-file executable for Windows and macOS.
- [ ] Provide a Linux `.AppImage` or instruct users to run from source.
- [ ] Write end-user `README.md` with installation instructions for each platform.
- [ ] Publish release artifacts on GitHub Releases.
- [ ] Tag release as `v8.0.0`.

---

## 11. Workbook Sheet Inventory

The following is the complete list of sheets in `HeroForge Anew 3.5 v7.4.0.1.xlsm`, with their migration disposition.

### 11.1 User-Facing Tabs (→ PyQt tab or dialog)

| Sheet Name | Disposition |
|---|---|
| Stats & Character Details | PyQt tab |
| Race & Templates | PyQt tab |
| Prestige Classes I | PyQt tab (merged) |
| Prestige Classes II | PyQt tab (merged) |
| Prestige Classes III | PyQt tab (merged) |
| Skills | PyQt tab |
| Skill Tricks | PyQt tab |
| Languages | PyQt tab |
| Grafts | PyQt tab |
| Traits | PyQt tab |
| Flaws | PyQt tab (merged with Traits) |
| Maneuvers & Stances | PyQt tab |
| Feats | PyQt tab |
| Armor | PyQt tab |
| Attacks | PyQt tab |
| Enhancements | PyQt tab |
| Magic Equipment | PyQt tab |
| Buffs | PyQt tab |
| Soulmelds | PyQt tab |
| Animal Companion | PyQt tab |
| Familiar | PyQt tab |
| Character Sheet I | PyQt tab (merged) |
| Character Sheet II | PyQt tab (merged) |
| Character Sheet III | PyQt tab (merged) |
| Character Sheet IV | PyQt tab (merged) |
| Character Sheet V | PyQt tab (merged) |
| Game Log | PyQt tab |
| LG Game Log | PyQt tab (Living Greyhawk; low priority) |
| Initiative Card | PyQt tab |
| Table Tent | Low priority; printable summary |
| ExportSheet | Replaced by `logic/export.py` |

### 11.2 Configuration Sheets (→ PyQt dialog)

| Sheet Name | Disposition |
|---|---|
| Options | `OptionsDialog` |
| Sources | `SourceSelectDialog` |
| Custom Race | `CustomRaceDialog` |
| Custom Template | `CustomTemplateDialog` |
| Custom Class | `CustomClassDialog` |
| Custom Familiar | `CustomFamiliarDialog` |

### 11.3 Data Sheets (→ SQLite tables)

| Sheet Name | Target SQLite Table(s) |
|---|---|
| Race Info | `races` |
| Template Info | `templates` |
| Creature Info | `creatures` |
| Interfaces | Internal; defines data contracts |
| Classes | `classes` |
| Class Info | `classes`, `class_skills`, `class_abilities` |
| SoulmeldsInfo | `soulmelds` |
| SoulmeldAbilities | `soulmeld_abilities` |
| Incarnum Abilities | `incarnum_abilities` |
| Variants | `variants` |
| Domain Select | `domains` |
| Binder Vestiges | `vestiges` |
| Marshal Auras | `marshal_auras` |
| Class Abilities | `class_abilities` |
| Class Weapons & Armor | `class_weapons_armor` |
| Racial Abilities | `racial_abilities` |
| Graft Abilities | `graft_abilities` |
| Deities | `deities` |
| Domains | `domains` |
| Spell Info | `spells` |
| Spells per Day | `spells_per_day` |
| Spells Known | `spells_known` |
| Psionic Info | `psionic_powers` |
| Tables | `tables` (XP, carry, point buy, etc.) |
| LG MIL / LG Item Access Tracking | Low priority; Living Greyhawk specific |
| Option Info | Internal |

### 11.4 Calculation Sheets (→ logic modules)

| Sheet Name | Disposition |
|---|---|
| CS Calc. | Absorbed into `logic/` modules |

---

## 12. VBA Macro / Function Inventory

The VBA code in the workbook is compiled into `xl/vbaProject.bin`. The functional areas identified from studying the workbook behaviour are listed below. Each area maps to one or more Python functions in the corresponding `logic/` module.

> **Note:** Because the VBA source is in a compiled binary, each function must be reverse-engineered by observing workbook behaviour and cross-referencing D&D 3.5 rules. Where the workbook behaviour is clear and rule-compliant, the rules are the specification.

### Functional Areas

| Functional Area | Logic Module | Key Behaviours |
|---|---|---|
| Ability score modifiers | `ability_scores.py` | Standard modifier formula; temporary/permanent ability damage |
| BAB progression | `combat.py` | Fast (1/level), Medium (3/4), Slow (1/2) progressions; multi-class summing |
| Saving throw progression | `saving_throws.py` | Good (2 + level/2), Poor (level/3); ability modifier application |
| AC calculation | `combat.py` | All AC types; size modifier lookup |
| Grapple modifier | `combat.py` | BAB + STR + size modifier |
| Initiative | `combat.py` | DEX + Improved Initiative feat bonus |
| Skill point allocation | `skills.py` | Class vs. cross-class; INT modifier; first-level quadrupling |
| Skill modifier calculation | `skills.py` | Ranks + ability + class bonus + synergy + misc |
| Feat prerequisite validation | `feats.py` | Recursive prerequisite tree; BAB, skill rank, attribute checks |
| Spell slots per day | `spells.py` | Table lookup + bonus slots for high ability scores |
| Caster level | `spells.py` | Multi-class stacking for same-type casters |
| Arcane spell failure | `spells.py` | Armor ASF summing; feat reductions |
| Power point pool | `psionics.py` | Class table + key ability bonus |
| Essentia pool | `incarnum.py` | Class table + feat bonuses |
| Wild Shape form selection | `wild_shape.py` | Size/type restrictions by Druid level |
| Wild Shape stat replacement | `wild_shape.py` | STR/DEX/CON replacement; retaining mental stats |
| Buff stacking | `buffs.py` | Bonus type rules; highest bonus wins for typed bonuses |
| Temporary HP | `buffs.py` | Non-stacking, highest-only rule |
| Prestige class prerequisite | `prestige.py` | Arbitrary prerequisite expressions |
| Carrying capacity | `combat.py` | STR-based load thresholds; encumbrance categories |
| XP and levelling | `experience.py` | XP table; multi-class XP penalties |
| Enhancement bonus | `equipment.py` | Weapon/armor effective bonus |
| Character sheet export | `export.py` | Formatted text / PDF output |
| Sheet reset (new character) | `CharacterModel.reset()` | Clear all per-character data back to defaults |
| Save / load character | `db/` | Persist character state to/from SQLite |

---

## 13. Data File Inventory

| File | Format | Contents | Target |
|---|---|---|---|
| `data/ClassInfo.xlsx` | XLSX | Class details: BAB, saves, skill points, class skills, special abilities | `classes`, `class_skills`, `class_abilities` SQLite tables |
| `data/CreatureInfo.csv` | CSV | Full creature stat blocks (races + wild shape targets + companions) | `races`, `creatures` SQLite tables |
| `data/Tables.csv` | CSV | XP table, carry weight table, point buy costs, alignment components, saving throw components | `tables` SQLite table |
| `data/WeaponInfo.csv` | CSV | Weapon statistics: size, damage, crit range, range increment, weight, type | `weapons` SQLite table |
| `HeroForge Anew 3.5 v7.4.0.1.xlsm` | XLSM | All remaining game data in worksheet data tables | All remaining SQLite tables |

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| VBA source unavailable (compiled binary) | High | High | Reverse-engineer from workbook behaviour + D&D 3.5 rules; use reference characters to validate results |
| Ambiguous prerequisite expressions in data | Medium | Medium | Parse prerequisites with a small grammar (pyparsing); log any that fail to parse for manual review |
| Large number of edge cases in feat/class interactions | High | Medium | Write targeted unit tests for every known edge case documented in CHANGELOG.md |
| PyQt6 API differences from PyQt5 | Low | Low | Follow PyQt6 migration guide; use Qt6 types exclusively |
| Data quality issues in source CSVs | Medium | Medium | Add validation step to seed script; log all rows that fail validation |
| Performance of DB queries during real-time recalculation | Low | Medium | Cache static data (races, classes, feats) in memory at startup; only hit DB for character-specific queries |
| Save format compatibility with `.hfg` files | Medium | Low | Implement a one-way importer; document that the old format is read-only |
| Living Greyhawk content is legacy and low priority | Low | Low | Implement stub tabs; mark as deprecated in the UI |

---

*Last updated: 2026-05-08*  
*Document owner: HeroForge Anew development team*
