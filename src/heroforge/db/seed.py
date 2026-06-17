"""Database seed script for HeroForge-Anew.

Reads source data files from the ``data/`` directory and populates the
SQLite database with game content.

Usage::

    python -m heroforge.db.seed --db heroforge.db --data-dir data/

The ``seed_all`` function is importable for use in tests.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import openpyxl

from heroforge.db.schema import initialize_database
from heroforge.logging_config import configure_logging
from heroforge.logic.animal_companion import (
    COMPANION_PROGRESSION_LABELS,
    STANDARD_COMPANION_PROGRESSION,
    CompanionProgression,
)
from heroforge.logic.familiar import STANDARD_FAMILIAR_BONUSES

logger = logging.getLogger(__name__)

# Project root is two levels above this file (src/heroforge/db/seed.py)
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
_DEFAULT_WORKBOOK = _PROJECT_ROOT / "HeroForge Anew 3.5 v7.4.0.1.xlsm"
_FOOTNOTE_MARKER_NORMALIZATION = {"1": "¹", "2": "²", "3": "³"}
_SKILL_FOOTNOTE_LEGEND_CELLS = (
    ("Character Sheet I", "BH151"),
    ("Animal Companion", "BI145"),
    ("Familiar", "BI145"),
)

#: The workbook's "Skills" sheet computes each skill's *unconditional* synergy
#: bonus in column GQ ("Synergy").  Each formula adds ``(2 + …)`` once for every
#: *source* skill that reaches 5 ranks, e.g. Diplomacy's cell reads
#: ``=(2+…)*((SkBluffRanks>=5)+…+(SkSenseMotiveRanks>=5)+…)``.  The
#: ``(from_skill -> to_skill)`` pairs are therefore encoded as the
#: ``Sk<Name>Ranks>=5`` references, which :func:`_extract_skill_synergies`
#: parses to seed ``skill_synergies`` rather than transcribing PHB p65 by hand.
_SKILL_SYNERGY_SHEET = "Skills"
_SKILL_SYNERGY_COLUMN_INDEX = 198  # column GQ ("Synergy"), 0-based
_SKILL_DATA_START_ROW = 5  # 0-based; data rows begin below the header
_SKILL_SYNERGY_BONUS = 2
_SKILL_SYNERGY_SOURCE_RE = re.compile(r"Sk([A-Za-z]+)Ranks>=5\)")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_int(value: object, default: int = 0) -> int:
    """Convert *value* to int, returning *default* on failure."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    """Convert *value* to float, returning *default* on failure."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _cell_value(cell: object) -> str:
    """Return the string representation of a spreadsheet cell value."""
    if cell is None:
        return ""
    val = getattr(cell, "value", cell)
    if val is None:
        return ""
    return str(val).strip()


# ---------------------------------------------------------------------------
# Workbook parsing helpers
# ---------------------------------------------------------------------------
#
# The reference workbook ``HeroForge Anew 3.5 v7.4.0.1.xlsm`` holds the bulk of
# the remaining game data on dedicated "data sheets" (see
# ``docs/conversion-plan.md`` §11.3).  Each sheet has its own idiosyncratic
# layout, so a small spec/extractor is written per target table below.  All
# extractors share the helpers in this section.


def _col(row: tuple[object, ...], letter: str) -> str:
    """Return the stripped string value of *row* at spreadsheet column *letter*.

    ``letter`` is a single column letter in the ``A``-``Z`` range (the data
    sheets used here never exceed column ``R``).  Out-of-range columns yield an
    empty string so extractors can probe optional columns safely.
    """
    idx = ord(letter.upper()) - ord("A")
    if idx < 0 or idx >= len(row):
        return ""
    value = row[idx]
    return "" if value is None else str(value).strip()


def _sheet_rows(
    ws: object, start_row: int, max_blank: int = 60
) -> list[tuple[object, ...]]:
    """Return data rows of *ws* starting at *start_row* (0-based).

    Iteration stops once *max_blank* consecutive fully-blank rows are seen.
    Several worksheets declare an enormous nominal dimension (e.g.
    ``A1:IQ65536``); the blank-run guard keeps parsing bounded to the populated
    region while still tolerating the small blank separators that group data.
    """
    collected: list[tuple[object, ...]] = []
    blank = 0
    for index, row in enumerate(ws.iter_rows(values_only=True)):  # type: ignore[attr-defined]
        if index < start_row:
            continue
        if all(cell is None or str(cell).strip() == "" for cell in row):
            blank += 1
            if blank >= max_blank:
                break
            continue
        blank = 0
        collected.append(row)
    return collected


def _normalize_skill_key(name: str) -> str:
    """Return a casefolded, punctuation-free key for matching skill names.

    Used to reconcile the workbook's ``Sk<Name>Ranks`` formula identifiers (e.g.
    ``KnowledgeArcana``) with their canonical skill names (e.g.
    ``Knowledge (arcana)``).
    """
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _strip_footnotes(name: str) -> str:
    """Remove trailing footnote markers (superscripts, asterisks, ellipsis) from a name.

    Workbook seeding preserves the stripped markers and their legend text in
    dedicated skill-footnote tables.
    """
    return re.sub(r"[\u00b9\u00b2\u00b3\u2026\*\s]+$", "", name).strip()


def _trailing_footnote_markers(name: str) -> str:
    """Return trailing footnote marker characters from *name*."""
    m = re.search(r"([\u00b9\u00b2\u00b3\*]+)\s*$", name)
    return m.group(1) if m else ""


def _normalize_footnote_marker(marker: str) -> str:
    """Normalize workbook legend markers to their skill-name form."""
    return "".join(_FOOTNOTE_MARKER_NORMALIZATION.get(ch, ch) for ch in marker)


def _parse_skill_footnote_legend(text: str) -> list[tuple[str, str]]:
    """Extract ``(marker, description)`` pairs from a workbook legend cell."""
    rows: list[tuple[str, str]] = []
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if line.startswith("Skills marked with "):
            m = re.match(r"Skills marked with ([¹²³])\s+(.*)", line)
            if m:
                rows.append((m.group(1), m.group(2).strip()))
            continue
        if line.startswith(("1 ", "2 ", "3 ", "¹ ", "² ", "³ ", "× ")):
            marker, description = line.split(None, 1)
            rows.append((_normalize_footnote_marker(marker), description.strip()))
            continue
        for marker, description in re.findall(
            r"(\*\*|\*)\s+(.+?)(?=(?:\s{2,}\*\*|\s{2,}\*|$))", line
        ):
            rows.append((marker, description.strip()))
    return rows


def _lstrip_separator(text: str) -> str:
    """Strip a leading ``" : "`` separator used by description columns."""
    return re.sub(r"^\s*:\s*", "", text).strip()


def _is_sql_identifier(name: str) -> bool:
    """Return ``True`` when *name* has safe SQL identifier syntax.

    This validates identifier shape only; it does not check whether the name
    exists in schema metadata.
    """
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))


# ---------------------------------------------------------------------------
# Per-table workbook extractors
#
# Each extractor receives the open workbook and returns a list of tuples whose
# order matches the ``columns`` declared in the ``_WORKBOOK_TABLES`` registry.
# ---------------------------------------------------------------------------


