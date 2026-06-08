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


@dataclass(frozen=True)
class ArmorItem:
    """An armor or shield entry from the ``armor`` table."""

    name: str
    type: str
    ac_bonus: int
    max_dex_bonus: int | None
    check_penalty: int
    arcane_spell_failure: int
    weight: float
    source: str

    @property
    def is_shield(self) -> bool:
        """``True`` when this entry is a shield rather than body armor."""
        return "shield" in (self.type or "").lower()


@dataclass(frozen=True)
class WeaponItem:
    """A weapon entry from the ``weapons`` table."""

    name: str
    category: str
    damage: str
    critical: str
    range_increment: int
    damage_type: str
    source: str


@dataclass(frozen=True)
class GraftItem:
    """A graft entry from the ``grafts`` table."""

    name: str
    type: str
    body_slot: str
    description: str
    source: str


@dataclass(frozen=True)
class SoulmeldItem:
    """A soulmeld entry from the ``soulmelds`` table."""

    name: str
    chakra: str
    essentia_capacity: int
    description: str
    source: str


@dataclass(frozen=True)
class PsionicPower:
    """A psionic power entry from the ``psionic_powers`` table."""

    name: str
    discipline: str
    power_points: int
    manifester_level_min: int
    description: str
    source: str


@dataclass(frozen=True)
class Maneuver:
    """A martial maneuver/stance entry from the ``maneuvers`` table."""

    name: str
    discipline: str
    level: int
    type: str
    source: str

    @property
    def is_stance(self) -> bool:
        """``True`` when this entry is a stance rather than a maneuver."""
        return "stance" in (self.type or "").lower()


@dataclass(frozen=True)
class MagicEnhancement:
    """A magic weapon/armor enhancement from the ``magic_enhancements`` table."""

    name: str
    type: str
    bonus_equivalent: int
    description: str
    source: str


@dataclass(frozen=True)
class MagicItem:
    """A magic item entry from the ``magic_equipment`` table."""

    name: str
    slot: str
    description: str
    source: str


@dataclass(frozen=True)
class SkillTrick:
    """A skill trick entry from the ``skill_tricks`` table."""

    name: str
    cost: int
    description: str
    prerequisite: str


