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
from heroforge.logic.familiar import (
    FamiliarBonus,
    FamiliarMasterAbility,
    describe_bonus,
)
from heroforge.models.race import Race
from heroforge.models.template import Template

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
class DomainInfo:
    """A cleric domain from the ``domains`` table.

    ``domain_spells`` is a list of nine spell names (indices 0–8 correspond to
    spell levels 1–9); empty strings indicate no domain spell at that level.
    Reference: PHB Chapter 11 (domain descriptions).
    """

    name: str
    granted_power: str
    domain_spells: list[str]  # length 9, indices 0-8 → levels 1-9


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
    natural_armor: int


@dataclass(frozen=True)
class IncarnumAbility:
    """An entry from the ``incarnum_abilities`` table (Magic of Incarnum)."""

    name: str
    description: str


@dataclass(frozen=True)
class Vestige:
    """A bindable vestige entry from the ``vestiges`` table (Tome of Magic)."""

    name: str
    level: int | None
    """Binding DC level of the vestige, or ``None`` if not recorded in the source."""
    source: str | None
    """Sourcebook abbreviation, or ``None`` for unsourced/core vestiges."""


@dataclass(frozen=True)
class MarshalAura:
    """A marshal aura entry from the ``marshal_auras`` table (Miniatures Handbook)."""

    name: str
    aura_type: str


@dataclass(frozen=True)
class RacialAbility:
    """A racial special ability from the ``racial_abilities`` table."""

    race_name: str
    ability_name: str
    description: str


@dataclass(frozen=True)
class GraftAbility:
    """A graft special ability from the ``graft_abilities`` table."""

    graft_name: str
    ability_name: str
    description: str


@dataclass(frozen=True)
class Variant:
    """A class/racial variant from the ``variants`` table.

    ``base_class`` names the class **or race** the variant modifies; race
    variants are those whose ``base_class`` matches a race name.
    """

    name: str
    base_class: str
    description: str
    source: str


@dataclass(frozen=True)
class ClassInfo:
    """A character class entry from the ``classes`` table (PHB Chapter 3)."""

    name: str
    is_prestige: bool
    hit_die: int
    bab_progression: str
    fort_progression: str
    ref_progression: str
    will_progression: str
    skill_points_per_level: int
    source: str


