"""Character sheet export (plain text and PDF) for HeroForge-Anew."""

from __future__ import annotations

import os
import textwrap
from typing import TYPE_CHECKING, BinaryIO

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


def export_character_sheet_pdf(
    character_data: dict,  # type: ignore[type-arg]
    path: str | os.PathLike[str] | BinaryIO,
) -> str | os.PathLike[str] | BinaryIO:
    """Render *character_data* to a PDF character sheet at *path*.

    The PDF reuses the exact layout produced by
    :func:`export_character_sheet_text`, drawn in a monospaced font so the
    columns line up, with automatic page breaks for long sheets.

    Args:
        character_data: The same payload accepted by
            :func:`export_character_sheet_text` (see
            :func:`character_sheet_data`).
        path: Destination for the PDF.  May be a filesystem path (``str`` or
            :class:`os.PathLike`) or an already-open binary file object.

    Returns:
        The *path* argument, so callers can chain or assert on it.

    Raises:
        RuntimeError: If the ``reportlab`` PDF extra is not installed.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise RuntimeError(
            "PDF export requires the 'reportlab' package; "
            "install it with 'pip install heroforge[pdf]' or "
            "'pip install reportlab'."
        ) from exc

    text = export_character_sheet_text(character_data)

    # reportlab accepts a filename or a binary file object; normalise PathLike
    # to a string while leaving str paths and file objects untouched.
    destination = os.fspath(path) if isinstance(path, os.PathLike) else path

    page_width, page_height = letter
    margin = 54.0  # 0.75 inch
    font_name = "Courier"
    font_size = 9.0
    line_height = font_size * 1.25

    pdf = canvas.Canvas(destination, pagesize=letter)
    name = str(character_data.get("name", "")).strip() or "Character Sheet"
    pdf.setTitle(f"{name} – Character Sheet")
    pdf.setFont(font_name, font_size)
    usable_width = page_width - (2 * margin)
    char_width = pdf.stringWidth("M", font_name, font_size) or font_size
    max_chars = max(1, int(usable_width // char_width))

    y = page_height - margin
    for raw_line in text.split("\n"):
        wrapped_lines = textwrap.wrap(
            raw_line,
            width=max_chars,
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]
        for line in wrapped_lines:
            if y < margin:
                pdf.showPage()
                pdf.setFont(font_name, font_size)
                y = page_height - margin
            pdf.drawString(margin, y, line)
            y -= line_height

    pdf.showPage()
    pdf.save()
    return path


#: Printable width (in characters) of a single Table Tent panel.
TABLE_TENT_WIDTH = 60


def table_tent_data(
    character: Character,
    derived: DerivedStats | None = None,
) -> dict:  # type: ignore[type-arg]
    """Build the :func:`export_table_tent_text` payload for *character*.

    The Table Tent currently reuses the full :func:`character_sheet_data`
    payload so both exporters share a single model→dict bridge.
    """
    return character_sheet_data(character, derived)


def _signed(value: object) -> str:
    """Render a numeric modifier with an explicit sign, passing text through."""
    if isinstance(value, bool):  # bool is an int subclass; treat it as text.
        return str(value)
    if isinstance(value, int):
        return f"+{value}" if value >= 0 else str(value)
    return str(value)


def _table_tent_panel(character_data: dict) -> list[str]:  # type: ignore[type-arg]
    """Render one upright Table Tent panel as a list of centred lines."""

    def get(key: str, default: object = "") -> object:
        return character_data.get(key, default)

    name = str(get("name", "Unknown Hero")).strip() or "Unknown Hero"
    player = str(get("player", "")).strip()
    race = str(get("race", "")).strip()
    alignment = str(get("alignment", "")).strip()

    classes: list[tuple[str, int]] = character_data.get("classes", [])  # type: ignore[assignment]
    class_str = ", ".join(f"{cls} {lvl}" for cls, lvl in classes)
    descriptor = " ".join(part for part in (race, class_str) if part)
    if alignment:
        descriptor = f"{descriptor} ({alignment})" if descriptor else f"({alignment})"

    hp = get("hp", "?")
    speed = get("speed", 30)
    init = _signed(get("initiative", "?"))
    ac = get("ac", "?")
    tac = get("touch_ac", "?")
    ffac = get("flat_footed_ac", "?")
    fort = _signed(get("fort", "?"))
    ref = _signed(get("ref", "?"))
    will = _signed(get("will", "?"))

    panel: list[str] = [
        name.upper(),
        f"Player: {player}" if player else "",
        descriptor,
        "",
        f"AC {ac}   Touch {tac}   Flat-Footed {ffac}",
        f"HP {hp}   Init {init}   Speed {speed} ft.",
        f"Fort {fort}   Ref {ref}   Will {will}",
    ]
    # Keep the fixed row structure (including intentional blank rows) so the
    # printed layout mirrors the legacy Excel Table Tent panel.
    return [line.center(TABLE_TENT_WIDTH).rstrip() for line in panel]


def export_table_tent_text(character_data: dict) -> str:  # type: ignore[type-arg]
    """Format a printable Table Tent (folded name-card) from *character_data*.

    The Table Tent is the folded card a player stands on the table so the name
    and key combat numbers are visible from across the table.  It is printed as
    two panels separated by a fold line; the upper panel is inverted (its line
    order reversed) so that, once the page is folded along the centre line, both
    faces read upright to people seated on either side.

    *character_data* accepts the same payload as
    :func:`export_character_sheet_text` (see :func:`table_tent_data`); only the
    identity and combat fields are used.

    Returns:
        Multi-line plain-text Table Tent string.
    """
    # A dashed fold guide ("- - - …") spanning the panel width.
    fold = "- " * (TABLE_TENT_WIDTH // 2)
    fold_line = fold[:TABLE_TENT_WIDTH].rstrip()

    panel = _table_tent_panel(character_data)
    # Top face is printed upside-down (reversed) so it reads upright once the
    # card is folded; the bottom face is printed normally.
    top_face = list(reversed(panel))

    lines: list[str] = []
    lines.append("TABLE TENT".center(TABLE_TENT_WIDTH).rstrip())
    lines.append(
        "(fold along the centre line; both faces read upright)".center(
            TABLE_TENT_WIDTH
        ).rstrip()
    )
    lines.append("")
    lines.extend(top_face)
    lines.append(fold_line)
    lines.extend(panel)
    return "\n".join(lines)