def _extract_sources(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Sources"]  # type: ignore[index]
    for row in _sheet_rows(ws, 7):
        full_name = _col(row, "C")
        abbr = _col(row, "H")
        m = re.match(r"^\((.+)\)$", abbr)
        if not (m and full_name):
            continue
        rows.append((m.group(1).strip(), full_name))
    return rows


def _extract_languages(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Languages"]  # type: ignore[index]
    for row in _sheet_rows(ws, 4):
        name = _col(row, "B")
        if not name:
            continue
        rows.append((name, "", ""))
    return rows


def _extract_skills(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Skills"]  # type: ignore[index]
    for row in _sheet_rows(ws, 5):
        raw_name = _col(row, "A")
        if not raw_name or raw_name.upper() == "SKILL NAME":
            continue
        name = _strip_footnotes(raw_name)
        if not name:
            continue
        key_raw = _col(row, "B")
        armor_check = 1 if "*" in key_raw else 0
        key_ability = key_raw.replace("*", "").strip()
        rows.append((name, key_ability, 0, armor_check, ""))
    return rows


def _extract_skill_footnotes(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Skills"]  # type: ignore[index]
    for row in _sheet_rows(ws, 5):
        raw_name = _col(row, "A")
        if not raw_name or raw_name.upper() == "SKILL NAME":
            continue
        marker = _trailing_footnote_markers(raw_name)
        if not marker:
            continue
        name = _strip_footnotes(raw_name)
        if not name:
            logger.warning("Could not normalize skill footnote row: %r", raw_name)
            continue
        rows.append((name, raw_name, marker))
    return rows


def _extract_skill_footnote_definitions(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for sheet_name, cell in _SKILL_FOOTNOTE_LEGEND_CELLS:
        legend = _cell_value(wb[sheet_name][cell])  # type: ignore[index]
        for marker, description in _parse_skill_footnote_legend(legend):
            rows.append((sheet_name, marker, description))
    return rows


def _extract_skill_tricks(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Skill Tricks"]  # type: ignore[index]
    for row in _sheet_rows(ws, 5):
        name = _col(row, "C")
        description = _col(row, "E")
        if not (name and description):
            continue
        rows.append((name, 2, _lstrip_separator(description), _col(row, "D")))
    return rows


def _extract_traits(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Traits"]  # type: ignore[index]
    for row in _sheet_rows(ws, 3):
        name = _col(row, "C")
        benefit = _col(row, "L")
        if not name or name == "Trait" or not benefit:
            continue
        source = f"{_col(row, 'I')} {_col(row, 'J')}".strip()
        benefit = _lstrip_separator(benefit)
        rows.append((name, benefit, benefit, "", source))
    return rows


def _extract_flaws(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Flaws"]  # type: ignore[index]
    for row in _sheet_rows(ws, 4):
        name = _col(row, "C")
        effect = _col(row, "I")
        if not name or name == "Flaw" or not effect:
            continue
        source = f"{_col(row, 'G')} {_col(row, 'H')}".strip()
        rows.append((name, "", _lstrip_separator(effect), source))
    return rows


def _extract_variants(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Variants"]  # type: ignore[index]
    base_class = ""
    for row in _sheet_rows(ws, 3):
        name = _col(row, "C")
        if not name:
            continue
        prereq = _col(row, "D")
        source = _col(row, "E")
        if not prereq and not source:
            # Section header naming the base class for the rows that follow.
            base_class = name
            continue
        rows.append((name, base_class, prereq, source))
    return rows


def _extract_domains(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Domains"]  # type: ignore[index]
    for row in _sheet_rows(ws, 0):
        raw_name = _col(row, "A")
        granted = _col(row, "B")
        if not raw_name or not granted:
            continue
        name = re.sub(r"^xx-|-xx$", "", raw_name).strip()
        spells = [_col(row, chr(ord("C") + i)) for i in range(9)]
        rows.append((name, granted, *spells))
    return rows


def _extract_deities(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Deities"]  # type: ignore[index]
    for row in _sheet_rows(ws, 3):
        name = _col(row, "A")
        if not name or name == "Select A Deity":
            continue
        rows.append((name, _col(row, "B"), _col(row, "I"), _col(row, "J"), ""))
    return rows


def _extract_feats(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Feats"]  # type: ignore[index]
    current_type = ""
    for row in _sheet_rows(ws, 9):
        name = _col(row, "D")
        benefit = _col(row, "F")
        if not name:
            continue
        if not benefit:
            # Category/section header (e.g. "General Feats").
            current_type = name
            continue
        benefit = _lstrip_separator(benefit)
        rows.append((name, current_type, benefit, benefit, "", ""))
    return rows


def _extract_feat_prerequisites(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Feats"]  # type: ignore[index]
    for row in _sheet_rows(ws, 9):
        name = _col(row, "D")
        benefit = _col(row, "F")
        if not name or not benefit:
            continue
        prereq_raw = _col(row, "E")
        for prereq in (p.strip() for p in prereq_raw.split(",")):
            if prereq:
                rows.append((name, prereq))
    return rows


def _extract_armor(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Armor"]  # type: ignore[index]
    for row in _sheet_rows(ws, 4):
        name = _col(row, "H")
        if not name or name == "(none)" or "\u2013" in name:
            continue
        rows.append(
            (
                name,
                _col(row, "K"),
                _safe_int(_col(row, "M")),
                _safe_int(_col(row, "N")),
                _safe_int(_col(row, "O")),
                _safe_int(_col(row, "P")),
                None,
                None,
                _safe_float(_col(row, "Q")),
                _col(row, "I"),
            )
        )
    return rows


def _extract_maneuvers(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Maneuvers & Stances"]  # type: ignore[index]
    discipline = ""
    for row in _sheet_rows(ws, 5):
        name = _col(row, "D")
        if not name:
            continue
        level = _col(row, "I")
        maneuver_type = _col(row, "K")
        if not level and not maneuver_type:
            # Discipline header preceding its maneuvers.
            discipline = name
            continue
        rows.append(
            (
                name,
                discipline,
                _safe_int(level) if level else None,
                maneuver_type,
                "",
                "",
                "",
                "",
                "",
                "",
            )
        )
    return rows


def _extract_grafts(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Grafts"]  # type: ignore[index]
    graft_type = ""
    for row in _sheet_rows(ws, 3):
        name = _col(row, "C")
        if not name:
            continue
        if name.endswith("Grafts"):
            graft_type = name
            continue
        rows.append((name, graft_type, "", "", ""))
    return rows


def _extract_graft_abilities(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["Graft Abilities"]  # type: ignore[index]
    for row in _sheet_rows(ws, 5):
        graft_name = _col(row, "A")
        description = _col(row, "B")
        if not (graft_name and description):
            continue
        ability = _ability_name_from_description(description)
        rows.append((graft_name, ability or graft_name, description))
    return rows


#: Whole-cell numeric guards used to skip spacer/header cells in the data sheets.
_SIGNED_INT_RE = re.compile(r"-?\d+")
_UNSIGNED_INT_RE = re.compile(r"\d+")


def _ability_name_from_description(description: str) -> str:
    """Derive an ability name from a ``"× Name: text"`` description bullet.

    Strips a leading ``×`` bullet/whitespace and keeps the text up to the first
    colon.  Descriptions with no colon yield the full (de-bulleted) text so the
    name is never empty.
    """
    return re.sub(r"^[\u00d7\s]+", "", description).split(":", 1)[0].strip()


def _extract_racial_abilities(wb: object) -> list[tuple[object, ...]]:
    """Extract per-race special abilities from the ``Racial Abilities`` sheet.

    Each populated data row carries the race name in column ``A`` and a single
    ability bullet (``× Name: description``) in column ``C``.  The legend/template
    block at the top of the sheet has no race name in column ``A`` and is skipped
    naturally.  The ability name is parsed from the bullet for convenience while
    the full bullet text is preserved as the description.
    """
    rows: list[tuple[object, ...]] = []
    ws = wb["Racial Abilities"]  # type: ignore[index]
    for row in _sheet_rows(ws, 0):
        race_name = _col(row, "A")
        description = _col(row, "C")
        if not (race_name and description):
            continue
        ability = _ability_name_from_description(description)
        rows.append((race_name, ability or race_name, description))
    return rows


def _extract_incarnum_abilities(wb: object) -> list[tuple[object, ...]]:
    """Extract the receptacle (blue) incarnum abilities from ``Incarnum Abilities``.

    The catalogue lives in a three-column block: an index in column ``V``, the
    ability name in column ``W`` and a description template in column ``X``.
    Header/spacer rows (whose ``W`` cell is blank or purely numeric) are skipped.
    """
    rows: list[tuple[object, ...]] = []
    ws = wb["Incarnum Abilities"]  # type: ignore[index]
    for row in _sheet_rows(ws, 0):
        name = _col(row, "W")
        description = _col(row, "X")
        if not name or not description or _SIGNED_INT_RE.fullmatch(name):
            continue
        rows.append((name, None, None, description))
    return rows


def _extract_vestiges(wb: object) -> list[tuple[object, ...]]:
    """Extract the bindable vestige list from the ``Binder Vestiges`` sheet.

    The vestige index/name/DC table occupies columns ``P``/``Q``/``R``; rows are
    keyed by an integer index in column ``P`` with the name in column ``Q``.
    Iteration stops at the unrelated ``Pact Augmentations`` block that reuses the
    same columns lower down the sheet.
    """
    rows: list[tuple[object, ...]] = []
    ws = wb["Binder Vestiges"]  # type: ignore[index]
    for row in _sheet_rows(ws, 0):
        name = _col(row, "Q")
        if name == "Pact Augmentations":
            break
        index = _col(row, "P")
        if not _UNSIGNED_INT_RE.fullmatch(index) or not name:
            continue
        dc_str = _col(row, "R")
        dc: int | None = int(dc_str) if _UNSIGNED_INT_RE.fullmatch(dc_str) else None
        rows.append((name, dc, "", "", "", ""))
    return rows


def _extract_marshal_auras(wb: object) -> list[tuple[object, ...]]:
    """Extract minor and major marshal auras from the ``Marshal Auras`` sheet.

    Minor auras are listed in column ``B`` and major auras in column ``E``, each
    under a ``Minor Auras``/``Major Auras`` header.  The header labels live in
    columns ``A``/``D`` so the name columns contain only aura names.
    """
    rows: list[tuple[object, ...]] = []
    ws = wb["Marshal Auras"]  # type: ignore[index]
    for row in _sheet_rows(ws, 0):
        minor = _col(row, "B")
        if minor:
            rows.append((minor, "Minor", "", ""))
        major = _col(row, "E")
        if major:
            rows.append((major, "Major", "", ""))
    return rows


# Matches the wizard "× Familiar:" class-feature header that introduces the
# universal master benefits in the Character Sheet's Special Abilities section.
_FAMILIAR_PARENT_RE = re.compile(r"^\s*[\u00d7]\s*Familiar\s*:", re.IGNORECASE)


def _parse_master_ability(text: str) -> tuple[str, str]:
    """Split a ``"× Name: description"`` bullet into ``(name, description)``."""
    body = re.sub(r"^[\u00d7\s]+", "", text)
    name, _sep, description = body.partition(":")
    return name.strip(), description.strip()


def _extract_familiar_master_abilities(wb: object) -> list[tuple[object, ...]]:
    """Extract the universal familiar master benefits from ``Class Abilities``.

    These are the indented lines that appear immediately beneath the
    ``× Familiar: You have called a <creature> …`` wizard class-feature entry in
    the Character Sheet's *Special Abilities* section
    (``Class Abilities!A162:A164`` in the reference workbook): Alertness, Scry on
    Familiar and Natural Link.  They are detected structurally – the parent
    ``× Familiar:`` line followed by its indented ``×`` children – so the
    extractor tolerates row shifts in future workbook revisions.
    """
    ws = wb["Class Abilities"]  # type: ignore[index]
    rows: list[tuple[object, ...]] = []
    in_block = False
    order = 0
    for (value,) in ws.iter_rows(  # type: ignore[attr-defined]
        min_col=1, max_col=1, values_only=True
    ):
        if value is None:
            if in_block:
                break
            continue
        text = str(value)
        stripped = text.strip()
        if not in_block:
            if (
                _FAMILIAR_PARENT_RE.match(text)
                and "magical companion" in stripped.lower()
            ):
                in_block = True
            continue
        # In-block: collect the indented "×" child bullets, stopping at the next
        # non-indented ability (or any non-bullet line).
        if text[:1].isspace() and stripped.startswith("\u00d7"):
            name, description = _parse_master_ability(stripped)
            if name and description:
                rows.append((name, description, order))
                order += 1
            continue
        break
    return rows


def _extract_soulmelds(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["SoulmeldsInfo"]  # type: ignore[index]
    for row in _sheet_rows(ws, 4):
        name = _col(row, "A")
        if not name or name.startswith("Select") or name.startswith("You do not"):
            continue
        rows.append((name, "", "", 3, None, "", ""))
    return rows


def _extract_soulmeld_abilities(wb: object) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    ws = wb["SoulmeldAbilities"]  # type: ignore[index]
    current = ""
    for row in _sheet_rows(ws, 7):
        name = _col(row, "A")
        if name:
            current = name
        description = _col(row, "E")
        if not current or not description:
            continue
        rows.append((current, "", _safe_int(_col(row, "D")), description))
    return rows


_SPELL_LEVEL_RE = re.compile(r"(\d+)")


def _extract_buffs(wb: object) -> list[tuple[object, ...]]:
    """Extract the master buff catalogue from the two-column ``Buffs`` sheet.

    The left block (column ``A``) lists buff *spells* grouped under spell-level
    headers (``0 Level``, ``1st Level`` …).  The right block (column ``L``)
    lists *class* buffs grouped under class/category headers.  Header rows carry
    a name but no checkbox cells; buff rows carry the two ``True/False`` toggles.
    """
    ws = wb["Buffs"]  # type: ignore[index]
    rows: list[tuple[object, ...]] = []
    seen: set[tuple[str, str]] = set()
    spell_level: object = None
    class_category = ""
    for row in _sheet_rows(ws, 1):
        # Left block: buff spells grouped by spell level.
        name = _col(row, "A")
        if name:
            if not _col(row, "B") and not _col(row, "C"):
                match = _SPELL_LEVEL_RE.search(name)
                spell_level = int(match.group(1)) if match else None
            else:
                key = (name, "Buff Spells")
                if key not in seen:
                    seen.add(key)
                    rows.append((name, "Buff Spells", spell_level, None, None, None))

        # Right block: class buffs grouped by class/category header.
        class_name = _col(row, "L")
        if class_name:
            if not _col(row, "M") and not _col(row, "N"):
                class_category = class_name.rstrip(":")
            elif class_category:
                key = (class_name, class_category)
                if key not in seen:
                    seen.add(key)
                    rows.append((class_name, class_category, None, None, None, None))
    return rows


def _extract_races(wb: object) -> list[tuple[object, ...]]:
    """Extract the base race list from the ``Race Info`` sheet.

    The sheet's race-type lookup block tags each base race/creature category in
    column ``A`` with the literal ``"Racial"`` in column ``B``.  These names are
    the selectable races in HeroForge's data model; richer per-race statistics
    are computed by the workbook at runtime and are not stored as a flat table.
    """
    ws = wb["Race Info"]  # type: ignore[index]
    rows: list[tuple[object, ...]] = []
    seen: set[str] = set()
    for row in _sheet_rows(ws, 0):
        name = _col(row, "A")
        category = _col(row, "B")
        if category != "Racial" or not name or name in seen:
            continue
        seen.add(name)
        rows.append((name,))
    return rows


def _extract_templates(wb: object) -> list[tuple[object, ...]]:
    """Extract the template catalogue from the ``Template Info`` sheet.

    The template table begins below the ``Template*`` header row; each data row
    carries the template name in column ``A`` plus optional type/subtype changes
    in columns ``D``/``E``.  The ``Custom Template`` placeholder row is skipped.
    """
    ws = wb["Template Info"]  # type: ignore[index]
    rows: list[tuple[object, ...]] = []
    seen: set[str] = set()
    started = False
    for row in _sheet_rows(ws, 13):
        name = _col(row, "A")
        if not started:
            if name == "Template*":
                started = True
            continue
        if not name or name.lstrip().startswith("Custom Template") or name in seen:
            continue
        seen.add(name)
        rows.append((name, _col(row, "D"), _col(row, "E")))
    return rows


def _extract_spell_progression(wb: object, sheet: str) -> list[tuple[object, ...]]:
    """Extract a class/level/spell-level/count grid from a spell sheet.

    Both ``Spells per Day`` and ``Spells Known`` lay out many class blocks in a
    grid.  Each block has a class name in its header cell; the row immediately
    below holds spell-level headers (``0``-``9``); the column just left of the
    first spell-level column holds the caster level; subsequent rows give the
    slot/known count per spell level.  Returns ``(class_name, caster_level,
    spell_level, count)`` tuples (blank cells, meaning "no slots", are skipped).
    """
    ws = wb[sheet]  # type: ignore[index]
    grid = [tuple(r) for r in ws.iter_rows(values_only=True)]

    def _as_int(value: object, *, warn_on_loss: bool = True) -> int | None:
        def _warn(reason: str) -> None:
            if warn_on_loss:
                logger.warning(
                    "Dropping non-integral value while extracting sheet %s: %r (%s)",
                    sheet,
                    value,
                    reason,
                )

        if value is None:
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            if math.isfinite(value) and value.is_integer():
                return int(value)
            _warn("float is not an integral finite value")
            return None
        text = str(value).strip()
        if text == "":
            return None
        try:
            numeric = float(text)
            if not math.isfinite(numeric) or not numeric.is_integer():
                _warn("parsed value is not a finite integer")
                return None
            return int(numeric)
        except (TypeError, ValueError):
            _warn("failed to parse as numeric value")
            return None

    # Locate class-name header cells: non-numeric, non-empty labels that are not
    # the level-column markers used inside some blocks.
    headers: list[tuple[int, int, str]] = []
    for r_idx, row in enumerate(grid):
        for c_idx, cell in enumerate(row):
            if cell is None:
                continue
            text = str(cell).strip()
            if (
                text
                and _as_int(text, warn_on_loss=False) is None
                and text not in ("CL", "Lvl")
            ):
                headers.append((r_idx, c_idx, text))

    rows: list[tuple[object, ...]] = []
    for r_idx, c_idx, class_name in headers:
        if r_idx + 1 >= len(grid):
            continue
        level_header = grid[r_idx + 1]
        # Spell-level columns are the run of integer (0-9) headers starting at
        # the class-name column.
        spell_cols: list[tuple[int, int]] = []
        col = c_idx
        while col < len(level_header):
            value = _as_int(level_header[col], warn_on_loss=False)
            if value is None or not 0 <= value <= 9:
                break
            spell_cols.append((col, value))
            col += 1
        if not spell_cols:
            continue
        level_col = spell_cols[0][0] - 1
        if level_col < 0:
            continue
        # Data rows run until the next class block in the same column.
        next_row = len(grid)
        for hr, hc, _ in headers:
            if hc == c_idx and r_idx < hr < next_row:
                next_row = hr
        for d_idx in range(r_idx + 2, next_row):
            data_row = grid[d_idx]
            if level_col >= len(data_row):
                break
            caster_level = _as_int(data_row[level_col])
            if caster_level is None:
                cell = data_row[level_col]
                if cell is None or str(cell).strip() == "":
                    continue  # tolerate intra-block blank separators
                logger.warning(
                    "Skipping %s block %r row %d: non-integral caster level %r",
                    sheet,
                    class_name,
                    d_idx + 1,
                    cell,
                )
                break
            for spell_col, spell_level in spell_cols:
                if spell_col >= len(data_row):
                    continue
                count = _as_int(data_row[spell_col])
                if count is None:
                    cell = data_row[spell_col]
                    if cell is not None and str(cell).strip() != "":
                        logger.warning(
                            "Skipping %s block %r row %d spell level %d: "
                            "non-integral count %r",
                            sheet,
                            class_name,
                            d_idx + 1,
                            spell_level,
                            cell,
                        )
                    continue
                rows.append((class_name, caster_level, spell_level, count))
    return rows


def _extract_spells_per_day(wb: object) -> list[tuple[object, ...]]:
    return _extract_spell_progression(wb, "Spells per Day")


def _extract_spells_known(wb: object) -> list[tuple[object, ...]]:
    return _extract_spell_progression(wb, "Spells Known")


# ---------------------------------------------------------------------------
# Psionic progression (workbook "Psionic Info" sheet, Excel tab 7b)
# ---------------------------------------------------------------------------

_PSIONIC_SHEET = "Psionic Info"

#: Each manifesting class's key ability is encoded on the "Psionic Info" sheet
#: as a formula in column G (``=PIInt``/``=PIWis``/``=PICha``) referencing the
#: relevant ability named range.  Reading the formula text is the only way to
#: recover the mapping, since a value-only load resolves these to a score.
_PSIONIC_KEY_ABILITY_TOKENS: dict[str, str] = {
    "PIInt": "INT",
    "PIWis": "WIS",
    "PICha": "CHA",
}


def _optional_int(value: object) -> int | None:
    """Return *value* as an int, or ``None`` if it is blank/non-integral."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    text = str(value).strip()
    if text == "":
        return None
    try:
        numeric = float(text)
    except (TypeError, ValueError):
        return None
    return int(numeric) if math.isfinite(numeric) and numeric.is_integer() else None


def _psionic_key_abilities(grid: list[tuple[object, ...]]) -> dict[str, str]:
    """Map each manifesting class to its key ability via column G formulas.

    Reads the class roster in cells ``A4:A12`` of the "Psionic Info" sheet and
    classifies each by the ability named range referenced in column G.
    """
    abilities: dict[str, str] = {}
    for row in grid:
        if len(row) < 7:
            continue
        name, formula = row[0], row[6]
        if not isinstance(name, str) or not isinstance(formula, str):
            continue
        cls = name.strip()
        if not cls:
            continue
        for token, ability in _PSIONIC_KEY_ABILITY_TOKENS.items():
            if token in formula:
                abilities[cls] = ability
                break
    return abilities


def _is_psionic_block_header(row: tuple[object, ...], col: int) -> bool:
    """Return whether the sub-header at *col* marks a PP/Day progression block."""
    if col + 1 >= len(row):
        return False
    level = row[col]
    pp = row[col + 1]
    return (
        isinstance(level, str)
        and level.strip().lower().startswith("level")
        and isinstance(pp, str)
        and pp.strip() == "PP/Day"
    )


def _extract_psionic_progression(wb: object) -> list[tuple[object, ...]]:
    """Extract per-class psionic power-point progressions from the workbook.

    The "Psionic Info" sheet lays out one ``Level``/``PP/Day``/``Known`` block
    per manifesting class (Excel tab 7b).  Returns ``(class_name, key_ability,
    manifester_level, power_points, powers_known)`` tuples transcribed directly
    from those blocks.  Must be read from a formula-mode workbook so the
    key-ability formulas in column G are available.
    """
    ws = wb[_PSIONIC_SHEET]  # type: ignore[index]
    grid = [tuple(r) for r in ws.iter_rows(values_only=True)]  # type: ignore[attr-defined]
    abilities = _psionic_key_abilities(grid)

    rows: list[tuple[object, ...]] = []
    for r_idx, row in enumerate(grid):
        for c_idx, cell in enumerate(row):
            cls = cell.strip() if isinstance(cell, str) else ""
            if cls not in abilities:
                continue
            if r_idx + 1 >= len(grid) or not _is_psionic_block_header(
                grid[r_idx + 1], c_idx
            ):
                continue
            key_ability = abilities[cls]
            for d_idx in range(r_idx + 2, len(grid)):
                data = grid[d_idx]
                level = _optional_int(data[c_idx]) if c_idx < len(data) else None
                if level is None:
                    break  # blank separator terminates the block
                power_points = (
                    _optional_int(data[c_idx + 1]) if c_idx + 1 < len(data) else None
                )
                powers_known = (
                    _optional_int(data[c_idx + 2]) if c_idx + 2 < len(data) else None
                )
                rows.append(
                    (
                        cls,
                        key_ability,
                        level,
                        power_points or 0,
                        powers_known or 0,
                    )
                )
    return rows


# ---------------------------------------------------------------------------
# Workbook table registry
#
# ``columns`` lists the destination columns (in tuple order).  ``unique_by``
# names the column(s) backed by a UNIQUE constraint in ``schema.py``; it is
# used by tests to verify persisted row counts against the source workbook
# using the same UNIQUE-key deduplication semantics as SQLite.
# ---------------------------------------------------------------------------


class _WorkbookTable:
    """Specification binding a workbook sheet to a destination table."""

    def __init__(
        self,
        table: str,
        sheet: str,
        columns: tuple[str, ...],
        extractor: Callable[[object], list[tuple[object, ...]]],
        unique_by: tuple[str, ...] | None = None,
    ) -> None:
        self.table = table
        self.sheet = sheet
        self.columns = columns
        self.extractor = extractor
        self.unique_by = unique_by


_WORKBOOK_TABLES: tuple[_WorkbookTable, ...] = (
    _WorkbookTable(
        "sources",
        "Sources",
        ("abbreviation", "full_name"),
        _extract_sources,
        unique_by=("abbreviation",),
    ),
    _WorkbookTable(
        "languages",
        "Languages",
        ("name", "typical_speakers", "script"),
        _extract_languages,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "skills",
        "Skills",
        ("name", "key_ability", "trained_only", "armor_check_penalty", "description"),
        _extract_skills,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "skill_footnotes",
        "Skills",
        ("skill_name", "raw_name", "marker"),
        _extract_skill_footnotes,
        unique_by=("skill_name", "marker"),
    ),
    _WorkbookTable(
        "skill_footnote_definitions",
        "Character Sheet I",
        ("source_sheet", "marker", "description"),
        _extract_skill_footnote_definitions,
        unique_by=("source_sheet", "marker"),
    ),
    _WorkbookTable(
        "skill_tricks",
        "Skill Tricks",
        ("name", "cost", "description", "prerequisite"),
        _extract_skill_tricks,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "traits",
        "Traits",
        ("name", "description", "benefit", "drawback", "source"),
        _extract_traits,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "flaws",
        "Flaws",
        ("name", "description", "effect", "source"),
        _extract_flaws,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "variants",
        "Variants",
        ("name", "base_class", "description", "source"),
        _extract_variants,
    ),
    _WorkbookTable(
        "domains",
        "Domains",
        (
            "name",
            "granted_power",
            "spell_1",
            "spell_2",
            "spell_3",
            "spell_4",
            "spell_5",
            "spell_6",
            "spell_7",
            "spell_8",
            "spell_9",
        ),
        _extract_domains,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "deities",
        "Deities",
        ("name", "alignment", "domains", "favored_weapon", "source"),
        _extract_deities,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "feats",
        "Feats",
        ("name", "type", "description", "benefit", "special", "source"),
        _extract_feats,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "feat_prerequisites",
        "Feats",
        ("feat_name", "prerequisite"),
        _extract_feat_prerequisites,
    ),
    _WorkbookTable(
        "armor",
        "Armor",
        (
            "name",
            "type",
            "ac_bonus",
            "max_dex_bonus",
            "check_penalty",
            "arcane_spell_failure",
            "speed_30",
            "speed_20",
            "weight",
            "source",
        ),
        _extract_armor,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "maneuvers",
        "Maneuvers & Stances",
        (
            "name",
            "discipline",
            "level",
            "type",
            "initiation_action",
            "range",
            "target",
            "duration",
            "description",
            "source",
        ),
        _extract_maneuvers,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "grafts",
        "Grafts",
        ("name", "type", "body_slot", "description", "source"),
        _extract_grafts,
    ),
    _WorkbookTable(
        "graft_abilities",
        "Graft Abilities",
        ("graft_name", "ability_name", "description"),
        _extract_graft_abilities,
    ),
    _WorkbookTable(
        "racial_abilities",
        "Racial Abilities",
        ("race_name", "ability_name", "description"),
        _extract_racial_abilities,
    ),
    _WorkbookTable(
        "incarnum_abilities",
        "Incarnum Abilities",
        ("name", "class_name", "feat_name", "description"),
        _extract_incarnum_abilities,
    ),
    _WorkbookTable(
        "vestiges",
        "Binder Vestiges",
        ("name", "level", "sign", "influence", "granted_abilities", "source"),
        _extract_vestiges,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "marshal_auras",
        "Marshal Auras",
        ("name", "type", "bonus_type", "description"),
        _extract_marshal_auras,
    ),
    _WorkbookTable(
        "familiar_master_abilities",
        "Class Abilities",
        ("name", "description", "sort_order"),
        _extract_familiar_master_abilities,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "soulmelds",
        "SoulmeldsInfo",
        (
            "name",
            "descriptors",
            "chakra",
            "essentia_capacity",
            "bind_dc",
            "description",
            "source",
        ),
        _extract_soulmelds,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "soulmeld_abilities",
        "SoulmeldAbilities",
        ("soulmeld_name", "chakra", "essentia", "description"),
        _extract_soulmeld_abilities,
    ),
    _WorkbookTable(
        "buffs",
        "Buffs",
        ("name", "category", "spell_level", "bonus_type", "description", "source"),
        _extract_buffs,
        unique_by=("name", "category"),
    ),
    _WorkbookTable(
        "races",
        "Race Info",
        ("name",),
        _extract_races,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "templates",
        "Template Info",
        ("name", "type_change", "subtype_added"),
        _extract_templates,
        unique_by=("name",),
    ),
    _WorkbookTable(
        "spells_per_day",
        "Spells per Day",
        ("class_name", "caster_level", "spell_level", "slots"),
        _extract_spells_per_day,
    ),
    _WorkbookTable(
        "spells_known",
        "Spells Known",
        ("class_name", "caster_level", "spell_level", "count"),
        _extract_spells_known,
    ),
)


def _seed_workbook_table(
    conn: sqlite3.Connection, wb: object, spec: _WorkbookTable
) -> None:
    """Populate a single workbook-backed table from *wb* per *spec*.

    Rows are extracted first, then the destination table is replaced in full:
    existing rows are deleted and fresh workbook rows inserted.  This mirrors
    the original workbook-first application model where each seed run
    regenerates these reference tables from workbook data.  Inserts that
    violate constraints are skipped and logged.
    """
    try:
        rows = spec.extractor(wb)
    except KeyError:
        logger.warning(
            "Sheet %r not found in workbook – skipping %s",
            spec.sheet,
            spec.table,
        )
        return

    # Table and column names cannot be passed as SQL bind parameters, so they
    # are interpolated below.  They originate from the hardcoded
    # ``_WORKBOOK_TABLES`` registry, but validate them as plain SQL identifiers
    # for defense in depth before any interpolation.
    if not _is_sql_identifier(spec.table) or not all(
        _is_sql_identifier(col) for col in spec.columns
    ):
        raise ValueError(f"Invalid table/column identifier for {spec.table!r}")

    placeholders = ", ".join("?" for _ in spec.columns)
    column_list = ", ".join(spec.columns)
    statement = f"INSERT INTO {spec.table} ({column_list}) VALUES ({placeholders})"

    conn.execute(f"DELETE FROM {spec.table}")
    inserted = 0
    skipped = 0
    for values in rows:
        try:
            conn.execute(statement, values)
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping %s row %r: %s", spec.table, values, exc)
            skipped += 1

    conn.commit()
    stored = conn.execute(f"SELECT COUNT(*) FROM {spec.table}").fetchone()[0]
    if skipped:
        logger.warning(
            "%s: skipped %d source rows due to insert errors (see debug logs)",
            spec.table,
            skipped,
        )
    logger.info(
        "%s: stored %d rows from sheet %r (processed %d, skipped %d)",
        spec.table,
        stored,
        spec.sheet,
        inserted,
        skipped,
    )


def seed_workbook(
    conn: sqlite3.Connection,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
    workbook: openpyxl.Workbook | None = None,
) -> None:
    """Seed every workbook-backed table from the reference ``.xlsm`` file.

    Reads ``HeroForge Anew 3.5 v7.4.0.1.xlsm`` (see ``docs/conversion-plan.md``
    §6.3 and §13) via :mod:`openpyxl` and populates each table declared in
    :data:`_WORKBOOK_TABLES`.  If the workbook is missing the function logs a
    warning and returns without modifying any tables.
    """
    wb = workbook
    owns_workbook = wb is None
    if wb is None:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            logger.warning(
                "Workbook not found at %s – skipping workbook-backed tables",
                workbook_path,
            )
            return
        logger.info("Loading workbook %s", workbook_path.name)
        wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)

    try:
        for spec in _WORKBOOK_TABLES:
            _seed_workbook_table(conn, wb, spec)
    finally:
        if owns_workbook:
            wb.close()


# ---------------------------------------------------------------------------
# Per-table seed functions
# ---------------------------------------------------------------------------

#: ``WeaponInfo.csv`` encodes weapon damage as an integer *step code* on the
#: D&D 3.5 weapon-damage progression rather than a literal die expression.  The
#: canonical, size-aware decode lives in the workbook's "Class Weapons & Armor"
#: sheet as a 2-D matrix (base damage × creature size); it is seeded into the
#: :data:`weapon_damage <heroforge.db.game_schema>` table by
#: :func:`seed_weapon_damage` and read back here, replacing what used to be a
#: hand-transcribed in-code constant.
#:
#: The matrix occupies cells ``K4:S20`` (the ``TblWeaponDamage`` named range)
#: with the size headers on row 3 (``K3:S3`` / ``TblWeaponSizeLookup``); a
#: weapon's ``Dmg1(M)`` step code is the 1-based row offset into that range, so
#: ``INDEX(TblWeaponDamage, step_code, size_column)`` yields the size-adjusted
#: die (verified against canonical weapons such as Dagger=1d4, Longsword=1d8,
#: Greataxe=1d12, Greatsword=2d6).
_WEAPON_DAMAGE_SHEET = "Class Weapons & Armor"
_WEAPON_DAMAGE_HEADER_ROW = 3
_WEAPON_DAMAGE_LAST_ROW = 20
_WEAPON_DAMAGE_FIRST_COL = 11  # column K (Fine)
_WEAPON_DAMAGE_LAST_COL = 19  # column S (Colossal)
_MEDIUM_SIZE = "Medium"


def _extract_weapon_damage(wb: object) -> list[tuple[object, ...]]:
    """Extract the size-aware weapon-damage matrix from the workbook.

    Returns ``(step_code, size, damage)`` tuples drawn from the
    ``TblWeaponDamage`` named range (``K4:S20``) on the "Class Weapons & Armor"
    sheet.  Cells that are empty (a weapon too small to deal damage at that
    creature size) are skipped.  The step code is the 1-based row offset into
    the matrix, matching the ``INDEX(TblWeaponDamage, step_code, …)`` lookup the
    workbook uses to decode ``WeaponInfo.csv`` ``Dmg1(M)`` codes.
    """
    ws = wb[_WEAPON_DAMAGE_SHEET]  # type: ignore[index]
    rows = list(
        ws.iter_rows(  # type: ignore[attr-defined]
            min_row=_WEAPON_DAMAGE_HEADER_ROW,
            max_row=_WEAPON_DAMAGE_LAST_ROW,
            min_col=_WEAPON_DAMAGE_FIRST_COL,
            max_col=_WEAPON_DAMAGE_LAST_COL,
            values_only=True,
        )
    )
    if not rows:
        return []

    sizes = [_cell_value(value) for value in rows[0]]
    extracted: list[tuple[object, ...]] = []
    for offset, row in enumerate(rows[1:], start=1):
        step_code = offset  # row 4 → step 1, row 5 → step 2, …
        # ``sizes`` and ``row`` are sliced from the same K:S column range, so
        # they always share a width; ``strict`` turns any future layout drift
        # into a loud error instead of silently dropping cells.
        for size, cell in zip(sizes, row, strict=True):
            damage = _cell_value(cell)
            if not size or not damage:
                continue
            extracted.append((step_code, size, damage))
    return extracted


def seed_weapon_damage(
    conn: sqlite3.Connection,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
    workbook: openpyxl.Workbook | None = None,
) -> None:
    """Seed the *weapon_damage* table from the workbook damage-by-size matrix.

    This must run before :func:`seed_weapons` so the latter can decode each
    weapon's Medium-size damage from the database rather than a hand-maintained
    constant.  If the workbook is missing the function logs a warning and leaves
    the table untouched.
    """
    wb = workbook
    owns_workbook = wb is None
    if wb is None:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            logger.warning(
                "Workbook not found at %s – skipping weapon_damage matrix",
                workbook_path,
            )
            return
        wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)
    try:
        rows = _extract_weapon_damage(wb)
    except KeyError:
        logger.warning(
            "Sheet %r not found in workbook – skipping weapon_damage",
            _WEAPON_DAMAGE_SHEET,
        )
        return
    finally:
        if owns_workbook:
            wb.close()

    if not rows:
        logger.warning(
            "No weapon_damage rows extracted from workbook – leaving table untouched"
        )
        return

    conn.execute("DELETE FROM weapon_damage")
    inserted = 0
    skipped = 0
    for values in rows:
        try:
            conn.execute(
                "INSERT INTO weapon_damage (step_code, size, damage) "
                "VALUES (?, ?, ?)",
                values,
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping weapon_damage row %r: %s", values, exc)
            skipped += 1
    conn.commit()
    logger.info("weapon_damage: inserted %d rows, skipped %d", inserted, skipped)
    if skipped:
        logger.warning(
            "weapon_damage: %d row(s) skipped – matrix may be incomplete", skipped
        )


def seed_psionic_progression(
    conn: sqlite3.Connection,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
    workbook: openpyxl.Workbook | None = None,
) -> None:
    """Seed the *psionic_progression* table from the "Psionic Info" sheet.

    Replaces the table in full with the per-class power-point-per-day and
    powers-known progressions transcribed from the workbook (Excel tab 7b),
    including each class's key ability.  The workbook is loaded in formula mode
    so the key-ability formulas in column G are readable.  Callers may pass an
    already-open formula-mode ``workbook`` to avoid re-parsing the ``.xlsm``;
    when omitted the workbook is loaded (and closed) here.  If the workbook is
    missing the function logs a warning and leaves the table untouched.
    """
    wb = workbook
    owns_workbook = wb is None
    if wb is None:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            logger.warning(
                "Workbook not found at %s – skipping psionic_progression",
                workbook_path,
            )
            return
        wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=False)
    try:
        rows = _extract_psionic_progression(wb)
    except KeyError:
        logger.warning(
            "Sheet %r not found in workbook – skipping psionic_progression",
            _PSIONIC_SHEET,
        )
        return
    finally:
        if owns_workbook:
            wb.close()

    if not rows:
        logger.warning(
            "No psionic_progression rows extracted from workbook – "
            "leaving table untouched"
        )
        return

    conn.execute("DELETE FROM psionic_progression")
    inserted = 0
    skipped = 0
    for values in rows:
        try:
            conn.execute(
                "INSERT INTO psionic_progression "
                "(class_name, key_ability, manifester_level, power_points, "
                "powers_known) VALUES (?, ?, ?, ?, ?)",
                values,
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping psionic_progression row %r: %s", values, exc)
            skipped += 1
    conn.commit()
    logger.info("psionic_progression: inserted %d rows, skipped %d", inserted, skipped)


def _load_medium_weapon_damage(conn: sqlite3.Connection) -> dict[int, str]:
    """Return the Medium-size ``{step_code: die}`` map from *weapon_damage*."""
    return {
        int(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT step_code, damage FROM weapon_damage WHERE size = ?",
            (_MEDIUM_SIZE,),
        )
    }


def _decode_weapon_damage(code: str, damage_by_step: dict[int, str]) -> str:
    """Translate a ``WeaponInfo.csv`` damage *code* into a die expression.

    *damage_by_step* maps each Medium-size step code to its die (loaded from the
    seeded ``weapon_damage`` table via :func:`_load_medium_weapon_damage`).
    Blank codes yield an empty string; references to other cells (e.g.
    ``ref:UnarmedStrikeDamage``) and codes absent from the matrix are passed
    through unchanged so the source value is never silently lost.
    """
    code = (code or "").strip()
    if not code:
        return ""
    try:
        step = int(float(code))
    except (TypeError, ValueError):
        return code  # e.g. "ref:UnarmedStrikeDamage" – preserve verbatim
    return damage_by_step.get(step, code)


def _format_weapon_critical(threat: str, multiplier: str) -> str:
    """Build a ``19-20/×2`` style critical string from threat/multiplier codes.

    ``threat`` is the lowest natural roll that threatens a critical (20 means
    only a natural 20) and ``multiplier`` is the damage multiplier (2, 3, …).
    Missing pieces degrade gracefully so partial source data still produces a
    sensible string.
    """
    threat_i = _safe_int(threat, default=20) or 20
    mult_i = _safe_int(multiplier, default=2) or 2
    threat_part = "" if threat_i >= 20 else f"{threat_i}-20/"
    return f"{threat_part}×{mult_i}"


def seed_weapons(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``WeaponInfo.csv`` into the *weapons* table.

    The CSV stores damage as a step code on the 3.5 damage progression and the
    critical as separate threat/multiplier columns; both are decoded here into
    the human-readable forms the Attacks tab displays.
    """
    csv_path = data_dir / "WeaponInfo.csv"
    if not csv_path.exists():
        logger.warning("WeaponInfo.csv not found at %s – skipping weapons", csv_path)
        return

    inserted = 0
    skipped = 0
    medium_damage = _load_medium_weapon_damage(conn)
    if not medium_damage:
        logger.warning(
            "weapon_damage table has no %s rows; skipping weapon seeding "
            "to prevent persisting raw damage step codes",
            _MEDIUM_SIZE,
        )
        return
    with csv_path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (
                row.get("Select A Weapon") or row.get("Name") or row.get("name") or ""
            ).strip()
            if not name or name == "Select A Weapon":
                skipped += 1
                continue
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO weapons
                        (name, category, size, damage_small, damage_medium,
                         critical, range_increment, weight, damage_type, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        (
                            row.get("Cat")
                            or row.get("Category")
                            or row.get("category")
                            or ""
                        ).strip(),
                        (row.get("Size") or row.get("size") or "").strip(),
                        # The current source file has no Small-size damage
                        # column; the fallbacks support tidy exports that may
                        # supply one via "Damage (S)" or "damage_small".
                        (
                            row.get("Damage (S)") or row.get("damage_small") or ""
                        ).strip(),
                        _decode_weapon_damage(
                            row.get("Dmg1(M)")
                            or row.get("Damage (M)")
                            or row.get("damage_medium")
                            or "",
                            medium_damage,
                        ),
                        # Honour a pre-formatted critical column if one is present,
                        # otherwise build it from the threat/multiplier codes.
                        (row.get("Critical") or row.get("critical") or "").strip()
                        or _format_weapon_critical(
                            row.get("Threat") or "", row.get("Crit1") or ""
                        ),
                        _safe_int(
                            row.get("Range")
                            or row.get("Range Increment")
                            or row.get("range_increment")
                        ),
                        _safe_float(
                            row.get("Wgt") or row.get("Weight") or row.get("weight")
                        ),
                        (row.get("Type") or row.get("damage_type") or "").strip(),
                        (row.get("Source") or row.get("source") or "").strip(),
                    ),
                )
                inserted += 1
            except sqlite3.Error as exc:
                logger.debug("Skipping weapon row %r: %s", name, exc)
                skipped += 1

    conn.commit()
    logger.info("Weapons: inserted/replaced %d rows, skipped %d", inserted, skipped)


def seed_creatures(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``CreatureInfo.csv`` into the *creatures* table.

    Each row is a full creature/race stat block (the source of wild-shape
    forms, animal companions and familiars).  The creature name lives in the
    ``Race`` column and the listed AC contribution is the ``Natural Armor``
    value.  Header/placeholder rows ("Select a Race/Creature", "Custom Race")
    are skipped.
    """
    csv_path = data_dir / "CreatureInfo.csv"
    if not csv_path.exists():
        logger.warning(
            "CreatureInfo.csv not found at %s – skipping creatures", csv_path
        )
        return

    inserted = 0
    skipped = 0
    with csv_path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("Race") or row.get("Name") or row.get("name") or "").strip()
            if not name or name in (
                "Select a Race/Creature",
                "Custom Race",
            ):
                skipped += 1
                continue
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO creatures
                        (name, size, type, subtype, hit_dice,
                         str_score, dex_score, con_score,
                         int_score, wis_score, cha_score,
                         bab, grapple_mod, natural_armor, speed, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        (row.get("Size") or row.get("size") or "").strip(),
                        (row.get("Type") or row.get("type") or "").strip(),
                        (row.get("Subtype") or row.get("subtype") or "").strip(),
                        (row.get("HD") or row.get("hit_dice") or "").strip(),
                        _safe_int(
                            row.get("Str") or row.get("STR") or row.get("str_score")
                        ),
                        _safe_int(
                            row.get("Dex") or row.get("DEX") or row.get("dex_score")
                        ),
                        _safe_int(
                            row.get("Con") or row.get("CON") or row.get("con_score")
                        ),
                        _safe_int(
                            row.get("Int") or row.get("INT") or row.get("int_score")
                        ),
                        _safe_int(
                            row.get("Wis") or row.get("WIS") or row.get("wis_score")
                        ),
                        _safe_int(
                            row.get("Cha") or row.get("CHA") or row.get("cha_score")
                        ),
                        (row.get("BAB") or row.get("bab") or "").strip(),
                        _safe_int(row.get("Grapple") or row.get("grapple_mod")),
                        _safe_int(
                            row.get("Natural Armor")
                            or row.get("AC")
                            or row.get("armor_class")
                        ),
                        (
                            row.get("Land")
                            or row.get("Speed")
                            or row.get("speed")
                            or ""
                        ).strip(),
                        (
                            row.get("Src")
                            or row.get("Source")
                            or row.get("source")
                            or ""
                        ).strip(),
                    ),
                )
                inserted += 1
            except sqlite3.Error as exc:
                logger.debug("Skipping creature row %r: %s", name, exc)
                skipped += 1

    conn.commit()
    logger.info("Creatures: inserted/replaced %d rows, skipped %d", inserted, skipped)


def _is_numeric_str(value: str) -> bool:
    """Return ``True`` if *value* parses as an int or float."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def seed_tables(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``Tables.csv`` into the *tables* table.

    ``Tables.csv`` is not a tidy ``(table, key, value)`` export: it is a wide
    spreadsheet grid in which many independent lookup tables (experience,
    carrying capacity, point-buy costs, alignment components, …) sit side by
    side, and some columns even stack several tables vertically.  Each
    contiguous run of cells in a column is treated as one logical table: a
    textual leading cell names the table and the remaining cells are its
    values, while a number-led run is captured under a ``Column N`` name.  The
    source row/column coordinates form the key so every cell migrates exactly
    once with no loss.

    A normalised ``TableName,Key,Value`` file is still honoured if supplied.
    """
    csv_path = data_dir / "Tables.csv"
    if not csv_path.exists():
        logger.warning("Tables.csv not found at %s – skipping tables", csv_path)
        return

    with csv_path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        grid = [[(cell or "").strip() for cell in row] for row in csv.reader(fh)]

    inserted = 0
    skipped = 0

    def _store(table_name: str, key: str, value: str) -> None:
        nonlocal inserted, skipped
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tables (table_name, key, value)
                VALUES (?, ?, ?)
                """,
                (table_name, key, value),
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping table row %r/%r: %s", table_name, key, exc)
            skipped += 1

    # Tidy ``TableName,Key,Value`` form (kept for forward/backward compatibility).
    header = grid[0] if grid else []
    normalized_header = [re.sub(r"[^a-z0-9]+", "", col.lower()) for col in header[:3]]
    if normalized_header in (
        ["tablename", "key", "value"],
        ["table_name", "key", "value"],
    ):
        for row in grid[1:]:
            table_name = row[0].strip() if len(row) > 0 else ""
            key = row[1].strip() if len(row) > 1 else ""
            value = row[2].strip() if len(row) > 2 else ""
            if not table_name or not key:
                skipped += 1
                continue
            _store(table_name, key, value)
    else:
        # Wide multi-table grid: walk each column run by run.
        n_rows = len(grid)
        n_cols = max((len(r) for r in grid), default=0)
        for c in range(n_cols):
            column = [grid[r][c] if c < len(grid[r]) else "" for r in range(n_rows)]
            r = 0
            while r < n_rows:
                if not column[r]:
                    r += 1
                    continue
                start = r
                while r < n_rows and column[r]:
                    r += 1
                run = column[start:r]
                if _is_numeric_str(run[0]):
                    table_name = f"Column {c}"
                    value_rows = range(start, r)
                    values = run
                else:
                    table_name = run[0]
                    value_rows = range(start + 1, r)
                    values = run[1:]
                for row_idx, value in zip(value_rows, values):
                    _store(table_name, f"{c}:{row_idx}", value)

    conn.commit()
    logger.info("Tables: inserted/replaced %d rows, skipped %d", inserted, skipped)


def _bab_progression(factor: object) -> str:
    """Map a ``ClassInfo`` BAB factor (1 / 0.75 / 0.5) to a progression name."""
    f = _safe_float(factor, default=-1.0)
    if f < 0:
        return ""
    if f >= 0.95:
        return "fast"
    if f >= 0.7:
        return "medium"
    return "slow"


def _save_progression(factor: object) -> str:
    """Map a ``ClassInfo`` save factor (0.5 good / 0.34 poor) to its name."""
    f = _safe_float(factor, default=-1.0)
    if f < 0:
        return ""
    return "good" if f >= 0.45 else "poor"


#: The ``ClassInfo`` header lives within the first few rows; scan a small,
#: fixed window rather than the whole sheet when locating it.
_CLASS_HEADER_SEARCH_ROWS = 6

#: Non-class placeholder rows present in ``ClassInfo.xlsx`` that must be skipped.
_CLASS_PLACEHOLDER_NAMES = frozenset({"Select Class", "N/A", "<custom-defined class>"})


def seed_classes(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``ClassInfo.xlsx`` into *classes* (and *class_skills*).

    ``ClassInfo.xlsx`` is a single wide sheet: the class name sits in the
    unlabelled column to the left of the ``Abr`` header, the BAB/save columns
    (``fBAB``/``fFort``/``fRef``/``fWill``) hold numeric progression factors,
    a wide block of per-skill columns marks class skills with a ``2``, and the
    ``Light``..``Other Weapons`` columns mirror the "Class Weapons & Armor"
    proficiencies (used to populate *class_weapons_armor*).
    Section-divider rows (``– … –``) toggle whether following classes are
    prestige classes, and placeholder rows (``Select Class``, ``N/A``,
    ``<custom-defined class>``) are skipped.
    """
    xlsx_path = data_dir / "ClassInfo.xlsx"
    if not xlsx_path.exists():
        logger.warning("ClassInfo.xlsx not found at %s – skipping classes", xlsx_path)
        return

    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)

    inserted_classes = 0
    inserted_skills = 0
    inserted_profs = 0
    skipped = 0

    try:
        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue

            # Locate the header row (the one carrying both "Abr" and "Skill Pts").
            headers: list[str] = []
            for candidate in rows[:_CLASS_HEADER_SEARCH_ROWS]:
                labels = [str(h).strip() if h is not None else "" for h in candidate]
                if "Abr" in labels and "Skill Pts" in labels:
                    headers = labels
                    break
            if not headers:
                continue

            def hidx(label: str) -> int:
                return headers.index(label) if label in headers else -1

            abr_idx = hidx("Abr")
            name_idx = abr_idx - 1 if abr_idx > 0 else -1
            sp_idx = hidx("Skill Pts")
            hd_idx = hidx("HD Type")
            bab_idx = hidx("fBAB")
            fort_idx = hidx("fFort")
            ref_idx = hidx("fRef")
            will_idx = hidx("fWill")
            source_idx = hidx("Reference")

            # Armor/shield/weapon proficiency flags (the "Class Weapons & Armor"
            # data mirrored into ClassInfo).  Each flag column holds ``True`` when
            # the class is proficient; the "Other Weapons" column is a
            # ``;``-separated list of individually granted weapon proficiencies.
            prof_flag_cols: list[tuple[int, str]] = [
                (hidx("Light"), "Light armor"),
                (hidx("Med"), "Medium armor"),
                (hidx("Heavy"), "Heavy armor"),
                (hidx("Shield"), "Shields"),
                (hidx("Tower"), "Tower shields"),
                (hidx("Simple"), "Simple weapons"),
                (hidx("Martial"), "Martial weapons"),
            ]
            other_weapons_idx = hidx("Other Weapons")

            # The per-skill block runs from "Appraise" up to (but excluding)
            # "Reference"; ignore "… "-suffixed category separators.
            skill_cols: list[tuple[int, str]] = []
            start = hidx("Appraise")
            end = source_idx if source_idx != -1 else len(headers)
            if start != -1:
                for i in range(start, end):
                    label = headers[i] if i < len(headers) else ""
                    if label and "…" not in label:
                        skill_cols.append((i, label))

            def cell(row_data: tuple, idx: int) -> str:
                if idx < 0 or idx >= len(row_data):
                    return ""
                val = row_data[idx]
                return str(val).strip() if val is not None else ""

            is_prestige = 0
            for row_data in rows:
                if all(v is None for v in row_data):
                    continue
                name = cell(row_data, name_idx)
                if not name:
                    continue
                # Section dividers (e.g. "– Prestige Classes DMG –") set context
                # for the classes that follow but are not classes themselves.
                if name.startswith("–"):
                    is_prestige = 1 if "prestige" in name.lower() else 0
                    continue
                # Skip placeholders / non-class rows (these have no abbreviation or
                # are explicit placeholders in the source sheet).
                if not cell(row_data, abr_idx) or name in _CLASS_PLACEHOLDER_NAMES:
                    skipped += 1
                    continue
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO classes
                            (name, is_prestige, hit_die, bab_progression,
                             fort_progression, ref_progression, will_progression,
                             skill_points_per_level, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            is_prestige,
                            _safe_int(cell(row_data, hd_idx)),
                            _bab_progression(cell(row_data, bab_idx)),
                            _save_progression(cell(row_data, fort_idx)),
                            _save_progression(cell(row_data, ref_idx)),
                            _save_progression(cell(row_data, will_idx)),
                            _safe_int(cell(row_data, sp_idx)),
                            cell(row_data, source_idx),
                        ),
                    )
                    inserted_classes += 1

                    # Weapon & armor proficiencies for this class.  Cleared first
                    # so repeated seeding stays idempotent (the table has no
                    # UNIQUE key of its own).
                    conn.execute(
                        "DELETE FROM class_weapons_armor WHERE class_name = ?",
                        (name,),
                    )
                    proficiencies = [
                        label
                        for idx, label in prof_flag_cols
                        if cell(row_data, idx).lower() == "true"
                    ]
                    proficiencies.extend(
                        part.strip()
                        for part in cell(row_data, other_weapons_idx).split(";")
                        if part.strip()
                    )
                    for proficiency in proficiencies:
                        try:
                            conn.execute(
                                "INSERT INTO class_weapons_armor "
                                "(class_name, proficiency) VALUES (?, ?)",
                                (name, proficiency),
                            )
                            inserted_profs += 1
                        except sqlite3.Error:
                            pass

                    # A skill cell value of "2" marks a class skill for this class.
                    for idx, skill_name in skill_cols:
                        if cell(row_data, idx) == "2":
                            try:
                                conn.execute(
                                    """
                                    INSERT OR REPLACE INTO class_skills
                                        (class_name, skill_name)
                                    VALUES (?, ?)
                                    """,
                                    (name, skill_name),
                                )
                                inserted_skills += 1
                            except sqlite3.Error:
                                pass

                except sqlite3.Error as exc:
                    logger.debug("Skipping class row %r: %s", name, exc)
                    skipped += 1

        conn.commit()
    finally:
        wb.close()
    logger.info(
        "Classes: inserted/replaced %d class rows, %d skill rows, "
        "%d weapon/armor proficiency rows, skipped %d",
        inserted_classes,
        inserted_skills,
        inserted_profs,
        skipped,
    )


# ---------------------------------------------------------------------------
# Code-defined reference seeding helpers
# ---------------------------------------------------------------------------


def _extract_skill_synergies(wb: object) -> list[tuple[object, ...]]:
    """Extract the unconditional ``(from_skill, to_skill)`` synergy pairs.

    Parses the "Synergy" column (GQ) on the workbook's "Skills" sheet: each
    cell's formula references ``Sk<Name>Ranks>=5`` for every source skill that
    grants the row's skill a +2 synergy bonus (PHB p65).  The source skills are
    mapped back to their canonical names (as seeded into the ``skills`` table),
    and the row's own skill name is the bonus target.

    Returns ``(from_skill, to_skill, bonus, condition)`` tuples with a ``None``
    condition, so only the always-on synergies are seeded; circumstance-specific
    synergies are handled elsewhere in the workbook and are intentionally
    excluded from this flat table.
    """
    ws = wb[_SKILL_SYNERGY_SHEET]  # type: ignore[index]
    sheet_rows = _sheet_rows(ws, _SKILL_DATA_START_ROW)

    # Map each skill's ``Sk<Name>Ranks`` key back to its canonical name so the
    # formula references can be resolved to seeded skill names.
    name_by_key: dict[str, str] = {}
    for row in sheet_rows:
        raw_name = _col(row, "A")
        if not raw_name or raw_name.upper() == "SKILL NAME":
            continue
        name = _strip_footnotes(raw_name)
        if name:
            name_by_key.setdefault(_normalize_skill_key(name), name)

    extracted: list[tuple[object, ...]] = []
    for row in sheet_rows:
        raw_name = _col(row, "A")
        if not raw_name or raw_name.upper() == "SKILL NAME":
            continue
        to_skill = _strip_footnotes(raw_name)
        formula = (
            row[_SKILL_SYNERGY_COLUMN_INDEX]
            if len(row) > _SKILL_SYNERGY_COLUMN_INDEX
            else None
        )
        if not (to_skill and isinstance(formula, str)):
            continue
        compact_formula = formula.replace(" ", "")
        for match in _SKILL_SYNERGY_SOURCE_RE.finditer(compact_formula):
            from_skill = name_by_key.get(_normalize_skill_key(match.group(1)))
            if not from_skill:
                logger.warning(
                    "Unknown synergy source %r for skill %r", match.group(1), to_skill
                )
                continue
            extracted.append((from_skill, to_skill, _SKILL_SYNERGY_BONUS, None))
    return extracted


def seed_skill_synergies(
    conn: sqlite3.Connection,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
    workbook: openpyxl.Workbook | None = None,
) -> None:
    """Seed the *skill_synergies* table from the workbook "Synergy" column.

    The pairs are parsed from cell formulas (see :func:`_extract_skill_synergies`),
    so the workbook is opened with ``data_only=False`` to expose them.  Callers
    may pass an already-open formula-mode ``workbook`` to avoid re-parsing the
    ``.xlsm``; when omitted the workbook is loaded (and closed) here.  If the
    workbook is missing the function logs a warning and leaves the table
    untouched.
    """
    wb = workbook
    owns_workbook = wb is None
    if wb is None:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            logger.warning(
                "Workbook not found at %s – skipping skill_synergies",
                workbook_path,
            )
            return
        wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=False)
    try:
        rows = _extract_skill_synergies(wb)
    except KeyError:
        logger.warning(
            "Sheet %r not found in workbook – skipping skill_synergies",
            _SKILL_SYNERGY_SHEET,
        )
        return
    finally:
        if owns_workbook:
            wb.close()

    if not rows:
        logger.warning(
            "No skill_synergies rows extracted from workbook – leaving table untouched"
        )
        return

    conn.execute("DELETE FROM skill_synergies")
    inserted = 0
    skipped = 0
    for values in rows:
        try:
            conn.execute(
                "INSERT INTO skill_synergies (from_skill, to_skill, bonus, condition) "
                "VALUES (?, ?, ?, ?)",
                values,
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping skill_synergies row %r: %s", values, exc)
            skipped += 1
    conn.commit()
    logger.info("skill_synergies: inserted %d rows, skipped %d", inserted, skipped)


def seed_familiar_bonuses(conn: sqlite3.Connection) -> None:
    """Insert the standard-familiar master-bonus rows into ``familiar_bonuses``.

    The data is the structured PHB p52–53 table defined once in
    :data:`heroforge.logic.familiar.STANDARD_FAMILIAR_BONUSES` (the same source
    the original workbook used to both apply and describe each bonus).  Rows are
    upserted so repeated calls are idempotent.

    No external file is read: unlike the other seeders this is reference data
    that the application owns, so it is kept in code rather than a CSV.
    """
    inserted = 0
    for bonus in STANDARD_FAMILIAR_BONUSES:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO familiar_bonuses
                    (creature_name, value, bonus_kind, target, condition)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bonus.creature_name,
                    bonus.value,
                    bonus.kind,
                    bonus.target,
                    bonus.condition,
                ),
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.debug("Skipping familiar bonus row %r: %s", bonus.creature_name, exc)

    conn.commit()
    logger.info("Familiar bonuses: inserted/replaced %d rows", inserted)


# The progression table sits on the *Animal Companion* sheet under a small block
# of headings; it is located by scanning for the ``Level`` / ``Bonus HD`` header
# pair so the seeder is resilient to the exact column the workbook uses.
_COMPANION_SHEET = "Animal Companion"
_COMPANION_LEVEL_HEADER = "Level"
_COMPANION_BONUS_HD_HEADER = "Bonus HD"


def _group_companion_levels(
    levels: Sequence[tuple[int, int, int, int, str]],
) -> tuple[CompanionProgression, ...]:
    """Collapse per-level progression rows into PHB tiers.

    Consecutive effective druid levels that share the same bonus HD, natural
    armor and Str/Dex adjustment form one tier.  The tier's bonus-tricks count is
    its 1-based ordinal (PHB p36) and its special quality is taken from the first
    row of the group (the *Abilities* cell), with comma/semicolon separated
    qualities normalised to a single comma-separated string.
    """
    tiers: list[CompanionProgression] = []
    for level, bonus_hd, nat_armor, ability_adj, special in levels:
        normalized = ", ".join(
            part.strip() for part in re.split(r"[;,]", special) if part.strip()
        )
        if (
            tiers
            and tiers[-1].bonus_hd == bonus_hd
            and tiers[-1].natural_armor == nat_armor
            and tiers[-1].ability_adjustment == ability_adj
        ):
            prev = tiers[-1]
            tiers[-1] = replace(
                prev,
                max_level=level,
                special=prev.special or normalized,
            )
        else:
            tiers.append(
                CompanionProgression(
                    min_level=level,
                    max_level=level,
                    bonus_hd=bonus_hd,
                    natural_armor=nat_armor,
                    ability_adjustment=ability_adj,
                    bonus_tricks=len(tiers) + 1,
                    special=normalized,
                )
            )
    return tuple(tiers)


def _read_companion_progression(
    workbook_path: str | Path,
) -> tuple[CompanionProgression, ...]:
    """Return the companion progression parsed from the workbook.

    Reads the per-level progression table from the *Animal Companion* sheet of
    ``HeroForge Anew 3.5 v7.4.0.1.xlsm`` (tab 9) and collapses it into tiers via
    :func:`_group_companion_levels`.  Falls back to the in-code
    :data:`STANDARD_COMPANION_PROGRESSION` transcription when the workbook is
    missing, the sheet is absent, or the table cannot be located.
    """
    workbook_path = Path(workbook_path)
    if not workbook_path.exists():
        logger.warning(
            "Workbook not found at %s – using in-code companion progression",
            workbook_path,
        )
        return STANDARD_COMPANION_PROGRESSION

    wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)
    try:
        if _COMPANION_SHEET not in wb.sheetnames:
            logger.warning(
                "Sheet %r missing – using in-code companion progression",
                _COMPANION_SHEET,
            )
            return STANDARD_COMPANION_PROGRESSION

        ws = wb[_COMPANION_SHEET]
        header_col: int | None = None
        levels: list[tuple[int, int, int, int, str]] = []
        for row in ws.iter_rows(values_only=True):
            if header_col is None:
                header_col = _find_companion_header(row)
                continue
            level = row[header_col] if header_col < len(row) else None
            if level is None:
                continue
            if header_col + 3 >= len(row):
                continue
            if isinstance(level, float):
                if not level.is_integer():
                    break
                level_value = int(level)
            elif isinstance(level, int):
                level_value = level
            else:
                break
            abilities = row[header_col + 4] if header_col + 4 < len(row) else None
            levels.append(
                (
                    level_value,
                    _safe_int(row[header_col + 1]),
                    _safe_int(row[header_col + 2]),
                    _safe_int(row[header_col + 3]),
                    abilities.strip() if isinstance(abilities, str) else "",
                )
            )
    finally:
        wb.close()

    tiers = _group_companion_levels(levels)
    if not tiers:
        logger.warning(
            "Companion progression table not found on sheet %r – using in-code "
            "transcription",
            _COMPANION_SHEET,
        )
        return STANDARD_COMPANION_PROGRESSION
    return tiers


def _find_companion_header(row: tuple[object, ...]) -> int | None:
    """Return the column index of the ``Level`` heading in *row*, or ``None``.

    The progression block starts where ``Level`` is immediately followed by
    ``Bonus HD``; that pair anchors the table irrespective of the workbook's
    absolute column position.
    """
    for idx, value in enumerate(row):
        following = row[idx + 1] if idx + 1 < len(row) else None
        if (
            isinstance(value, str)
            and value.strip() == _COMPANION_LEVEL_HEADER
            and isinstance(following, str)
            and following.strip() == _COMPANION_BONUS_HD_HEADER
        ):
            return idx
    return None


def seed_companion_progression(
    conn: sqlite3.Connection, workbook_path: str | Path = _DEFAULT_WORKBOOK
) -> None:
    """Insert the standard animal-companion progression into the game database.

    The level-based progression (PHB p36) lives in the reference workbook's
    *Animal Companion* sheet (``HeroForge Anew 3.5 v7.4.0.1.xlsm`` tab 9) as a
    per-level table, and is read from there via :mod:`openpyxl` rather than from
    hardcoded values.  When the workbook is missing or its table cannot be parsed
    the function falls back to
    :data:`heroforge.logic.animal_companion.STANDARD_COMPANION_PROGRESSION`, which
    is a faithful offline transcription of the same table.

    The *Animal Companion* tab's row headings come from
    :data:`heroforge.logic.animal_companion.COMPANION_PROGRESSION_LABELS`.  Both
    the ``companion_progression`` and ``companion_progression_labels`` tables are
    upserted so repeated calls are idempotent.
    """
    progression = _read_companion_progression(workbook_path)

    tiers = 0
    for order, tier in enumerate(progression):
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO companion_progression
                    (min_level, max_level, bonus_hd, natural_armor,
                     ability_adjustment, bonus_tricks, special, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tier.min_level,
                    tier.max_level,
                    tier.bonus_hd,
                    tier.natural_armor,
                    tier.ability_adjustment,
                    tier.bonus_tricks,
                    tier.special,
                    order,
                ),
            )
            tiers += 1
        except sqlite3.Error as exc:
            logger.debug(
                "Skipping companion progression tier %r: %s", tier.min_level, exc
            )

    labels = 0
    for order, entry in enumerate(COMPANION_PROGRESSION_LABELS):
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO companion_progression_labels
                    (field_key, label, sort_order)
                VALUES (?, ?, ?)
                """,
                (entry.field_key, entry.label, order),
            )
            labels += 1
        except sqlite3.Error as exc:
            logger.debug(
                "Skipping companion progression label %r: %s", entry.field_key, exc
            )

    conn.commit()
    logger.info(
        "Companion progression: inserted/replaced %d tiers, %d labels",
        tiers,
        labels,
    )


# ---------------------------------------------------------------------------
# Spellcasting class data extraction from the reference workbook
# ---------------------------------------------------------------------------

# 0-based column indices in the "Spells per Day" sheet that identify the
# caster progression archetype for a class.  These are fixed across all
# sections of the sheet and determined by the original workbook layout:
#   index 1  (2nd column)  – Bard-like (limited, ≤ 6th level)   → three_quarter
#   index 9  (10th column) – Cleric-like (full 9 spell levels)   → full
#   index 20 (21st column) – Paladin-like (CL + 4 spell levels)  → half
# Index 31 (32nd column) holds "Standard Prestige Good/Poor" archetypes,
# which are not mapped to a caster type here.
_SPD_PARTIAL_CASTER_COL: int = 1
_SPD_FULL_CASTER_COL: int = 9
_SPD_HALF_CASTER_COL: int = 20

# Strings that appear in the "Spells per Day" header rows but are NOT
# individual class names (archetype labels and sub-header tokens).
_SPD_NON_CLASS_HEADERS: frozenset[str] = frozenset(
    {
        "CL",
        "Standard Prestige Good",
        "Standard Prestige Poor",
    }
)


def _extract_spellcasting_class_data(
    wb: openpyxl.Workbook,
) -> dict[str, tuple[str, str]]:
    """Extract spellcasting ability and caster type for each class in *wb*.

    Reads two sheets from the reference workbook:

    * **"Spell Info"** – column 0 holds the full class name; column 7 holds
      the spellcasting ability key (``'Wis'``, ``'Int'``, ``'Cha'``, …).
      Values are upper-cased before storage (e.g. ``'WIS'``).

    * **"Spells per Day"** – class names appear as section headers in fixed
      column positions; the column position identifies the caster archetype:
      col 1 → ``'three_quarter'``, col 9 → ``'full'``, col 20 → ``'half'``.

    Only classes that appear in *both* sheets are returned.

    Returns:
        ``{class_name: (spellcasting_ability, caster_type)}``
    """
    sheet_titles = {ws.title for ws in wb.worksheets}

    # --- Step 1: spellcasting ability from "Spell Info" ---
    ability_map: dict[str, str] = {}
    if "Spell Info" in sheet_titles:
        ws_si = wb["Spell Info"]
        for row_idx, row in enumerate(ws_si.iter_rows(values_only=True)):
            if row_idx < 3:
                # row 0 = column-number row, row 1 = header, row 2 = sub-header
                continue
            class_name = row[0]
            stat = row[7]  # "Stat" column – e.g. 'Wis', 'Int', 'Cha'
            if (
                isinstance(class_name, str)
                and class_name
                and isinstance(stat, str)
                and stat
            ):
                ability_map[class_name] = stat.upper()

    # --- Step 2: caster type from "Spells per Day" column positions ---
    caster_type_map: dict[str, str] = {}
    if "Spells per Day" in sheet_titles:
        ws_spd = wb["Spells per Day"]
        col_ctype_pairs = (
            (_SPD_PARTIAL_CASTER_COL, "three_quarter"),
            (_SPD_FULL_CASTER_COL, "full"),
            (_SPD_HALF_CASTER_COL, "half"),
        )
        for row in ws_spd.iter_rows(values_only=True):
            for col_idx, ctype in col_ctype_pairs:
                if col_idx < len(row):
                    val = row[col_idx]
                    if isinstance(val, str) and val not in _SPD_NON_CLASS_HEADERS:
                        caster_type_map[val] = ctype

    # --- Step 3: combine – emit only entries present in both sheets ---
    return {
        cls: (ability_map[cls], caster_type_map[cls])
        for cls in ability_map
        if cls in caster_type_map
    }


def seed_class_spellcasting_info(
    conn: sqlite3.Connection,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
    workbook: openpyxl.Workbook | None = None,
) -> None:
    """Update the ``classes`` table with spellcasting ability and caster type.

    Reads the reference workbook to extract, for each spellcasting class:

    * ``spellcasting_ability`` (e.g. ``'WIS'``, ``'INT'``, ``'CHA'``) – from
      the ``'Stat'`` column in the workbook's **"Spell Info"** sheet.
    * ``caster_type`` (``'full'`` / ``'three_quarter'`` / ``'half'``) –
      inferred from the column position in which the class appears as a
      section header in the **"Spells per Day"** sheet:
      col 1 → ``'three_quarter'``, col 9 → ``'full'``, col 20 → ``'half'``.

    Rows not yet present in the ``classes`` table are silently skipped so this
    seeder runs safely before or after :func:`seed_classes`.  If the workbook
    file is absent the function logs a warning and returns without error.

    Reference: workbook sheets "Spell Info" and "Spells per Day".
    """
    wb = workbook
    owns_workbook = wb is None
    if wb is None:
        workbook_path = Path(workbook_path)
        if not workbook_path.exists():
            logger.warning(
                "Workbook not found at %s – skipping spellcasting class info",
                workbook_path,
            )
            return
        wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)
    try:
        spellcasting_data = _extract_spellcasting_class_data(wb)
    finally:
        if owns_workbook:
            wb.close()

    updated = 0
    for class_name, (spellcasting_ability, caster_type) in spellcasting_data.items():
        try:
            result = conn.execute(
                """
                UPDATE classes
                SET spellcasting_ability = ?, caster_type = ?
                WHERE name = ?
                """,
                (spellcasting_ability, caster_type, class_name),
            )
            updated += result.rowcount
        except sqlite3.Error as exc:
            logger.debug("Skipping spellcasting info for %r: %s", class_name, exc)

    conn.commit()
    logger.info("Class spellcasting info: updated %d rows", updated)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_all(
    db_path: str | Path = "heroforge.db",
    data_dir: str | Path = _DEFAULT_DATA_DIR,
    workbook_path: str | Path = _DEFAULT_WORKBOOK,
) -> None:
    """Seed the database with all available source data files.

    Args:
        db_path: Path to the SQLite database (created if absent).
        data_dir: Directory containing the source CSV/XLSX files.
        workbook_path: Path to the reference ``.xlsm`` workbook that backs the
            remaining game-data tables.
    """
    db_path = Path(db_path)
    data_dir = Path(data_dir)
    workbook_path = Path(workbook_path)

    logger.info("Seeding database at %s from data dir %s", db_path, data_dir)
    conn = initialize_database(db_path)
    wb_values: openpyxl.Workbook | None = None
    wb_formulas: openpyxl.Workbook | None = None
    try:
        if workbook_path.exists():
            logger.info("Loading workbook %s", workbook_path.name)
            wb_values = openpyxl.load_workbook(
                str(workbook_path), read_only=True, data_only=True
            )
            wb_formulas = openpyxl.load_workbook(
                str(workbook_path), read_only=True, data_only=False
            )
    except Exception:
        if wb_values is not None:
            wb_values.close()
        conn.close()
        raise

    try:
        seed_weapon_damage(conn, workbook_path, workbook=wb_values)
        seed_weapons(conn, data_dir)
        seed_creatures(conn, data_dir)
        seed_tables(conn, data_dir)
        seed_familiar_bonuses(conn)
        seed_companion_progression(conn, workbook_path)
        seed_classes(conn, data_dir)
        seed_class_spellcasting_info(conn, workbook_path, workbook=wb_values)
        seed_workbook(conn, workbook_path, workbook=wb_values)
        seed_skill_synergies(conn, workbook_path, workbook=wb_formulas)
        seed_psionic_progression(conn, workbook_path, workbook=wb_formulas)
    finally:
        if wb_values is not None:
            wb_values.close()
        if wb_formulas is not None:
            wb_formulas.close()
        conn.close()

    logger.info("Seeding complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed the HeroForge-Anew SQLite database from source data files."
    )
    parser.add_argument(
        "--db",
        default="heroforge.db",
        help="Path to the SQLite database file (default: heroforge.db)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(_DEFAULT_DATA_DIR),
        help="Directory containing source data files (default: <project_root>/data/)",
    )
    parser.add_argument(
        "--workbook",
        default=str(_DEFAULT_WORKBOOK),
        help=(
            "Path to the reference .xlsm workbook backing the remaining "
            "game-data tables (default: <project_root>/"
            "HeroForge Anew 3.5 v7.4.0.1.xlsm)"
        ),
    )
    return parser


def main() -> None:
    """CLI entry point."""
    configure_logging(fmt="%(levelname)s %(message)s")
    args = _build_parser().parse_args()
    seed_all(db_path=args.db, data_dir=args.data_dir, workbook_path=args.workbook)


if __name__ == "__main__":
    main()
