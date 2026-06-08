"""Persistence layer for HeroForge-Anew :class:`Character` objects.

This module reads and writes the ``character_*`` save tables defined in
:mod:`heroforge.db.schema`.  Character data is **volatile, user-owned state**
and is deliberately kept out of the source-of-truth game database
(``heroforge.db``); it lives only in standalone ``*.hfc`` save files.  Two
layers are provided:

* :func:`save_character` / :func:`load_character` / :func:`list_characters`
  operate on an open :class:`sqlite3.Connection` to a character save database
  (created via :func:`heroforge.db.schema.initialize_character_database`).
* :func:`save_character_to_file` / :func:`load_character_from_file` read and
  write a self-contained ``*.hfc`` save file, which is simply a SQLite
  database holding a single character with only the ``character_*`` tables.
  This is the new save format that legacy ``.hfg`` files are migrated to.

All writes are transactional: related ``character_*`` rows are replaced
atomically so a failed save never leaves a partially written character.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from heroforge.db.schema import get_connection, initialize_character_database
from heroforge.models.character import Character

# Related tables that are fully replaced whenever a character is saved.
_RELATED_TABLES: tuple[str, ...] = (
    "character_ability_scores",
    "character_classes",
    "character_feats",
    "character_skills",
    "character_equipment",
    "character_buffs",
    "character_languages",
    "character_spells_known",
    "character_spells_prepared",
    "character_soulmelds",
    "character_maneuvers",
    "character_grafts",
    "character_traits",
    "character_variants",
    "character_domains",
    "character_vestiges",
    "character_marshal_auras",
    "character_skill_tricks",
    "character_psionic_powers",
    "character_companions",
    "character_options",
    "character_wealth",
    "character_attacks",
    "character_enhancements",
    "character_custom_content",
    "character_lg_records",
    "character_notes",
)

_ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Connection-level persistence
# ---------------------------------------------------------------------------


def save_character(conn: sqlite3.Connection, character: Character) -> int:
    """Insert or update *character* and its related rows in *conn*.

    The whole operation runs in a single transaction.  When *character* has
    no ``id`` a new row is inserted and the assigned id is written back onto
    the object.  All related ``character_*`` rows are deleted and re-inserted
    so the saved state always matches the in-memory object exactly.

    Args:
        conn: Open connection to a database carrying the character schema.
        character: The character to persist.

    Returns:
        The database id of the saved character.
    """
    templates_json = json.dumps(list(character.templates))
    try:
        cur = conn.cursor()
        if character.id is None:
            now = _now()
            cur.execute(
                """
                INSERT INTO characters (
                    name, player, campaign, alignment, deity, homeland, race,
                    templates, gender, age, height, weight, eyes, hair, skin,
                    experience, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    character.name,
                    character.player,
                    character.campaign,
                    character.alignment,
                    character.deity,
                    character.homeland,
                    character.race,
                    templates_json,
                    character.gender,
                    character.age,
                    character.height,
                    character.weight,
                    character.eyes,
                    character.hair,
                    character.skin,
                    character.experience,
                    character.notes,
                    now,
                    now,
                ),
            )
            character.id = int(cur.lastrowid)  # type: ignore[arg-type]
        else:
            cur.execute(
                """
                UPDATE characters SET
                    name = ?, player = ?, campaign = ?, alignment = ?,
                    deity = ?, homeland = ?, race = ?, templates = ?,
                    gender = ?, age = ?, height = ?, weight = ?, eyes = ?,
                    hair = ?, skin = ?, experience = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    character.name,
                    character.player,
                    character.campaign,
                    character.alignment,
                    character.deity,
                    character.homeland,
                    character.race,
                    templates_json,
                    character.gender,
                    character.age,
                    character.height,
                    character.weight,
                    character.eyes,
                    character.hair,
                    character.skin,
                    character.experience,
                    character.notes,
                    _now(),
                    character.id,
                ),
            )

        cid = character.id
        for table in _RELATED_TABLES:
            cur.execute(f"DELETE FROM {table} WHERE character_id = ?", (cid,))

        cur.executemany(
            "INSERT INTO character_ability_scores "
            "(character_id, ability, base_score) VALUES (?, ?, ?)",
            [
                (cid, ability, int(character.ability_scores.get(ability, 10)))
                for ability in _ABILITIES
            ],
        )
        cur.executemany(
            "INSERT INTO character_classes "
            "(character_id, class_name, level, order_taken) VALUES (?, ?, ?, ?)",
            [
                (cid, class_name, int(level), order)
                for order, (class_name, level) in enumerate(character.classes)
            ],
        )
        cur.executemany(
            "INSERT INTO character_feats "
            "(character_id, feat_name, order_taken) VALUES (?, ?, ?)",
            [
                (cid, feat_name, order)
                for order, feat_name in enumerate(character.feats)
            ],
        )
        cur.executemany(
            "INSERT INTO character_skills "
            "(character_id, skill_name, ranks) VALUES (?, ?, ?)",
            [
                (cid, skill_name, float(ranks))
                for skill_name, ranks in character.skills.items()
            ],
        )
        cur.executemany(
            "INSERT INTO character_equipment "
            "(character_id, item_name, quantity, weight, equipped, slot, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cid,
                    str(item.get("item_name", "")),
                    int(item.get("quantity", 1)),
                    float(item.get("weight", 0)),
                    1 if item.get("equipped") else 0,
                    item.get("slot"),
                    item.get("notes"),
                )
                for item in character.equipment
            ],
        )
        cur.executemany(
            "INSERT INTO character_buffs (character_id, buff_name) VALUES (?, ?)",
            [(cid, buff["name"]) for buff in character.buffs],
        )
        cur.executemany(
            "INSERT INTO character_languages " "(character_id, language) VALUES (?, ?)",
            [(cid, language) for language in character.languages],
        )
        cur.executemany(
            "INSERT INTO character_spells_known "
            "(character_id, class_name, spell_level, spell_name) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(spell.get("class_name", "")),
                    int(spell.get("spell_level", 0)),
                    str(spell.get("spell_name", "")),
                )
                for spell in character.spells_known
            ],
        )
        cur.executemany(
            "INSERT INTO character_spells_prepared "
            "(character_id, class_name, spell_level, spell_name) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(spell.get("class_name", "")),
                    int(spell.get("spell_level", 0)),
                    str(spell.get("spell_name", "")),
                )
                for spell in character.spells_prepared
            ],
        )
        cur.executemany(
            "INSERT INTO character_soulmelds "
            "(character_id, soulmeld_name, chakra_bound, essentia_invested) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(meld.get("soulmeld_name", "")),
                    meld.get("chakra_bound"),
                    int(meld.get("essentia_invested", 0)),
                )
                for meld in character.soulmelds
            ],
        )
        cur.executemany(
            "INSERT INTO character_maneuvers "
            "(character_id, maneuver_name, readied) VALUES (?, ?, ?)",
            [
                (
                    cid,
                    str(maneuver.get("maneuver_name", "")),
                    1 if maneuver.get("readied") else 0,
                )
                for maneuver in character.maneuvers
            ],
        )
        cur.executemany(
            "INSERT INTO character_grafts "
            "(character_id, graft_name, body_slot, notes) VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(graft.get("graft_name", "")),
                    graft.get("body_slot"),
                    graft.get("notes"),
                )
                for graft in character.grafts
            ],
        )
        cur.executemany(
            "INSERT INTO character_traits "
            "(character_id, trait_name, is_flaw) VALUES (?, ?, ?)",
            [
                (
                    cid,
                    str(trait.get("trait_name", "")),
                    1 if trait.get("is_flaw") else 0,
                )
                for trait in character.traits
            ],
        )
        cur.executemany(
            "INSERT INTO character_variants "
            "(character_id, variant_name, class_name, notes) VALUES (?, ?, ?, ?)",
            [
                (
                    (cid, str(variant), None, None)
                    if isinstance(variant, str)
                    else (
                        cid,
                        str(variant.get("variant_name", "")),
                        variant.get("class_name"),
                        variant.get("notes"),
                    )
                )
                for variant in character.variants
            ],
        )
        cur.executemany(
            "INSERT INTO character_domains "
            "(character_id, domain_name, slot) VALUES (?, ?, ?)",
            [
                (cid, str(domain), order)
                for order, domain in enumerate(character.domains)
            ],
        )
        cur.executemany(
            "INSERT INTO character_vestiges "
            "(character_id, vestige_name, level, bound) VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(vestige.get("vestige_name", "")),
                    int(vestige.get("level", 0)),
                    1 if vestige.get("bound", True) else 0,
                )
                for vestige in character.vestiges
            ],
        )
        cur.executemany(
            "INSERT INTO character_marshal_auras "
            "(character_id, aura_name, aura_type, active) VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(aura.get("aura_name", "")),
                    aura.get("aura_type"),
                    1 if aura.get("active") else 0,
                )
                for aura in character.marshal_auras
            ],
        )
        cur.executemany(
            "INSERT INTO character_skill_tricks "
            "(character_id, trick_name) VALUES (?, ?)",
            [(cid, str(trick)) for trick in character.skill_tricks],
        )
        cur.executemany(
            "INSERT INTO character_psionic_powers "
            "(character_id, class_name, power_level, power_name) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(power.get("class_name", "")),
                    int(power.get("power_level", 0)),
                    str(power.get("power_name", "")),
                )
                for power in character.psionic_powers
            ],
        )
        cur.executemany(
            "INSERT INTO character_companions "
            "(character_id, companion_type, name, creature, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    cid,
                    str(companion.get("companion_type", "")),
                    companion.get("name"),
                    companion.get("creature"),
                    companion.get("notes"),
                )
                for companion in character.companions
            ],
        )
        cur.executemany(
            "INSERT INTO character_options "
            "(character_id, option_name, value) VALUES (?, ?, ?)",
            [
                (cid, str(name), None if value is None else str(value))
                for name, value in character.options.items()
            ],
        )
        cur.executemany(
            "INSERT INTO character_wealth "
            "(character_id, kind, amount) VALUES (?, ?, ?)",
            [
                (cid, str(kind), float(amount))
                for kind, amount in character.wealth.items()
            ],
        )
        cur.executemany(
            "INSERT INTO character_attacks "
            "(character_id, weapon_name, attack_bonus, damage, critical, "
            "range_increment, damage_type, ammunition, notes, order_taken) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cid,
                    str(attack.get("weapon_name", "")),
                    attack.get("attack_bonus"),
                    attack.get("damage"),
                    attack.get("critical"),
                    attack.get("range_increment"),
                    attack.get("damage_type"),
                    attack.get("ammunition"),
                    attack.get("notes"),
                    order,
                )
                for order, attack in enumerate(character.attacks)
            ],
        )
        cur.executemany(
            "INSERT INTO character_enhancements "
            "(character_id, target, bonus_type, value, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    cid,
                    str(enh.get("target", "")),
                    enh.get("bonus_type"),
                    int(enh.get("value", 0)),
                    enh.get("notes"),
                )
                for enh in character.enhancements
            ],
        )
        cur.executemany(
            "INSERT INTO character_custom_content "
            "(character_id, content_type, name, definition) VALUES (?, ?, ?, ?)",
            [
                (
                    cid,
                    str(content.get("content_type", "")),
                    str(content.get("name", "")),
                    content.get("definition"),
                )
                for content in character.custom_content
            ],
        )
        cur.executemany(
            "INSERT INTO character_lg_records "
            "(character_id, record_type, event_date, description, gp_change, "
            "xp_change, notes, order_taken) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cid,
                    str(record.get("record_type", "")),
                    record.get("event_date"),
                    record.get("description"),
                    float(record.get("gp_change", 0)),
                    float(record.get("xp_change", 0)),
                    record.get("notes"),
                    order,
                )
                for order, record in enumerate(character.lg_records)
            ],
        )
        cur.executemany(
            "INSERT INTO character_notes "
            "(character_id, timestamp, content) VALUES (?, ?, ?)",
            [
                (
                    cid,
                    str(entry.get("timestamp", "")),
                    str(entry.get("content", "")),
                )
                for entry in character.game_log
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return int(cid)


def load_character(conn: sqlite3.Connection, character_id: int) -> Character:
    """Reconstruct a full :class:`Character` from *conn* by id.

    Args:
        conn: Open connection to a database carrying the character schema.
        character_id: Primary key of the character to load.

    Returns:
        The fully populated :class:`Character`.

    Raises:
        KeyError: If no character with *character_id* exists.
    """
    row = conn.execute(
        "SELECT * FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"No character with id {character_id}")

    templates_raw = row["templates"]
    try:
        templates = list(json.loads(templates_raw)) if templates_raw else []
    except (TypeError, ValueError):
        templates = []

    character = Character(
        id=row["id"],
        name=row["name"] or "",
        player=row["player"] or "",
        campaign=row["campaign"] or "",
        alignment=row["alignment"] or "",
        deity=row["deity"] or "",
        homeland=row["homeland"] or "",
        race=row["race"] or "",
        templates=templates,
        gender=row["gender"] or "",
        age=row["age"] or 0,
        height=row["height"] or "",
        weight=row["weight"] or "",
        eyes=row["eyes"] or "",
        hair=row["hair"] or "",
        skin=row["skin"] or "",
        experience=row["experience"] or 0,
        notes=row["notes"] or "",
    )

    ability_rows = conn.execute(
        "SELECT ability, base_score FROM character_ability_scores "
        "WHERE character_id = ?",
        (character_id,),
    ).fetchall()
    for ar in ability_rows:
        character.ability_scores[ar["ability"]] = ar["base_score"]

    character.classes = [
        (cr["class_name"], cr["level"])
        for cr in conn.execute(
            "SELECT class_name, level FROM character_classes "
            "WHERE character_id = ? ORDER BY order_taken",
            (character_id,),
        ).fetchall()
    ]

    character.feats = [
        fr["feat_name"]
        for fr in conn.execute(
            "SELECT feat_name FROM character_feats "
            "WHERE character_id = ? ORDER BY order_taken",
            (character_id,),
        ).fetchall()
    ]

    character.skills = {
        sr["skill_name"]: sr["ranks"]
        for sr in conn.execute(
            "SELECT skill_name, ranks FROM character_skills WHERE character_id = ?",
            (character_id,),
        ).fetchall()
    }

    character.equipment = [
        {
            "item_name": er["item_name"],
            "quantity": er["quantity"],
            "weight": er["weight"],
            "equipped": bool(er["equipped"]),
            "slot": er["slot"],
            "notes": er["notes"],
        }
        for er in conn.execute(
            "SELECT item_name, quantity, weight, equipped, slot, notes "
            "FROM character_equipment WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.buffs = [
        {"id": br["id"], "name": br["buff_name"]}
        for br in conn.execute(
            "SELECT id, buff_name FROM character_buffs "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.languages = [
        lr["language"]
        for lr in conn.execute(
            "SELECT language FROM character_languages "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.spells_known = [
        {
            "class_name": sr["class_name"],
            "spell_level": sr["spell_level"],
            "spell_name": sr["spell_name"],
        }
        for sr in conn.execute(
            "SELECT class_name, spell_level, spell_name FROM character_spells_known "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.spells_prepared = [
        {
            "class_name": sr["class_name"],
            "spell_level": sr["spell_level"],
            "spell_name": sr["spell_name"],
        }
        for sr in conn.execute(
            "SELECT class_name, spell_level, spell_name FROM character_spells_prepared "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.soulmelds = [
        {
            "soulmeld_name": mr["soulmeld_name"],
            "chakra_bound": mr["chakra_bound"],
            "essentia_invested": mr["essentia_invested"],
        }
        for mr in conn.execute(
            "SELECT soulmeld_name, chakra_bound, essentia_invested "
            "FROM character_soulmelds WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.maneuvers = [
        {"maneuver_name": mr["maneuver_name"], "readied": bool(mr["readied"])}
        for mr in conn.execute(
            "SELECT maneuver_name, readied FROM character_maneuvers "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.grafts = [
        {
            "graft_name": gr["graft_name"],
            "body_slot": gr["body_slot"],
            "notes": gr["notes"],
        }
        for gr in conn.execute(
            "SELECT graft_name, body_slot, notes FROM character_grafts "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.traits = [
        {"trait_name": tr["trait_name"], "is_flaw": bool(tr["is_flaw"])}
        for tr in conn.execute(
            "SELECT trait_name, is_flaw FROM character_traits "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.variants = [
        (
            vr["variant_name"]
            if vr["class_name"] is None and vr["notes"] is None
            else {
                "variant_name": vr["variant_name"],
                "class_name": vr["class_name"],
                "notes": vr["notes"],
            }
        )
        for vr in conn.execute(
            "SELECT variant_name, class_name, notes FROM character_variants "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.domains = [
        dr["domain_name"]
        for dr in conn.execute(
            "SELECT domain_name FROM character_domains "
            "WHERE character_id = ? ORDER BY slot, id",
            (character_id,),
        ).fetchall()
    ]

    character.vestiges = [
        {
            "vestige_name": vr["vestige_name"],
            "level": vr["level"],
            "bound": bool(vr["bound"]),
        }
        for vr in conn.execute(
            "SELECT vestige_name, level, bound FROM character_vestiges "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.marshal_auras = [
        {
            "aura_name": ar["aura_name"],
            "aura_type": ar["aura_type"],
            "active": bool(ar["active"]),
        }
        for ar in conn.execute(
            "SELECT aura_name, aura_type, active FROM character_marshal_auras "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.skill_tricks = [
        tr["trick_name"]
        for tr in conn.execute(
            "SELECT trick_name FROM character_skill_tricks "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.psionic_powers = [
        {
            "class_name": pr["class_name"],
            "power_level": pr["power_level"],
            "power_name": pr["power_name"],
        }
        for pr in conn.execute(
            "SELECT class_name, power_level, power_name FROM character_psionic_powers "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.companions = [
        {
            "companion_type": cr["companion_type"],
            "name": cr["name"],
            "creature": cr["creature"],
            "notes": cr["notes"],
        }
        for cr in conn.execute(
            "SELECT companion_type, name, creature, notes FROM character_companions "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.options = {
        orow["option_name"]: orow["value"]
        for orow in conn.execute(
            "SELECT option_name, value FROM character_options "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    }

    character.wealth = {
        wr["kind"]: wr["amount"]
        for wr in conn.execute(
            "SELECT kind, amount FROM character_wealth "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    }

    character.attacks = [
        {
            "weapon_name": atk["weapon_name"],
            "attack_bonus": atk["attack_bonus"],
            "damage": atk["damage"],
            "critical": atk["critical"],
            "range_increment": atk["range_increment"],
            "damage_type": atk["damage_type"],
            "ammunition": atk["ammunition"],
            "notes": atk["notes"],
        }
        for atk in conn.execute(
            "SELECT weapon_name, attack_bonus, damage, critical, range_increment, "
            "damage_type, ammunition, notes FROM character_attacks "
            "WHERE character_id = ? ORDER BY order_taken, id",
            (character_id,),
        ).fetchall()
    ]

    character.enhancements = [
        {
            "target": en["target"],
            "bonus_type": en["bonus_type"],
            "value": en["value"],
            "notes": en["notes"],
        }
        for en in conn.execute(
            "SELECT target, bonus_type, value, notes FROM character_enhancements "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.custom_content = [
        {
            "content_type": ccr["content_type"],
            "name": ccr["name"],
            "definition": ccr["definition"],
        }
        for ccr in conn.execute(
            "SELECT content_type, name, definition FROM character_custom_content "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    character.lg_records = [
        {
            "record_type": lr["record_type"],
            "event_date": lr["event_date"],
            "description": lr["description"],
            "gp_change": lr["gp_change"],
            "xp_change": lr["xp_change"],
            "notes": lr["notes"],
        }
        for lr in conn.execute(
            "SELECT record_type, event_date, description, gp_change, xp_change, notes "
            "FROM character_lg_records WHERE character_id = ? ORDER BY order_taken, id",
            (character_id,),
        ).fetchall()
    ]

    character.game_log = [
        {"timestamp": nr["timestamp"], "content": nr["content"]}
        for nr in conn.execute(
            "SELECT timestamp, content FROM character_notes "
            "WHERE character_id = ? ORDER BY id",
            (character_id,),
        ).fetchall()
    ]

    return character


def list_characters(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """Return ``(id, name)`` for every saved character ordered by id."""
    return [
        (r["id"], r["name"])
        for r in conn.execute("SELECT id, name FROM characters ORDER BY id").fetchall()
    ]


# ---------------------------------------------------------------------------
# File-level persistence (the new ``*.hfc`` format)
# ---------------------------------------------------------------------------


def save_character_to_file(character: Character, path: str | Path) -> int:
    """Write *character* to a self-contained ``*.hfc`` SQLite save file.

    The file is written atomically (to a temporary file in the same
    directory, then renamed) so an interrupted save never corrupts an
    existing file.  A ``*.hfc`` file always holds exactly one character.

    Args:
        character: The character to persist.
        path: Destination path for the save file.

    Returns:
        The database id assigned to the character inside the file.
    """
    path = Path(path)
    directory = path.parent if str(path.parent) else Path(".")
    directory.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(suffix=".hfc", dir=str(directory))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        conn = initialize_character_database(tmp_path)
        try:
            # A .hfc holds exactly one character; assign it id 1 in the file.
            character.id = None
            cid = save_character(conn, character)
        finally:
            conn.close()
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return cid


def load_character_from_file(path: str | Path) -> Character:
    """Load the character stored in a ``*.hfc`` save file.

    Args:
        path: Path to the ``*.hfc`` save file.

    Returns:
        The fully populated :class:`Character`.

    Raises:
        FileNotFoundError: If *path* does not exist.
        KeyError: If the save file contains no character.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    conn = get_connection(path)
    try:
        row = conn.execute("SELECT id FROM characters ORDER BY id LIMIT 1").fetchone()
        if row is None:
            raise KeyError(f"Save file contains no character: {path}")
        return load_character(conn, row["id"])
    finally:
        conn.close()
