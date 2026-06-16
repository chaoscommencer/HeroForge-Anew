# GitHub Copilot Instructions for HeroForge-Anew

## Project Overview

HeroForge-Anew is a D&D 3.5 character builder being converted from an Excel-based implementation (`.xlsm`) to a modern Python application. The original workbook contains:

- **Data tables** – races, classes, feats, spells, creatures, weapons, etc. (some already exported to `data/` as `.csv`/`.xlsx`).
- **Macros and functions** – VBA logic that drives character-generation calculations.
- **UI tabs/pages** – worksheets that represent each section of the character sheet (Stats & Character Details, Feats, Skills, Spells, Equipment, etc.).

The new application is built with:

- **Python 3** – application logic.
- **SQLite** (via the `sqlite3` standard-library module or `SQLAlchemy`) – persistent storage, replacing the Excel data tables.
- **PyQt6** (or PyQt5) – graphical user interface, providing a 1:1 visual replacement for every Excel tab.

---

## Repository Layout

```
HeroForge-Anew/
├── .github/
│   └── copilot-instructions.md   # this file
├── data/                         # source data exported from the workbook
│   ├── ClassInfo.xlsx
│   ├── CreatureInfo.csv
│   ├── Tables.csv
│   └── WeaponInfo.csv
├── "HeroForge Anew 3.5 v7.4.0.1.xlsm"  # reference workbook (read-only); filename contains spaces – always quote it in shell scripts
├── Launcher.xlsm                         # reference launcher  (read-only)
├── CHANGELOG.md
└── README.md
```

New Python source files should be placed under a `src/` package tree, for example:

```
src/
├── heroforge/
│   ├── __init__.py
│   ├── db/           # SQLite schema and data-access layer
│   ├── models/       # dataclasses / SQLAlchemy models
│   ├── logic/        # character-generation calculations (ported from VBA)
│   └── ui/           # PyQt windows, widgets, and tab pages
├── tests/
└── main.py           # application entry point
```

---

## Codebase Navigation with Graphify (do this first)

For any question about this repo's architecture, structure, components, or how to add/modify/find
code, your first action should be `graphify query "<question>"` when `graphify-out/graph.json`
exists. Use `graphify path "<A>" "<B>"` for relationship questions and `graphify explain "<concept>"`
for focused-concept questions. These return a scoped subgraph, usually much smaller than the full
report or raw grep output.

Triggers: "how do I…", "where is…", "what does … do", "add/modify a <component>",
"explain the architecture", or anything that depends on how files or classes relate.

If `graphify-out/wiki/index.md` exists, use it for broad navigation. Read `graphify-out/GRAPH_REPORT.md`
only for broad architecture review or when query/path/explain do not surface enough context. Only read
source files when (a) modifying/debugging specific code, (b) the graph lacks the needed detail, or
(c) the graph is missing or stale.

Type `/graphify` in Copilot Chat to build or update the graph, or, preferably, use the isolated `Dockerfile.graphify` container via the `build-graph.sh` script, as outlined in the following section, instead.

### How the graph is built and where the CLI lives

This repository can be mapped into a queryable **knowledge graph** by
[graphify](https://github.com/safishamsi/graphify) (PyPI package `graphifyy`,
CLI `graphify`). `graphifyy` is pinned in the hash-locked `requirements-dev.txt`
(and `requirements-graphifyy.txt`), so the coding agent's setup
(`.github/workflows/copilot-setup-steps.yml`) installs those requirements with
`pip --user`, putting the `graphify` CLI on its `PATH`. Locally, the CLI is
intentionally NOT installed into the dev container's environment — it runs inside
an isolated container instead (see below). Code is extracted locally with
tree-sitter — no API key or network access is needed to build or query the graph.

**Availability differs by environment:**

- In the GitHub Copilot **coding agent** environment, the graph is pre-built at
  `graphify-out/graph.json` by `.github/workflows/copilot-setup-steps.yml`.
