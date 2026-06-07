"""One-way importer for legacy HeroForge ``.hfg`` save files.

The original spreadsheet-based HeroForge tool stored characters in a plain
text ``.hfg`` file.  v8.0+ treats this format as **read-only legacy input**:
``import_hfg`` parses such a file into a :class:`Character`, which the caller
then migrates to the new ``*.hfc`` format (see
:mod:`heroforge.db.character_repo`).  There is intentionally no writer.

Recognised layout (INI-like, sections in any order)::

    [Character]
    Name=Aedan
    Race=Human
    Templates=Half-Celestial|Fiendish
    Age=25
    Experience=15000

    [AbilityScores]
    STR=16
    DEX=14

    [Classes]
    Fighter=5
    Wizard=2

    [Feats]
    Power Attack
    Cleave

    [Skills]
    Climb=5
    Jump=3.5

    [Equipment]
    Longsword|1|4.0|1|weapon|Masterwork

    [Buffs]
    Bless

    [Languages]
    Common

    [SpellsKnown]
    Wizard|1|Magic Missile

    [SpellsPrepared]
    Wizard|1|Magic Missile

    [Soulmelds]
    Incarnate Avatar|Crown|2

    [Maneuvers]
    Steel Wind|1

    [Stances]
    Punishing Stance

    [Grafts]
    Fiendish Arm|arms|Grants a claw attack

    [Variants]
    Spell Sense

    [Domains]
    Healing
    Sun

    [Vestiges]
    Naberius|4|1

    [MarshalAuras]
    Motivate Dexterity|major|1

    [SkillTricks]
    Acrobatic Backstab

    [PsionicPowers]
    Psion|1|Mind Thrust

    [Companions]
    Animal Companion|Rex|Wolf|Loyal scout

    [Options]
    Gestalt=true
    Fractional BAB=true

    [Wealth]
    platinum=2
    gold=150

    [Attacks]
    Longsword|+8/+3|1d8+4|19-20/x2|-|slashing||Masterwork

    [Enhancements]
    Speed|Circumstance|10|Boots of Striding

    [CustomContent]
    race|Half-Dragon (Brass)|{"size": "Medium"}

    [LGRecords]
    game_log|2024-02-02|Defeated bandits|150|450|AR for The Bandit Kings

    [Traits]
    Aggressive|0

    [Flaws]
    Shaky

    [GameLog]
    2024-01-01T10:00:00|Set out from Verbobonc.

    [Notes]
    Free-text notes, preserved verbatim.

Order is preserved for classes, feats, equipment, buffs, languages, spells,
soulmelds, maneuvers, stances, grafts, traits, variants, domains, vestiges,
marshal auras, skill tricks, psionic powers, companions, attacks, custom
content, Living Greyhawk records, and game-log entries.
"""

from __future__ import annotations

from pathlib import Path

from heroforge.models.character import Character

# Map of [Character] keys to Character string attributes.
_TEXT_FIELDS: dict[str, str] = {
    "name": "name",
    "player": "player",
    "campaign": "campaign",
    "alignment": "alignment",
    "deity": "deity",
    "homeland": "homeland",
    "race": "race",
    "gender": "gender",
    "height": "height",
    "weight": "weight",
    "eyes": "eyes",
    "hair": "hair",
    "skin": "skin",
}

_ABILITIES: frozenset[str] = frozenset({"STR", "DEX", "CON", "INT", "WIS", "CHA"})


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value.strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


def _to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes")