@dataclass(frozen=True)
class ClassAbility:
    """A class special ability from the ``class_abilities`` table.

    ``level`` is the class level at which the ability is gained.
    """

    class_name: str
    level: int
    ability_name: str
    description: str


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

    def list_classes(
        self,
        sources: Iterable[str] | None = None,
        *,
        include_prestige: bool = False,
    ) -> list[ClassInfo]:
        """Return character classes ordered by name.

        By default only base classes (``is_prestige = 0``) are returned, which
        is what the base-class picker (Excel tab 1b) needs; pass
        ``include_prestige=True`` to include prestige classes as well.  Results
        can additionally be filtered by enabled *sources*.
        """
        fragment, params = self._source_filter("source", sources)
        clauses: list[str] = []
        if not include_prestige:
            clauses.append("COALESCE(is_prestige, 0) = 0")
        if fragment:
            clauses.append(fragment)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._query(
            "SELECT name, is_prestige, hit_die, bab_progression, "
            "fort_progression, ref_progression, will_progression, "
            f"skill_points_per_level, source FROM classes {where} ORDER BY name",
            params,
        )
        return [
            ClassInfo(
                name=r["name"],
                is_prestige=bool(r["is_prestige"]),
                hit_die=r["hit_die"] or 8,
                bab_progression=r["bab_progression"] or "medium",
                fort_progression=r["fort_progression"] or "poor",
                ref_progression=r["ref_progression"] or "poor",
                will_progression=r["will_progression"] or "poor",
                skill_points_per_level=r["skill_points_per_level"] or 2,
                source=r["source"] or "",
            )
            for r in rows
        ]

    def class_skills(self, class_name: str) -> list[str]:
        """Return the class-skill names for *class_name*, ordered alphabetically."""
        rows = self._query(
            "SELECT skill_name FROM class_skills WHERE class_name = ? "
            "ORDER BY skill_name",
            (class_name,),
        )
        return [r["skill_name"] for r in rows]

    def class_proficiencies(self, class_name: str) -> list[str]:
        """Return the weapon/armor proficiencies granted by *class_name*.

        Drawn from the ``class_weapons_armor`` table seeded from the workbook's
        "Class Weapons & Armor" data.
        """
        rows = self._query(
            "SELECT proficiency FROM class_weapons_armor WHERE class_name = ? "
            "ORDER BY id",
            (class_name,),
        )
        return [r["proficiency"] for r in rows]

    def class_abilities(self, class_name: str) -> list[ClassAbility]:
        """Return the special abilities granted by *class_name* by level."""
        rows = self._query(
            "SELECT class_name, level, ability_name, description "
            "FROM class_abilities WHERE class_name = ? ORDER BY level, id",
            (class_name,),
        )
        return [
            ClassAbility(
                class_name=r["class_name"],
                level=r["level"],
                ability_name=r["ability_name"],
                description=r["description"] or "",
            )
            for r in rows
        ]

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

    def get_race(self, name: str) -> Race | None:
        """Return the full :class:`~heroforge.models.race.Race` row for *name*.

        Supplies the ability adjustments, size, speeds, vision, natural armor,
        and level adjustment used to apply racial modifiers to a character.
        Returns ``None`` when the race is unknown or the database is
        unavailable.  The race's special abilities are populated from the
        ``racial_abilities`` table.
        """
        rows = self._query(
            "SELECT id, name, size, type, subtype, base_land_speed, "
            "base_fly_speed, base_swim_speed, base_climb_speed, "
            "base_burrow_speed, darkvision, low_light_vision, natural_armor, "
            "str_adj, dex_adj, con_adj, int_adj, wis_adj, cha_adj, "
            "level_adjustment, favored_class, source "
            "FROM races WHERE LOWER(name) = LOWER(?) LIMIT 1",
            [name],
        )
        if not rows:
            return None
        r = rows[0]
        canonical_name = r["name"]
        return Race(
            id=r["id"],
            name=canonical_name,
            size=r["size"] or "Medium",
            type=r["type"] or "Humanoid",
            subtype=r["subtype"] or "",
            base_land_speed=r["base_land_speed"] or 0,
            base_fly_speed=r["base_fly_speed"] or 0,
            base_swim_speed=r["base_swim_speed"] or 0,
            base_climb_speed=r["base_climb_speed"] or 0,
            base_burrow_speed=r["base_burrow_speed"] or 0,
            darkvision=r["darkvision"] or 0,
            low_light_vision=r["low_light_vision"] or 0,
            natural_armor=r["natural_armor"] or 0,
            str_adj=r["str_adj"] or 0,
            dex_adj=r["dex_adj"] or 0,
            con_adj=r["con_adj"] or 0,
            int_adj=r["int_adj"] or 0,
            wis_adj=r["wis_adj"] or 0,
            cha_adj=r["cha_adj"] or 0,
            level_adjustment=r["level_adjustment"] or 0,
            favored_class=r["favored_class"] or "",
            source=r["source"] or "",
            abilities=[
                a.ability_name
                for a in self.list_racial_abilities(race_name=canonical_name)
            ],
        )

    def get_template(self, name: str) -> Template | None:
        """Return the full :class:`~heroforge.models.template.Template` for *name*.

        Supplies the ability adjustments, type/subtype changes, CR adjustment,
        and level adjustment a template contributes when layered on top of a
        base race/creature.  Returns ``None`` when the template is unknown or
        the database is unavailable.
        """
        rows = self._query(
            "SELECT id, name, cr_adjustment, level_adjustment, type_change, "
            "subtype_added, str_adj, dex_adj, con_adj, int_adj, wis_adj, "
            "cha_adj, source FROM templates WHERE LOWER(name) = LOWER(?) LIMIT 1",
            [name],
        )
        if not rows:
            return None
        r = rows[0]
        return Template(
            id=r["id"],
            name=r["name"],
            cr_adjustment=r["cr_adjustment"] or 0.0,
            level_adjustment=r["level_adjustment"] or 0,
            type_change=r["type_change"] or "",
            subtype_added=r["subtype_added"] or "",
            str_adj=r["str_adj"] or 0,
            dex_adj=r["dex_adj"] or 0,
            con_adj=r["con_adj"] or 0,
            int_adj=r["int_adj"] or 0,
            wis_adj=r["wis_adj"] or 0,
            cha_adj=r["cha_adj"] or 0,
            source=r["source"] or "",
        )

    def get_templates(self, names: Iterable[str]) -> list[Template]:
        """Return the :class:`Template` rows for *names*, skipping unknowns.

        Order follows *names* so template stacking respects the order the user
        applied them.  All rows are fetched in a single query to avoid N+1
        connection overhead when multiple templates are applied.
        """
        name_list = list(names)
        if not name_list:
            return []
        # Normalize once for case-insensitive matching while keeping the same
        # sequence (including duplicates) for final output reordering.
        normalized_names = [n.lower() for n in name_list]
        # Deduplicate query params to keep the SQL ``IN`` list compact; output
        # ordering and duplicates are restored from ``normalized_names`` below.
        unique_normalized_names = list(dict.fromkeys(normalized_names))
        placeholders = ", ".join("?" for _ in unique_normalized_names)
        rows = self._query(
            "SELECT id, name, cr_adjustment, level_adjustment, type_change, "
            "subtype_added, str_adj, dex_adj, con_adj, int_adj, wis_adj, "
            f"cha_adj, source FROM templates WHERE LOWER(name) IN ({placeholders})",
            unique_normalized_names,
        )
        by_name: dict[str, Template] = {}
        for r in rows:
            by_name[r["name"].lower()] = Template(
                id=r["id"],
                name=r["name"],
                cr_adjustment=r["cr_adjustment"] or 0.0,
                level_adjustment=r["level_adjustment"] or 0,
                type_change=r["type_change"] or "",
                subtype_added=r["subtype_added"] or "",
                str_adj=r["str_adj"] or 0,
                dex_adj=r["dex_adj"] or 0,
                con_adj=r["con_adj"] or 0,
                int_adj=r["int_adj"] or 0,
                wis_adj=r["wis_adj"] or 0,
                cha_adj=r["cha_adj"] or 0,
                source=r["source"] or "",
            )
        return [by_name[n] for n in normalized_names if n in by_name]

    def list_race_variants(
        self, race_name: str, sources: Iterable[str] | None = None
    ) -> list[Variant]:
        """Return the selectable variants for *race_name*.

        Race variants are ``variants`` rows whose ``base_class`` matches the
        race name (case-insensitive).  Returns an empty list when none exist or
        the database is unavailable.
        """
        fragment, params = self._source_filter("source", sources)
        where = "WHERE base_class = ? COLLATE NOCASE"
        query_params: list[object] = [race_name]
        if fragment:
            where += f" AND {fragment}"
            query_params.extend(params)
        rows = self._query(
            "SELECT name, base_class, description, source "
            f"FROM variants {where} ORDER BY name",
            query_params,
        )
        return [
            Variant(
                name=r["name"],
                base_class=r["base_class"] or "",
                description=r["description"] or "",
                source=r["source"] or "",
            )
            for r in rows
            if r["name"]
        ]

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

    def list_spell_names(self) -> list[str]:
        """Return all spell names ordered alphabetically.

        Used by the spell-selection picker in the Spells tab so the user can
        choose from the full seeded catalogue rather than typing free text.
        Reference: PHB Chapters 10-11 (spell lists).
        """
        rows = self._query("SELECT name FROM spells ORDER BY name")
        return [r["name"] for r in rows]

    def list_domains(self) -> list[DomainInfo]:
        """Return all domain entries ordered by name.

        Each :class:`DomainInfo` includes the nine domain-spell slots
        (one per spell level 1-9).  Empty strings signal "no domain spell at
        this level" and are preserved to keep indexing simple.
        Reference: PHB Chapter 11 (domain descriptions).
        """
        rows = self._query(
            "SELECT name, granted_power, spell_1, spell_2, spell_3, spell_4, "
            "spell_5, spell_6, spell_7, spell_8, spell_9 "
            "FROM domains ORDER BY name"
        )
        return [
            DomainInfo(
                name=r["name"],
                granted_power=r["granted_power"] or "",
                domain_spells=[r[f"spell_{i}"] or "" for i in range(1, 10)],
            )
            for r in rows
            if r["name"]
        ]

    def get_domain(self, name: str) -> DomainInfo | None:
        """Return the :class:`DomainInfo` for *name*, or ``None`` if not found.

        Reference: PHB Chapter 11 (domain descriptions).
        """
        rows = self._query(
            "SELECT name, granted_power, spell_1, spell_2, spell_3, spell_4, "
            "spell_5, spell_6, spell_7, spell_8, spell_9 "
            "FROM domains WHERE name = ? COLLATE NOCASE",
            (name,),
        )
        if not rows:
            return None
        r = rows[0]
        return DomainInfo(
            name=r["name"],
            granted_power=r["granted_power"] or "",
            domain_spells=[r[f"spell_{i}"] or "" for i in range(1, 10)],
        )

    def list_deities(self) -> list[str]:
        """Return all deity names ordered alphabetically.

        Used to populate the deity picker in the Spells tab.
        Reference: PHB Chapter 6 (religion).
        """
        rows = self._query("SELECT name FROM deities ORDER BY name")
        return [r["name"] for r in rows]

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
            "int_score, wis_score, cha_score, natural_armor "
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
                natural_armor=int(r["natural_armor"] or 0),
            )
            for r in rows
        ]

    def get_familiar_bonus_records(self) -> list[FamiliarBonus]:
        """Return the structured standard-familiar bonus rows.

        Data is read from the ``familiar_bonuses`` table (seeded from
        :data:`heroforge.logic.familiar.STANDARD_FAMILIAR_BONUSES`).  Returns an
        empty list when the database is unavailable or the table has not been
        seeded yet.
        """
        rows = self._query(
            "SELECT creature_name, value, bonus_kind, target, condition "
            "FROM familiar_bonuses"
        )
        return [
            FamiliarBonus(
                creature_name=r["creature_name"],
                value=int(r["value"] or 0),
                kind=r["bonus_kind"] or "",
                target=r["target"] or "",
                condition=r["condition"] or "",
            )
            for r in rows
            if r["creature_name"]
        ]

    def get_familiar_bonuses(self) -> dict[str, str]:
        """Return a mapping of familiar name (lower-case) → master-bonus text.

        The descriptive text is *generated* from the structured rows via
        :func:`heroforge.logic.familiar.describe_bonus`, so it always reflects
        the stored numbers and can never drift out of sync with the mechanical
        bonus.  Returns an empty dict when the database is unavailable or the
        table has not been seeded yet.
        """
        return {
            bonus.creature_name.lower(): describe_bonus(bonus)
            for bonus in self.get_familiar_bonus_records()
        }

    def get_familiar_master_abilities(self) -> list[FamiliarMasterAbility]:
        """Return the universal familiar master benefits in display order.

        These are the benefits every standard familiar grants its master
        (Alertness, Scry on Familiar, Natural Link).  Data is read from the
        ``familiar_master_abilities`` table, which is seeded from the reference
        workbook's *Special Abilities* → Familiar entry
        (``Class Abilities!A162:A164``).  Returns an empty list when the database
        is unavailable or the table has not been seeded yet; callers can fall
        back to
        :data:`heroforge.logic.familiar.STANDARD_FAMILIAR_MASTER_ABILITIES`.
        """
        rows = self._query(
            "SELECT name, description FROM familiar_master_abilities "
            "ORDER BY sort_order, id"
        )
        return [
            FamiliarMasterAbility(name=r["name"], description=r["description"])
            for r in rows
            if r["name"]
        ]

    # ------------------------------------------------------------------
    # Incarnum abilities
    # ------------------------------------------------------------------

    def list_incarnum_abilities(self) -> list[IncarnumAbility]:
        """Return all incarnum abilities ordered by name.

        Data is read from the ``incarnum_abilities`` table seeded from the
        *Incarnum Abilities* sheet of the reference workbook.  Returns an
        empty list when the database is unavailable or not yet seeded.
        """
        rows = self._query(
            "SELECT name, description FROM incarnum_abilities ORDER BY name"
        )
        return [
            IncarnumAbility(
                name=r["name"],
                description=r["description"] or "",
            )
            for r in rows
            if r["name"]
        ]

    # ------------------------------------------------------------------
    # Vestiges
    # ------------------------------------------------------------------

    def list_vestiges(self, sources: Iterable[str] | None = None) -> list[Vestige]:
        """Return bindable vestige entries ordered by name.

        Data is read from the ``vestiges`` table seeded from the *Binder
        Vestiges* sheet of the reference workbook.  Returns an empty list
        when the database is unavailable or not yet seeded.
        """
        fragment, params = self._source_filter("source", sources)
        where = f"WHERE {fragment}" if fragment else ""
        rows = self._query(
            f"SELECT name, level, source FROM vestiges {where} ORDER BY name",
            params,
        )
        return [
            Vestige(
                name=r["name"],
                level=int(r["level"]) if r["level"] is not None else None,
                source=r["source"] or None,
            )
            for r in rows
            if r["name"]
        ]

    # ------------------------------------------------------------------
    # Marshal auras
    # ------------------------------------------------------------------

    def list_marshal_auras(self, aura_type: str | None = None) -> list[MarshalAura]:
        """Return marshal aura entries ordered by type then name.

        Args:
            aura_type: When provided, limit results to ``'Minor'`` or
                ``'Major'`` auras only.  ``None`` returns all auras.

        Data is read from the ``marshal_auras`` table seeded from the
        *Marshal Auras* sheet of the reference workbook.  Returns an empty
        list when the database is unavailable or not yet seeded.
        """
        if aura_type is not None:
            rows = self._query(
                "SELECT name, type FROM marshal_auras "
                "WHERE type = ? ORDER BY type, name",
                [aura_type],
            )
        else:
            rows = self._query(
                "SELECT name, type FROM marshal_auras ORDER BY type, name"
            )
        return [
            MarshalAura(
                name=r["name"],
                aura_type=r["type"] or "",
            )
            for r in rows
            if r["name"]
        ]

    # ------------------------------------------------------------------
    # Racial abilities
    # ------------------------------------------------------------------

    def list_racial_abilities(
        self, race_name: str | None = None
    ) -> list[RacialAbility]:
        """Return racial special-ability entries.

        Args:
            race_name: When provided, only abilities for that exact race are
                returned (case-sensitive match).  ``None`` returns abilities
                for all races.

        Data is read from the ``racial_abilities`` table seeded from the
        *Racial Abilities* sheet of the reference workbook.  Returns an empty
        list when the database is unavailable or not yet seeded.
        """
        if race_name is not None:
            rows = self._query(
                "SELECT race_name, ability_name, description "
                "FROM racial_abilities WHERE race_name = ? "
                "ORDER BY ability_name",
                [race_name],
            )
        else:
            rows = self._query(
                "SELECT race_name, ability_name, description "
                "FROM racial_abilities ORDER BY race_name, ability_name"
            )
        return [
            RacialAbility(
                race_name=r["race_name"],
                ability_name=r["ability_name"] or "",
                description=r["description"] or "",
            )
            for r in rows
            if r["race_name"]
        ]

    # ------------------------------------------------------------------
    # Graft abilities
    # ------------------------------------------------------------------

    def list_graft_abilities(self, graft_name: str | None = None) -> list[GraftAbility]:
        """Return graft special-ability entries.

        Args:
            graft_name: When provided, only abilities for that exact graft are
                returned (case-sensitive match).  ``None`` returns abilities
                for all grafts.

        Data is read from the ``graft_abilities`` table seeded from the
        *Graft Abilities* sheet of the reference workbook.  Returns an empty
        list when the database is unavailable or not yet seeded.
        """
        if graft_name is not None:
            rows = self._query(
                "SELECT graft_name, ability_name, description "
                "FROM graft_abilities WHERE graft_name = ? "
                "ORDER BY ability_name",
                [graft_name],
            )
        else:
            rows = self._query(
                "SELECT graft_name, ability_name, description "
                "FROM graft_abilities ORDER BY graft_name, ability_name"
            )
        return [
            GraftAbility(
                graft_name=r["graft_name"],
                ability_name=r["ability_name"] or "",
                description=r["description"] or "",
            )
            for r in rows
            if r["graft_name"]
        ]
