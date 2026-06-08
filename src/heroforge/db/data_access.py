"""Read-only data-access layer for HeroForge-Anew game data.

The PyQt UI must treat ``heroforge.db`` as its single source of truth.  Rather
than embedding raw ``sqlite3`` queries inside individual widgets, every tab and
dialog goes through :class:`GameDataRepository`, a thin, read-only service that
opens the seeded game database and returns plain Python objects.

Design goals:

* **Read-only** – the repository never mutates ``heroforge.db``; it only ever
  issues ``SELECT`` statements.
* **Defensive** – a missing database file or a not-yet-seeded table yields an
  empty result instead of raising, so tab construction never crashes when the
  data is absent (e.g. in a fresh checkout before seeding).
* **Source-aware** – content that carries a ``source`` column can be filtered
  by the set of sourcebooks the user has enabled (see
  ``docs/conversion-plan.md`` §8.6).  Rows whose ``source`` is ``NULL``/empty
  are always included so unsourced reference data is never hidden.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from heroforge.db.schema import get_connection
from heroforge.logic.derived_stats import ClassProgression

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    """A sourcebook entry from the ``sources`` table."""

    abbreviation: str
    full_name: str

    @property
    def label(self) -> str:
        """Human-readable ``"ABBR – Full Name"`` label for list widgets."""
        return f"{self.abbreviation} – {self.full_name}"


@dataclass(frozen=True)
class Feat:
    """A feat entry from the ``feats`` table."""

    name: str
    type: str
    description: str
    benefit: str
    source: str


@dataclass(frozen=True)
class SpellSlots:
    """A single spells-per-day / spells-known progression cell."""

    caster_level: int
    spell_level: int
    count: int


class GameDataRepository:
    """Read-only accessor for the seeded ``heroforge.db`` game database.

    Args:
        db_path: Path to the SQLite game database.  May be ``None`` (e.g. when
            no database has been initialised yet), in which case every query
            returns an empty result.
    """

    def __init__(self, db_path: str | Path | None) -> None:
        self._db_path: Path | None = Path(db_path) if db_path else None

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path | None:
        """Path to the backing database, or ``None`` if unset."""
        return self._db_path

    @property
    def available(self) -> bool:
        """``True`` when a backing database file exists on disk."""
        return self._db_path is not None and self._db_path.exists()

    def _connect(self) -> sqlite3.Connection | None:
        """Open a connection, or return ``None`` if the DB is unavailable."""
        if not self.available:
            return None
        assert self._db_path is not None
        return get_connection(self._db_path)

    def _query(self, sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        """Run *sql* and return all rows, tolerating a missing DB/table."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            return conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error as exc:
            # A not-yet-seeded or missing table should degrade gracefully rather
            # than crash UI construction.
            logger.debug("Query failed (%s): %s", exc, sql)
            return []
        finally:
            conn.close()

    @staticmethod
    def _source_filter(
        column: str, sources: Iterable[str] | None
    ) -> tuple[str, list[str]]:
        """Build a ``WHERE``-fragment filtering *column* by *sources*.

        Rows with a ``NULL``/empty source are always kept so unsourced
        reference data is never filtered out.  Returns ``("", [])`` when no
        filtering is requested.
        """
        if sources is None:
            return "", []
        wanted = [s for s in sources if s]
        if not wanted:
            return "", []
        placeholders = ", ".join("?" for _ in wanted)
        fragment = (
            f"({column} IS NULL OR {column} = '' OR {column} IN ({placeholders}))"
        )
        return fragment, list(wanted)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def list_sources(self) -> list[Source]:
        """Return all sourcebooks ordered by abbreviation."""
        rows = self._query(
            "SELECT abbreviation, full_name FROM sources ORDER BY abbreviation"
        )
        return [Source(r["abbreviation"], r["full_name"]) for r in rows]

    # ------------------------------------------------------------------
    # Feats
    # ------------------------------------------------------------------

    def list_feats(self, sources: Iterable[str] | None = None) -> list[Feat]:
        """Return feats ordered by name, optionally filtered by *sources*."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, type, description, benefit, source "
            f"FROM feats {where} ORDER BY name",
            params,
        )
        return [
            Feat(
                name=r["name"],
                type=r["type"] or "",
                description=r["description"] or "",
                benefit=r["benefit"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def feat_prerequisites(self) -> dict[str, list[str]]:
        """Return a mapping of feat name → list of prerequisite strings.

        Feats with no recorded prerequisites are simply absent from the
        mapping.  Used by the UI to validate which feats a character qualifies
        for via :func:`heroforge.logic.feats.check_prerequisites`.
        """
        rows = self._query(
            "SELECT feat_name, prerequisite FROM feat_prerequisites "
            "ORDER BY feat_name, id"
        )
        result: dict[str, list[str]] = {}
        for r in rows:
            result.setdefault(r["feat_name"], []).append(r["prerequisite"])
        return result

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def class_progressions(self) -> dict[str, ClassProgression]:
        """Return a mapping of class name → :class:`ClassProgression`.

        Supplies the BAB and saving-throw progression types used to compute a
        character's derived combat/save values.  ``NULL`` columns fall back to
        the D&D defaults (``medium`` BAB, ``poor`` saves).
        """
        rows = self._query(
            "SELECT name, bab_progression, fort_progression, "
            "ref_progression, will_progression FROM classes"
        )
        return {
            r["name"]: ClassProgression(
                name=r["name"],
                bab=r["bab_progression"] or "medium",
                fort=r["fort_progression"] or "poor",
                ref=r["ref_progression"] or "poor",
                will=r["will_progression"] or "poor",
            )
            for r in rows
        }

    # ------------------------------------------------------------------
    # Races & templates
    # ------------------------------------------------------------------

    def list_races(self, sources: Iterable[str] | None = None) -> list[str]:
        """Return race names ordered alphabetically."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(f"SELECT name FROM races {where} ORDER BY name", params)
        return [r["name"] for r in rows]

    def list_templates(self, sources: Iterable[str] | None = None) -> list[str]:
        """Return template names ordered alphabetically."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(f"SELECT name FROM templates {where} ORDER BY name", params)
        return [r["name"] for r in rows]

    # ------------------------------------------------------------------
    # Spells
    # ------------------------------------------------------------------

    def list_caster_classes(self) -> list[str]:
        """Return spellcasting class names that have progression data.

        Names are drawn from both the spells-per-day and spells-known tables so
        every class with any spell progression is offered.
        """
        rows = self._query(
            "SELECT class_name FROM spells_per_day "
            "UNION SELECT class_name FROM spells_known "
            "ORDER BY class_name"
        )
        return [r["class_name"] for r in rows]

    def spells_per_day(self, class_name: str) -> list[SpellSlots]:
        """Return the spells-per-day progression for *class_name*."""
        rows = self._query(
            "SELECT caster_level, spell_level, slots FROM spells_per_day "
            "WHERE class_name = ? ORDER BY caster_level, spell_level",
            (class_name,),
        )
        return [
            SpellSlots(r["caster_level"], r["spell_level"], r["slots"]) for r in rows
        ]

    def spells_known(self, class_name: str) -> list[SpellSlots]:
        """Return the spells-known progression for *class_name*."""
        rows = self._query(
            "SELECT caster_level, spell_level, count FROM spells_known "
            "WHERE class_name = ? ORDER BY caster_level, spell_level",
            (class_name,),
        )
        return [
            SpellSlots(r["caster_level"], r["spell_level"], r["count"]) for r in rows
        ]
