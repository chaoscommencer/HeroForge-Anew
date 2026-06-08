"""Plain-text character sheet export for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from heroforge.logic.ability_scores import ability_modifier

if TYPE_CHECKING:
    from heroforge.logic.derived_stats import DerivedStats
    from heroforge.models.character import Character


def character_sheet_data(
    character: Character,
    derived: DerivedStats | None = None,
) -> dict:  # type: ignore[type-arg]
    """Build the :func:`export_character_sheet_text` payload for *character*.

    This bridges the :class:`~heroforge.models.character.Character` model and
    the optional :class:`~heroforge.logic.derived_stats.DerivedStats` snapshot
    into the flat ``dict`` the text exporter expects, so combat fields render
    real computed values instead of placeholders.
    """
    data: dict = {  # type: ignore[type-arg]
        "name": character.name,
        "player": character.player,
        "campaign": character.campaign,
        "alignment": character.alignment,
        "race": character.race,
        "classes": list(character.classes),
        "total_level": character.total_level,
        "experience": character.experience,
        "deity": character.deity,
        "homeland": character.homeland,
        "gender": character.gender,
        "age": character.age,
        "height": character.height,
        "weight": character.weight,
        "eyes": character.eyes,
        "hair": character.hair,
        "skin": character.skin,
        "ability_scores": dict(character.ability_scores),
        "feats": list(character.feats),
        "skills": dict(character.skills),
        "equipment": [dict(item) for item in character.equipment],
        "languages": list(character.languages),
        "notes": character.notes,
    }
    if derived is not None:
        data.update(
            {
                "initiative": derived.initiative,
                "bab": derived.base_attack_bonus,
                "fort": derived.fortitude,
                "ref": derived.reflex,
                "will": derived.will,
                "ac": derived.armor_class,
                "touch_ac": derived.touch_ac,
                "flat_footed_ac": derived.flat_footed_ac,
            }
        )
    return data


def export_character_sheet_text(character_data: dict) -> str:  # type: ignore[type-arg]
    """Format a plain-text character sheet from *character_data*.

    *character_data* is expected to contain the following keys (all optional
    with sensible defaults):

    - ``name`` (str)
    - ``player`` (str)
    - ``campaign`` (str)
    - ``alignment`` (str)
    - ``race`` (str)
    - ``classes`` (list of ``(class_name, level)`` tuples)
    - ``total_level`` (int)
    - ``experience`` (int)
    - ``deity`` (str)
    - ``homeland`` (str)
    - ``gender`` (str)
    - ``age`` (int)
    - ``height`` (str)
    - ``weight`` (str)
    - ``eyes`` (str)
    - ``hair`` (str)
    - ``skin`` (str)
    - ``ability_scores`` (dict of ability name → score)
    - ``hp`` (int)
    - ``speed`` (int)
    - ``initiative`` (int)
    - ``bab`` (int)
    - ``fort`` (int)
    - ``ref`` (int)
    - ``will`` (int)
    - ``ac`` (int)
    - ``touch_ac`` (int)
    - ``flat_footed_ac`` (int)
    - ``feats`` (list of str)
    - ``skills`` (dict of skill name → ranks)
    - ``equipment`` (list of item dicts with ``'item_name'`` and ``'quantity'``)
    - ``languages`` (list of str)
    - ``notes`` (str)

    Returns:
        Multi-line plain-text character sheet string.
    """
    sep = "=" * 60
    line = "-" * 60

    def get(key: str, default: object = "") -> object:
        return character_data.get(key, default)

    name = get("name", "Unknown Hero")
    player = get("player", "")
    campaign = get("campaign", "")
    alignment = get("alignment", "")
    race = get("race", "")
    classes: list[tuple[str, int]] = character_data.get("classes", [])  # type: ignore[assignment]
    class_str = ", ".join(f"{cls} {lvl}" for cls, lvl in classes) or "—"
    total_level = get("total_level", sum(lvl for _, lvl in classes))
    xp = get("experience", 0)
    deity = get("deity", "")
    homeland = get("homeland", "")

    ability_scores: dict[str, int] = character_data.get(  # type: ignore[assignment]
        "ability_scores",
        {a: 10 for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")},
    )

    lines: list[str] = []

    lines.append(sep)
    lines.append("  CHARACTER SHEET – HeroForge Anew")
    lines.append(sep)
    lines.append(f"Name       : {name}")
    lines.append(f"Player     : {player}    Campaign: {campaign}")
    lines.append(f"Race       : {race}    Alignment: {alignment}")
    lines.append(f"Class(es)  : {class_str}    Level: {total_level}")
    lines.append(f"Experience : {xp}")
    lines.append(f"Deity      : {deity}    Homeland: {homeland}")
    lines.append(line)

    # Ability scores
    lines.append("ABILITY SCORES")
    for ability in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        score = ability_scores.get(ability, 10)
        mod = ability_modifier(score)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        lines.append(f"  {ability}: {score:2d}  (mod {mod_str})")
    lines.append(line)

    # Combat stats
    hp = get("hp", "?")
    speed = get("speed", 30)
    init = get("initiative", "?")
    bab = get("bab", "?")
    fort = get("fort", "?")
    ref = get("ref", "?")
    will = get("will", "?")
    ac = get("ac", "?")
    tac = get("touch_ac", "?")
    ffac = get("flat_footed_ac", "?")

    lines.append("COMBAT")
    lines.append(f"  HP: {hp}    Speed: {speed} ft.    Initiative: {init}")
    lines.append(f"  BAB: {bab}    Fort: {fort}    Ref: {ref}    Will: {will}")
    lines.append(f"  AC: {ac}    Touch: {tac}    Flat-Footed: {ffac}")
    lines.append(line)

    # Feats
    feats: list[str] = character_data.get("feats", [])  # type: ignore[assignment]
    lines.append("FEATS")
    if feats:
        for feat in feats:
            lines.append(f"  • {feat}")
    else:
        lines.append("  (none)")
    lines.append(line)

    # Skills
    skills: dict[str, float] = character_data.get("skills", {})  # type: ignore[assignment]
    lines.append("SKILLS")
    if skills:
        for skill_name, ranks in sorted(skills.items()):
            lines.append(f"  {skill_name}: {ranks} ranks")
    else:
        lines.append("  (none)")
    lines.append(line)

    # Equipment
    equipment: list[dict] = character_data.get("equipment", [])  # type: ignore[assignment]
    lines.append("EQUIPMENT")
    if equipment:
        for item in equipment:
            qty = item.get("quantity", 1)
            iname = item.get("item_name", "Unknown item")
            lines.append(f"  {iname} ×{qty}")
    else:
        lines.append("  (none)")
    lines.append(line)

    # Languages
    languages: list[str] = character_data.get("languages", [])  # type: ignore[assignment]
    lines.append(f"LANGUAGES: {', '.join(languages) if languages else '(none)'}")
    lines.append(line)

    # Notes
    notes = str(get("notes", ""))
    if notes.strip():
        lines.append("NOTES")
        lines.append(notes)
        lines.append(line)

    lines.append(sep)
    return "\n".join(lines)
