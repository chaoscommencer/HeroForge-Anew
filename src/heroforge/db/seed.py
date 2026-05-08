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
import sqlite3
from pathlib import Path

import openpyxl

from heroforge.db.schema import initialize_database

logger = logging.getLogger(__name__)

# Project root is two levels above this file (src/heroforge/db/seed.py)
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"


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
# Per-table seed functions
# ---------------------------------------------------------------------------


def seed_weapons(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``WeaponInfo.csv`` into the *weapons* table."""
    csv_path = data_dir / "WeaponInfo.csv"
    if not csv_path.exists():
        logger.warning("WeaponInfo.csv not found at %s – skipping weapons", csv_path)
        return

    inserted = 0
    skipped = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("Name") or row.get("name") or "").strip()
            if not name:
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
                        (row.get("Category") or row.get("category") or "").strip(),
                        (row.get("Size") or row.get("size") or "").strip(),
                        (row.get("Damage (S)") or row.get("damage_small") or "").strip(),
                        (row.get("Damage (M)") or row.get("damage_medium") or "").strip(),
                        (row.get("Critical") or row.get("critical") or "").strip(),
                        _safe_int(row.get("Range Increment") or row.get("range_increment")),
                        _safe_float(row.get("Weight") or row.get("weight")),
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
    """Insert rows from ``CreatureInfo.csv`` into the *creatures* table."""
    csv_path = data_dir / "CreatureInfo.csv"
    if not csv_path.exists():
        logger.warning("CreatureInfo.csv not found at %s – skipping creatures", csv_path)
        return

    inserted = 0
    skipped = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("Name") or row.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO creatures
                        (name, size, type, subtype, hit_dice,
                         str_score, dex_score, con_score, int_score, wis_score, cha_score,
                         bab, grapple_mod, armor_class, speed, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        (row.get("Size") or row.get("size") or "").strip(),
                        (row.get("Type") or row.get("type") or "").strip(),
                        (row.get("Subtype") or row.get("subtype") or "").strip(),
                        (row.get("HD") or row.get("hit_dice") or "").strip(),
                        _safe_int(row.get("STR") or row.get("str_score")),
                        _safe_int(row.get("DEX") or row.get("dex_score")),
                        _safe_int(row.get("CON") or row.get("con_score")),
                        _safe_int(row.get("INT") or row.get("int_score")),
                        _safe_int(row.get("WIS") or row.get("wis_score")),
                        _safe_int(row.get("CHA") or row.get("cha_score")),
                        (row.get("BAB") or row.get("bab") or "").strip(),
                        _safe_int(row.get("Grapple") or row.get("grapple_mod")),
                        _safe_int(row.get("AC") or row.get("armor_class")),
                        (row.get("Speed") or row.get("speed") or "").strip(),
                        (row.get("Source") or row.get("source") or "").strip(),
                    ),
                )
                inserted += 1
            except sqlite3.Error as exc:
                logger.debug("Skipping creature row %r: %s", name, exc)
                skipped += 1

    conn.commit()
    logger.info("Creatures: inserted/replaced %d rows, skipped %d", inserted, skipped)


def seed_tables(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``Tables.csv`` into the *tables* table."""
    csv_path = data_dir / "Tables.csv"
    if not csv_path.exists():
        logger.warning("Tables.csv not found at %s – skipping tables", csv_path)
        return

    inserted = 0
    skipped = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            table_name = (row.get("TableName") or row.get("table_name") or "").strip()
            key = (row.get("Key") or row.get("key") or "").strip()
            value = (row.get("Value") or row.get("value") or "").strip()
            if not table_name or not key:
                skipped += 1
                continue
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO tables (table_name, key, value) VALUES (?, ?, ?)",
                    (table_name, key, value),
                )
                inserted += 1
            except sqlite3.Error as exc:
                logger.debug("Skipping table row %r/%r: %s", table_name, key, exc)
                skipped += 1

    conn.commit()
    logger.info("Tables: inserted/replaced %d rows, skipped %d", inserted, skipped)


def seed_classes(conn: sqlite3.Connection, data_dir: Path) -> None:
    """Insert rows from ``ClassInfo.xlsx`` into *classes* (and *class_skills*)."""
    xlsx_path = data_dir / "ClassInfo.xlsx"
    if not xlsx_path.exists():
        logger.warning("ClassInfo.xlsx not found at %s – skipping classes", xlsx_path)
        return

    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)

    inserted_classes = 0
    inserted_skills = 0
    skipped = 0

    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        # First row is header
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]

        def col(row_data: tuple, *candidates: str) -> str:
            for c in candidates:
                try:
                    idx = headers.index(c)
                    val = row_data[idx]
                    return str(val).strip() if val is not None else ""
                except (ValueError, IndexError):
                    pass
            return ""

        for row_data in rows[1:]:
            if all(v is None for v in row_data):
                continue
            name = col(row_data, "Name", "name", "Class", "class")
            if not name:
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
                        1 if col(row_data, "IsPrestige", "is_prestige", "Prestige").lower() in ("1", "true", "yes") else 0,
                        _safe_int(col(row_data, "HitDie", "hit_die", "HD")),
                        col(row_data, "BAB", "bab_progression", "BABProgression"),
                        col(row_data, "Fort", "fort_progression", "FortProgression"),
                        col(row_data, "Ref", "ref_progression", "RefProgression"),
                        col(row_data, "Will", "will_progression", "WillProgression"),
                        _safe_int(col(row_data, "SkillPoints", "skill_points_per_level", "SP")),
                        col(row_data, "Source", "source"),
                    ),
                )
                inserted_classes += 1

                # Handle class skills column if present (comma-separated)
                class_skills_raw = col(row_data, "ClassSkills", "class_skills", "Skills")
                if class_skills_raw:
                    for skill in (s.strip() for s in class_skills_raw.split(",") if s.strip()):
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO class_skills (class_name, skill_name) VALUES (?, ?)",
                                (name, skill),
                            )
                            inserted_skills += 1
                        except sqlite3.Error:
                            pass

            except sqlite3.Error as exc:
                logger.debug("Skipping class row %r: %s", name, exc)
                skipped += 1

    conn.commit()
    wb.close()
    logger.info(
        "Classes: inserted/replaced %d class rows, %d skill rows, skipped %d",
        inserted_classes,
        inserted_skills,
        skipped,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_all(
    db_path: str | Path = "heroforge.db",
    data_dir: str | Path = _DEFAULT_DATA_DIR,
) -> None:
    """Seed the database with all available source data files.

    Args:
        db_path: Path to the SQLite database (created if absent).
        data_dir: Directory containing the source CSV/XLSX files.
    """
    db_path = Path(db_path)
    data_dir = Path(data_dir)

    logger.info("Seeding database at %s from data dir %s", db_path, data_dir)
    conn = initialize_database(db_path)

    try:
        seed_weapons(conn, data_dir)
        seed_creatures(conn, data_dir)
        seed_tables(conn, data_dir)
        seed_classes(conn, data_dir)
    finally:
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
    return parser


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args()
    seed_all(db_path=args.db, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