@dataclass(frozen=True)
class Creature:
    """A creature entry from the ``creatures`` table (companions/familiars)."""

    name: str
    size: str
    type: str
    hit_dice: str
    ability_scores: dict[str, int]
    armor_class: int


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

    # ------------------------------------------------------------------
    # Equipment catalogues (armor, weapons, magic items, enhancements)
    # ------------------------------------------------------------------

    def list_armor(self, sources: Iterable[str] | None = None) -> list[ArmorItem]:
        """Return armor and shield entries ordered by name.

        Used by the Armor tab to offer real catalogue choices (with their AC,
        max-Dex, check-penalty, and arcane-spell-failure values) instead of
        free-form spinboxes.
        """
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, type, ac_bonus, max_dex_bonus, check_penalty, "
            "arcane_spell_failure, weight, source "
            f"FROM armor {where} ORDER BY name",
            params,
        )
        return [
            ArmorItem(
                name=r["name"],
                type=r["type"] or "",
                ac_bonus=int(r["ac_bonus"] or 0),
                max_dex_bonus=(
                    None if r["max_dex_bonus"] is None else int(r["max_dex_bonus"])
                ),
                check_penalty=int(r["check_penalty"] or 0),
                arcane_spell_failure=int(r["arcane_spell_failure"] or 0),
                weight=float(r["weight"] or 0.0),
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_weapons(self, sources: Iterable[str] | None = None) -> list[WeaponItem]:
        """Return weapon entries ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, category, damage_medium, critical, range_increment, "
            f"damage_type, source FROM weapons {where} ORDER BY name",
            params,
        )
        return [
            WeaponItem(
                name=r["name"],
                category=r["category"] or "",
                damage=r["damage_medium"] or "",
                critical=r["critical"] or "",
                range_increment=int(r["range_increment"] or 0),
                damage_type=r["damage_type"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_magic_enhancements(
        self, sources: Iterable[str] | None = None
    ) -> list[MagicEnhancement]:
        """Return magic weapon/armor enhancements ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, type, bonus_equivalent, description, source "
            f"FROM magic_enhancements {where} ORDER BY name",
            params,
        )
        return [
            MagicEnhancement(
                name=r["name"],
                type=r["type"] or "",
                bonus_equivalent=int(r["bonus_equivalent"] or 0),
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_magic_equipment(
        self, sources: Iterable[str] | None = None
    ) -> list[MagicItem]:
        """Return magic-item entries ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, slot, description, source "
            f"FROM magic_equipment {where} ORDER BY name",
            params,
        )
        return [
            MagicItem(
                name=r["name"],
                slot=r["slot"] or "",
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Grafts, soulmelds, psionics, maneuvers
    # ------------------------------------------------------------------

    def list_grafts(self, sources: Iterable[str] | None = None) -> list[GraftItem]:
        """Return graft entries ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, type, body_slot, description, source "
            f"FROM grafts {where} ORDER BY name",
            params,
        )
        return [
            GraftItem(
                name=r["name"],
                type=r["type"] or "",
                body_slot=r["body_slot"] or "",
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_soulmelds(
        self, sources: Iterable[str] | None = None
    ) -> list[SoulmeldItem]:
        """Return soulmeld entries ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, chakra, essentia_capacity, description, source "
            f"FROM soulmelds {where} ORDER BY name",
            params,
        )
        return [
            SoulmeldItem(
                name=r["name"],
                chakra=r["chakra"] or "",
                essentia_capacity=int(r["essentia_capacity"] or 0),
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_psionic_powers(
        self, sources: Iterable[str] | None = None
    ) -> list[PsionicPower]:
        """Return psionic power entries ordered by name."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, discipline, power_points, manifester_level_min, "
            f"description, source FROM psionic_powers {where} ORDER BY name",
            params,
        )
        return [
            PsionicPower(
                name=r["name"],
                discipline=r["discipline"] or "",
                power_points=int(r["power_points"] or 0),
                manifester_level_min=int(r["manifester_level_min"] or 0),
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    def list_maneuvers(self, sources: Iterable[str] | None = None) -> list[Maneuver]:
        """Return martial maneuver/stance entries ordered by discipline, level."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, discipline, level, type, source "
            f"FROM maneuvers {where} ORDER BY discipline, level, name",
            params,
        )
        return [
            Maneuver(
                name=r["name"],
                discipline=r["discipline"] or "",
                level=int(r["level"] or 0),
                type=r["type"] or "",
                source=r["source"] or "",
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Languages, traits, flaws, skill tricks, creatures
    # ------------------------------------------------------------------

    def list_languages(self) -> list[str]:
        """Return language names ordered alphabetically."""
        rows = self._query("SELECT name FROM languages ORDER BY name")
        return [r["name"] for r in rows]

    def list_traits(self, sources: Iterable[str] | None = None) -> list[str]:
        """Return trait names ordered alphabetically (Unearthed Arcana)."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(f"SELECT name FROM traits {where} ORDER BY name", params)
        return [r["name"] for r in rows]

    def list_flaws(self, sources: Iterable[str] | None = None) -> list[str]:
        """Return flaw names ordered alphabetically (Unearthed Arcana)."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(f"SELECT name FROM flaws {where} ORDER BY name", params)
        return [r["name"] for r in rows]

    def list_skill_tricks(self) -> list[SkillTrick]:
        """Return skill-trick entries ordered by name."""
        rows = self._query(
            "SELECT name, cost, description, prerequisite "
            "FROM skill_tricks ORDER BY name"
        )
        return [
            SkillTrick(
                name=r["name"],
                cost=int(r["cost"] or 2),
                description=r["description"] or "",
                prerequisite=r["prerequisite"] or "",
            )
            for r in rows
        ]

    def list_creatures(self, sources: Iterable[str] | None = None) -> list[Creature]:
        """Return creature entries ordered by name (companions/familiars)."""
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            "SELECT name, size, type, hit_dice, str_score, dex_score, con_score, "
            "int_score, wis_score, cha_score, armor_class "
            f"FROM creatures {where} ORDER BY name",
            params,
        )
        return [
            Creature(
                name=r["name"],
                size=r["size"] or "",
                type=r["type"] or "",
                hit_dice=r["hit_dice"] or "",
                ability_scores={
                    "STR": int(r["str_score"] or 10),
                    "DEX": int(r["dex_score"] or 10),
                    "CON": int(r["con_score"] or 10),
                    "INT": int(r["int_score"] or 10),
                    "WIS": int(r["wis_score"] or 10),
                    "CHA": int(r["cha_score"] or 10),
                },
                armor_class=int(r["armor_class"] or 10),
            )
            for r in rows
        ]
