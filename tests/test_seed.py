"""Tests for heroforge.db.seed.

Verifies that the workbook-backed migration populates every targeted
game-data table, that the persisted row counts match what is extracted from
the source workbook, and that re-seeding is idempotent.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from heroforge.db import seed
from heroforge.db.schema import get_connection

requires_workbook = pytest.mark.skipif(
    not seed._DEFAULT_WORKBOOK.exists(),
    reason="reference workbook not available",
)


def _expected_count(spec: seed._WorkbookTable, rows: list[tuple]) -> int:
    """Replicate UNIQUE-key conflict handling from workbook table inserts."""
    if spec.unique_by is None:
        return len(rows)
    key_indexes = [spec.columns.index(col) for col in spec.unique_by]
    keys = {tuple(row[i] for i in key_indexes) for row in rows}
    return len(keys)


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seed a temporary database once from the real workbook for the module."""
    db_path = tmp_path_factory.mktemp("seed") / "seeded.db"
    seed.seed_all(db_path=db_path)
    return db_path


@pytest.fixture(scope="module")
def source_counts() -> dict[str, int]:
    """Expected per-table row counts derived directly from the workbook."""
    wb = openpyxl.load_workbook(
        str(seed._DEFAULT_WORKBOOK), read_only=True, data_only=True
    )
    try:
        counts = {
            spec.table: _expected_count(spec, spec.extractor(wb))
            for spec in seed._WORKBOOK_TABLES
        }
    finally:
        wb.close()
    return counts


_TABLE_NAMES = [spec.table for spec in seed._WORKBOOK_TABLES]


@requires_workbook
class TestWorkbookSeeding:
    @pytest.mark.parametrize("table", _TABLE_NAMES)
    def test_table_is_populated(self, seeded_db: Path, table: str) -> None:
        conn = get_connection(seeded_db)
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()
        assert count > 0, f"{table} should be populated from the workbook"

    @pytest.mark.parametrize("table", _TABLE_NAMES)
    def test_count_matches_source(
        self, seeded_db: Path, source_counts: dict[str, int], table: str
    ) -> None:
        conn = get_connection(seeded_db)
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()
        assert count == source_counts[table]

    def test_skill_footnotes_preserve_marked_names(self, seeded_db: Path) -> None:
        conn = get_connection(seeded_db)
        try:
            row = conn.execute(
                """
                SELECT skill_name, raw_name, marker
                FROM skill_footnotes
                WHERE skill_name = 'Appraise'
                """
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["raw_name"] == "Appraise¹"
        assert row["marker"] == "¹"


@requires_workbook
class TestIdempotency:
    def test_reseeding_does_not_change_counts(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idempotent.db"

        seed.seed_all(db_path=db_path)
        conn = get_connection(db_path)
        try:
            first = {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in _TABLE_NAMES
            }
        finally:
            conn.close()

        # Seeding a second time must not duplicate any rows.
        seed.seed_all(db_path=db_path)
        conn = get_connection(db_path)
        try:
            second = {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in _TABLE_NAMES
            }
        finally:
            conn.close()

        assert first == second
        assert all(v > 0 for v in second.values())


class TestMissingWorkbook:
    def test_missing_workbook_is_skipped(self, tmp_path: Path) -> None:
        """A missing workbook logs a warning and leaves tables untouched."""
        from heroforge.db.schema import initialize_database

        db_path = tmp_path / "no_workbook.db"
        conn = initialize_database(db_path)
        try:
            seed.seed_workbook(conn, tmp_path / "does_not_exist.xlsm")
            count = conn.execute("SELECT COUNT(*) FROM feats").fetchone()[0]
        finally:
            conn.close()
        assert count == 0


class TestHelpers:
    def test_strip_footnotes(self) -> None:
        assert seed._strip_footnotes("Appraise\u00b9") == "Appraise"
        assert seed._strip_footnotes("Craft skills\u2026\u00b9") == "Craft skills"
        assert seed._strip_footnotes("Balance ") == "Balance"

    def test_trailing_footnote_markers(self) -> None:
        assert seed._trailing_footnote_markers("Appraise\u00b9") == "\u00b9"
        assert seed._trailing_footnote_markers("Swim\u00b9\u00b9") == "\u00b9\u00b9"
        assert seed._trailing_footnote_markers("Appraise\u00b9 ") == "\u00b9"
        assert seed._trailing_footnote_markers("Use Rope") == ""

    def test_lstrip_separator(self) -> None:
        assert seed._lstrip_separator(" : +2 bonus") == "+2 bonus"
        assert seed._lstrip_separator("plain") == "plain"

    def test_col_out_of_range(self) -> None:
        assert seed._col(("a", "b"), "Z") == ""
        assert seed._col(("a", None), "A") == "a"
        assert seed._col(("a", None), "B") == ""