- In the **local dev container** (Copilot Chat in VS Code), the graph is *not*
  built automatically. Build it on demand if `graphify-out/graph.json` is
  missing by running `scripts/build-graph.sh`. That script builds the graph in a
  throwaway, network-isolated container (repository mounted read-only, run with
  `--network none`) so graphifyy and its dependencies never enter the dev
  container's Python environment; the resulting `graphify-out/graph.json` is
  written back to the workspace, owned by the host user, ready to query. See
  `Dockerfile.graphify` for the two-stage build it uses.

**Query the graph before grepping or opening files.** A single `graphify query`
returns the relevant functions, classes, files, and their relationships in a
compact form, so you spend far fewer tokens than reading source files one by one.

- Build the graph on demand if `graphify-out/graph.json` does not yet exist:
  `scripts/build-graph.sh` (local dev container; isolated + network-free) or
  `graphify update .` (coding agent, where the CLI is already on `PATH`).
- Understand structure or find where logic lives:
  `graphify query "how are saving throws calculated"`
- Trace a relationship between two concepts:
  `graphify path "AttacksTab" "GameDataRepository"`
- Summarise one symbol and its neighbours:
  `graphify explain "compute_derived_stats()"`
- Rebuild after significant edits (or if `graphify-out/graph.json` is missing):
  `scripts/build-graph.sh` locally, or `graphify update .` in the coding agent.
- Skim `graphify-out/GRAPH_REPORT.md` for a high-level architecture overview.

In the **local dev container** the `graphify` CLI is not on `PATH`, so run any
`graphify` subcommand through the isolated container by forwarding it to the
script, e.g. `scripts/build-graph.sh graphify query "how are saving throws
calculated"` (the image is reused; the repo stays read-only and network-free).

Only fall back to `grep`/file reads for the specific locations the graph points
you at. See `.github/skills/graphify/SKILL.md` for full usage. The generated
`graphify-out/` directory is git-ignored.

---

## Goals and Conventions

### 1. Excel-to-SQLite Migration

- Treat each data sheet in the workbook (and each CSV/XLSX in `data/`) as a single SQLite table.
- Use `snake_case` for table and column names. Map Excel column headers directly where they are already descriptive; otherwise choose clear, concise names.
- Provide a migration/seed script (`src/heroforge/db/seed.py`) that reads the source files and populates a fresh SQLite database. The database file should default to `heroforge.db` at the project root (configurable via environment variable or CLI argument).
- Include appropriate indexes on columns that will be used for lookups (e.g. `class_name`, `race_name`, `feat_name`).
- Never hard-code data in Python source files; all game data must live in the database.

### 2. VBA-to-Python Logic Conversion

- Port each VBA macro or worksheet function to a standalone Python function or method in `src/heroforge/logic/`.
- Preserve the original calculation logic exactly – do not "fix" game-rule behaviour unless a bug has been explicitly identified and documented.
- Group related calculations into modules that mirror the Excel tab they came from (e.g. `logic/skills.py`, `logic/combat.py`, `logic/spells.py`).
- Write a pytest unit test for every ported function in `tests/`, using representative data drawn from the workbook.
- Use type hints on all function signatures.
- Document each function with a docstring that references the relevant D&D 3.5 rulebook, page number, and/or workbook sheet/cell where the logic was originally defined.

### 3. PyQt UI

- Implement one PyQt `QWidget` (or `QTabWidget` page) per original Excel tab, using the same tab names and layout order as the workbook.
- Place each tab's implementation in its own file under `src/heroforge/ui/tabs/` (e.g. `tabs/stats_and_character_details.py`, `tabs/feats.py`).
- The main window (`src/heroforge/ui/main_window.py`) should host a `QTabWidget` containing all tab pages.
- Use Qt signals/slots to keep the UI reactive – avoid polling or direct model mutation from within widgets.
- Apply a consistent style: use Qt stylesheets defined in `src/heroforge/ui/styles/` rather than inline style strings.
- All string literals displayed in the UI must be defined as constants or loaded from a resource file, not scattered through widget code.

### 4. General Coding Conventions

