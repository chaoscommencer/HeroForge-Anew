"""Persistence layer for HeroForge-Anew :class:`Character` objects.

This module reads and writes the ``character_*`` save tables defined in
:mod:`heroforge.db.schema`.  Two layers are provided:

* :func:`save_character` / :func:`load_character` / :func:`list_characters`
  operate on an open :class:`sqlite3.Connection` (e.g. the shared
  ``heroforge.db``) and may hold many characters.
* :func:`save_character_to_file` / :func:`load_character_from_file` read and
  write a self-contained ``*.hfc`` save file, which is simply a SQLite
  database holding a single character.  This is the new save format that
  legacy ``.hfg`` files are migrated to.

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

from heroforge.db.schema import get_connection, initialize_database
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
            [(cid, buff_name) for buff_name in character.buffs],
        )
        cur.executemany(
            "INSERT INTO character_languages " "(character_id, language) VALUES (?, ?)",
            [(cid, language) for language in character.languages],
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
        br["buff_name"]
        for br in conn.execute(
            "SELECT buff_name FROM character_buffs "
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
        conn = initialize_database(tmp_path)
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