def parse_hfg(text: str) -> Character:
    """Parse the contents of a legacy ``.hfg`` file into a :class:`Character`.

    Args:
        text: Full text of a legacy ``.hfg`` save file.

    Returns:
        A new :class:`Character` (with ``id`` left as ``None``).
    """
    character = Character()
    section = ""
    note_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Section headers.
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            continue

        # Notes preserve every line verbatim (including blanks and comments).
        if section == "notes":
            note_lines.append(line)
            continue

        if not stripped or stripped.startswith("#"):
            continue

        if section == "character":
            key, _, value = stripped.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key in _TEXT_FIELDS:
                setattr(character, _TEXT_FIELDS[key], value)
            elif key == "templates":
                character.templates = [t.strip() for t in value.split("|") if t.strip()]
            elif key == "age":
                character.age = _to_int(value)
            elif key == "experience":
                character.experience = _to_int(value)

        elif section == "abilityscores":
            key, _, value = stripped.partition("=")
            key = key.strip().upper()
            if key in _ABILITIES:
                character.ability_scores[key] = _to_int(value, 10)

        elif section == "classes":
            name, _, value = stripped.partition("=")
            character.classes.append((name.strip(), _to_int(value)))

        elif section == "feats":
            character.feats.append(stripped)

        elif section == "skills":
            name, _, value = stripped.partition("=")
            character.skills[name.strip()] = _to_float(value)

        elif section == "equipment":
            parts = stripped.split("|")
            item: dict[str, object] = {"item_name": parts[0].strip()}
            if len(parts) > 1:
                item["quantity"] = _to_int(parts[1], 1)
            if len(parts) > 2:
                item["weight"] = _to_float(parts[2])
            if len(parts) > 3:
                item["equipped"] = parts[3].strip().lower() in ("1", "true", "yes")
            if len(parts) > 4:
                item["slot"] = parts[4].strip() or None
            if len(parts) > 5:
                item["notes"] = parts[5].strip() or None
            character.equipment.append(item)

        elif section == "buffs":
            character.buffs.append(stripped)

        elif section == "languages":
            character.languages.append(stripped)

        elif section in ("spellsknown", "spellsprepared"):
            parts = stripped.split("|")
            spell: dict[str, object] = {"class_name": parts[0].strip()}
            spell["spell_level"] = _to_int(parts[1]) if len(parts) > 1 else 0
            spell["spell_name"] = parts[2].strip() if len(parts) > 2 else ""
            if section == "spellsknown":
                character.spells_known.append(spell)
            else:
                character.spells_prepared.append(spell)

        elif section == "soulmelds":
            parts = stripped.split("|")
            meld: dict[str, object] = {"soulmeld_name": parts[0].strip()}
            meld["chakra_bound"] = (
                (parts[1].strip() or None) if len(parts) > 1 else None
            )
            meld["essentia_invested"] = _to_int(parts[2]) if len(parts) > 2 else 0
            character.soulmelds.append(meld)

        elif section in ("maneuvers", "stances"):
            parts = stripped.split("|")
            maneuver: dict[str, object] = {"maneuver_name": parts[0].strip()}
            # Stances are always active; maneuvers carry an explicit readied flag.
            maneuver["readied"] = (
                _to_bool(parts[1]) if len(parts) > 1 else section == "stances"
            )
            character.maneuvers.append(maneuver)

        elif section == "grafts":
            parts = stripped.split("|")
            graft: dict[str, object] = {"graft_name": parts[0].strip()}
            graft["body_slot"] = (parts[1].strip() or None) if len(parts) > 1 else None
            graft["notes"] = (parts[2].strip() or None) if len(parts) > 2 else None
            character.grafts.append(graft)

        elif section in ("traits", "flaws"):
            parts = stripped.split("|")
            is_flaw = section == "flaws" or (len(parts) > 1 and _to_bool(parts[1]))
            character.traits.append(
                {"trait_name": parts[0].strip(), "is_flaw": is_flaw}
            )

        elif section == "variants":
            character.variants.append(stripped)

        elif section == "domains":
            character.domains.append(stripped)

        elif section == "vestiges":
            parts = stripped.split("|")
            vestige: dict[str, object] = {"vestige_name": parts[0].strip()}
            vestige["level"] = _to_int(parts[1]) if len(parts) > 1 else 0
            vestige["bound"] = _to_bool(parts[2]) if len(parts) > 2 else True
            character.vestiges.append(vestige)

        elif section == "marshalauras":
            parts = stripped.split("|")
            aura: dict[str, object] = {"aura_name": parts[0].strip()}
            aura["aura_type"] = (parts[1].strip() or None) if len(parts) > 1 else None
            aura["active"] = _to_bool(parts[2]) if len(parts) > 2 else False
            character.marshal_auras.append(aura)

        elif section == "skilltricks":
            character.skill_tricks.append(stripped)

        elif section == "psionicpowers":
            parts = stripped.split("|")
            power: dict[str, object] = {"class_name": parts[0].strip()}
            power["power_level"] = _to_int(parts[1]) if len(parts) > 1 else 0
            power["power_name"] = parts[2].strip() if len(parts) > 2 else ""
            character.psionic_powers.append(power)

        elif section in ("companions", "animalcompanion", "familiar"):
            parts = stripped.split("|")
            if section == "companions":
                companion: dict[str, object] = {
                    "companion_type": parts[0].strip(),
                    "name": (parts[1].strip() or None) if len(parts) > 1 else None,
                    "creature": (parts[2].strip() or None) if len(parts) > 2 else None,
                    "notes": (parts[3].strip() or None) if len(parts) > 3 else None,
                }
            else:
                companion = {
                    "companion_type": (
                        "Animal Companion"
                        if section == "animalcompanion"
                        else "Familiar"
                    ),
                    "name": (parts[0].strip() or None) if parts else None,
                    "creature": (parts[1].strip() or None) if len(parts) > 1 else None,
                    "notes": (parts[2].strip() or None) if len(parts) > 2 else None,
                }
            character.companions.append(companion)

        elif section == "options":
            key, _, value = stripped.partition("=")
            character.options[key.strip()] = value.strip()

        elif section == "wealth":
            key, _, value = stripped.partition("=")
            character.wealth[key.strip()] = _to_float(value)

        elif section == "attacks":
            parts = [p.strip() for p in stripped.split("|")]
            parts += [""] * (8 - len(parts))
            character.attacks.append(
                {
                    "weapon_name": parts[0],
                    "attack_bonus": parts[1] or None,
                    "damage": parts[2] or None,
                    "critical": parts[3] or None,
                    "range_increment": parts[4] or None,
                    "damage_type": parts[5] or None,
                    "ammunition": parts[6] or None,
                    "notes": parts[7] or None,
                }
            )

        elif section == "enhancements":
            parts = stripped.split("|")
            character.enhancements.append(
                {
                    "target": parts[0].strip(),
                    "bonus_type": (
                        (parts[1].strip() or None) if len(parts) > 1 else None
                    ),
                    "value": _to_int(parts[2]) if len(parts) > 2 else 0,
                    "notes": (parts[3].strip() or None) if len(parts) > 3 else None,
                }
            )

        elif section in ("customcontent", "custom"):
            parts = stripped.split("|")
            character.custom_content.append(
                {
                    "content_type": parts[0].strip(),
                    "name": parts[1].strip() if len(parts) > 1 else "",
                    "definition": (
                        (parts[2].strip() or None) if len(parts) > 2 else None
                    ),
                }
            )

        elif section in ("lgrecords", "lg"):
            parts = stripped.split("|")
            character.lg_records.append(
                {
                    "record_type": parts[0].strip(),
                    "event_date": (
                        (parts[1].strip() or None) if len(parts) > 1 else None
                    ),
                    "description": (
                        (parts[2].strip() or None) if len(parts) > 2 else None
                    ),
                    "gp_change": _to_float(parts[3]) if len(parts) > 3 else 0.0,
                    "xp_change": _to_float(parts[4]) if len(parts) > 4 else 0.0,
                    "notes": (parts[5].strip() or None) if len(parts) > 5 else None,
                }
            )

        elif section == "gamelog":
            timestamp, sep, content = stripped.partition("|")
            if sep:
                character.game_log.append(
                    {"timestamp": timestamp.strip(), "content": content.strip()}
                )
            else:
                character.game_log.append({"timestamp": "", "content": stripped})

    if note_lines:
        character.notes = "\n".join(note_lines)

    return character


def import_hfg(path: str | Path) -> Character:
    """Read and parse a legacy ``.hfg`` save file.

    Args:
        path: Path to the legacy ``.hfg`` file.

    Returns:
        A new :class:`Character` reconstructed from the legacy file.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return parse_hfg(text)