- Python version: **3.11+** (set `requires-python = ">=3.11"` in `pyproject.toml`).
- Formatting: **Black** with default settings (line length 88).
- Linting: **Ruff** (or Flake8) with at minimum E, W, and F rules enabled.
- Type checking: **mypy** in strict mode.
- Testing: **pytest**; aim for ≥ 80 % coverage on `logic/` and `db/` modules.
- Dependencies are managed via `pyproject.toml` (PEP 517/518). Do not use `setup.py`.
- Use `pathlib.Path` instead of `os.path` for all file-system operations.
- Prefer `dataclasses` or `pydantic` models over raw dictionaries for structured data passed between layers.

### 5. Pre-Completion Quality Checks

`ruff`, `black`, and `pytest` are pre-installed in Copilot's development environment via `.github/workflows/copilot-setup-steps.yml` (which installs the hash-pinned `requirements-dev.txt` with `pip --user`, then `--no-deps -e .`). Each tool has a skill definition under `.github/skills/<tool>/SKILL.md` that provides full usage instructions.

**Only when Python files have been added or modified**, run the following checks in order before finishing the task:

1. **Invoke the `pytest` skill** – follow its instructions to run the full test suite. All tests must pass (exit 0) before proceeding.
2. **Invoke the `black` skill** – follow its instructions to run `black src/ tests/` (format) and then `black --check src/ tests/` (verify). The check must exit 0.
3. **Invoke the `ruff` skill** – follow its instructions to run `ruff check src/`. Fix every reported violation so the check exits 0.

These steps mirror the *Run tests with pytest*, *Lint with Ruff*, and *Check formatting with Black* steps in `.github/workflows/ci.yml`. Generated code must pass all three checks before the task is considered complete.

### 6. Commit and Branch Conventions

- Branch names: `feature/<short-description>`, `bugfix/<short-description>`, `data/<sheet-name>`.
- Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:  
  `feat:`, `fix:`, `data:`, `refactor:`, `test:`, `docs:`, `chore:`.
- Keep commits focused; one logical change per commit.

---

## Key Domain Concepts

| Term | Meaning |
|---|---|
| **Ability Score** | One of the six core D&D attributes: STR, DEX, CON, INT, WIS, CHA |
| **Base Attack Bonus (BAB)** | Attack bonus derived from class levels |
| **Saving Throws** | Fortitude, Reflex, Will – calculated from class levels + ability modifiers |
| **Feat** | A special ability a character can take at certain levels |
| **Skill** | A trained ability with ranks, class-skill bonuses, and ability modifiers |
| **Prestige Class** | An advanced class with prerequisites, taken after core class levels |
| **Template** | A creature modification applied on top of a base race/creature |
| **Soulmeld** | An Incarnum-based ability (Magic of Incarnum sourcebook) |
| **Wild Shape** | A Druid class feature allowing the character to transform into animals |

Copilot should use these terms consistently in variable names, comments, and docstrings.

---

## Do's and Don'ts

**Do:**
- Query the graphify knowledge graph (`graphify query`, `path`, `explain`) before grepping or opening many files to understand the codebase.
- Follow the structure and naming conventions described above.
- Reference the original workbook and data files in comments when porting logic.
- Add or update tests whenever logic is added or modified.
- Use SQLite transactions for all multi-statement writes.
- Ask for clarification (via inline `TODO` or PR comment) when a VBA formula is ambiguous.
- When Python files have been added or modified, invoke the `pytest`, `black`, and `ruff` skills (in that order) before finishing the task, follow their instructions, and fix all issues so every check exits 0 (matching the CI workflow checks).
- If a request conflicts with, or would break from, the rules, architecture, or conventions established in this file, propose appropriate revisions to this instructions file as part of the response rather than silently deviating from it.

**Don't:**
- Hard-code game data in Python source files.
- Break the 1:1 tab mapping between the Excel workbook and the PyQt UI without explicit approval.
- Introduce dependencies not already listed in `pyproject.toml` without prior discussion.
- Silently change calculation results – any intentional rule deviation must be documented.
- Use deprecated PyQt APIs; target the current stable PyQt6 release.
