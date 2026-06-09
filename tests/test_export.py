"""Tests for the plain-text character-sheet export path.

These exercise the bridge from the central :class:`Character` model to the
text exporter (:func:`character_sheet_data` →
:func:`export_character_sheet_text`) directly, without Qt.  They lock in the
contract behind the Character Sheet tab so it can never regress to rendering an
empty ``{}`` payload (the original bug) while still rendering sensible defaults
for a blank/new character.
"""

from __future__ import annotations

from heroforge.logic.derived_stats import ClassProgression, compute_derived_stats
from heroforge.logic.export import (
    character_sheet_data,
    export_character_sheet_pdf,
    export_character_sheet_text,
    export_table_tent_text,
    table_tent_data,
)
from heroforge.models.character import Character


def _populated_character() -> Character:
    return Character(
        name="Aragorn",
        player="Viggo",
        campaign="War of the Ring",
        alignment="LG",
        race="Human",
        deity="Eru",
        homeland="Gondor",
        experience=15000,
        classes=[("Fighter", 5)],
        ability_scores={
            "STR": 16,
            "DEX": 14,
            "CON": 14,
            "INT": 12,
            "WIS": 13,
            "CHA": 15,
        },
        feats=["Power Attack", "Cleave"],
        skills={"Climb": 4.0, "Survival": 5.0},
        equipment=[{"item_name": "Andúril", "quantity": 1}],
        languages=["Common", "Elven"],
        notes="Heir of Isildur.",
    )


class TestCharacterSheetData:
    """The model → exporter dict bridge."""

    def test_maps_core_character_fields(self) -> None:
        character = _populated_character()

        data = character_sheet_data(character)

        assert data["name"] == "Aragorn"
        assert data["player"] == "Viggo"
        assert data["classes"] == [("Fighter", 5)]
        assert data["total_level"] == 5
        assert data["ability_scores"]["STR"] == 16
        assert data["feats"] == ["Power Attack", "Cleave"]
        assert data["skills"] == {"Climb": 4.0, "Survival": 5.0}
        assert data["equipment"] == [{"item_name": "Andúril", "quantity": 1}]
        assert data["languages"] == ["Common", "Elven"]

    def test_returns_copies_not_aliases(self) -> None:
        """Mutating the payload must not corrupt the source character."""
        character = _populated_character()

        data = character_sheet_data(character)
        data["feats"].append("Whirlwind Attack")
        data["ability_scores"]["STR"] = 99
        data["equipment"][0]["quantity"] = 2

        assert character.feats == ["Power Attack", "Cleave"]
        assert character.ability_scores["STR"] == 16
        assert character.equipment[0]["quantity"] == 1

    def test_includes_derived_combat_block_when_supplied(self) -> None:
        character = _populated_character()
        progressions = {
            "Fighter": ClassProgression("Fighter", "fast", "good", "poor", "poor")
        }
        derived = compute_derived_stats(character, progressions)

        data = character_sheet_data(character, derived)

        assert data["bab"] == derived.base_attack_bonus
        assert data["initiative"] == derived.initiative
        assert data["ac"] == derived.armor_class
        assert data["fort"] == derived.fortitude
        assert data["ref"] == derived.reflex
        assert data["will"] == derived.will

    def test_omits_combat_block_without_derived(self) -> None:
        data = character_sheet_data(_populated_character())

        for key in ("bab", "initiative", "ac", "fort", "ref", "will"):
            assert key not in data


class TestExportCharacterSheetText:
    """Rendering the payload to plain text."""

    def test_populated_character_renders_real_values(self) -> None:
        character = _populated_character()
        progressions = {
            "Fighter": ClassProgression("Fighter", "fast", "good", "poor", "poor")
        }
        derived = compute_derived_stats(character, progressions)

        text = export_character_sheet_text(character_sheet_data(character, derived))

        assert "Aragorn" in text
        assert "Fighter 5" in text
        assert "Power Attack" in text
        assert "Andúril" in text
        assert "Common, Elven" in text
        # Real computed combat numbers, not the "?" placeholders.
        assert f"BAB: {derived.base_attack_bonus}" in text
        assert f"Initiative: {derived.initiative}" in text
        # The BAB/saves line renders real computed numbers, not "?" placeholders.
        bab_line = next(
            (ln for ln in text.splitlines() if ln.strip().startswith("BAB:")), None
        )
        assert bab_line is not None
        assert "?" not in bab_line

    def test_empty_character_renders_defaults_without_crashing(self) -> None:
        text = export_character_sheet_text(character_sheet_data(Character()))

        assert "CHARACTER SHEET" in text
        assert "ABILITY SCORES" in text
        # No feats/skills/equipment/languages → "(none)" placeholders.
        assert text.count("(none)") >= 4
        # Default ability scores render at 10 with a +0 modifier.
        assert "STR: 10  (mod +0)" in text


class TestExportCharacterSheetPdf:
    """Rendering the payload to a PDF document."""

    def test_writes_valid_pdf_to_path(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        character = _populated_character()
        progressions = {
            "Fighter": ClassProgression("Fighter", "fast", "good", "poor", "poor")
        }
        derived = compute_derived_stats(character, progressions)
        out = tmp_path / "sheet.pdf"

        result = export_character_sheet_pdf(
            character_sheet_data(character, derived), out
        )

        assert result == out
        assert out.exists()
        contents = out.read_bytes()
        # A well-formed PDF starts with the %PDF signature and ends with %%EOF.
        assert contents.startswith(b"%PDF-")
        assert b"%%EOF" in contents

    def test_writes_valid_pdf_to_file_object(self) -> None:
        import io

        buffer = io.BytesIO()

        export_character_sheet_pdf(character_sheet_data(Character()), buffer)

        contents = buffer.getvalue()
        assert contents.startswith(b"%PDF-")
        assert b"%%EOF" in contents

    def test_empty_character_pdf_does_not_crash(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        out = tmp_path / "empty.pdf"

        export_character_sheet_pdf(character_sheet_data(Character()), out)

        assert out.read_bytes().startswith(b"%PDF-")


class TestExportTableTentText:
    """Rendering the folded printable name-card (Table Tent)."""

    def _derived(self, character: Character) -> object:
        progressions = {
            "Fighter": ClassProgression("Fighter", "fast", "good", "poor", "poor")
        }
        return compute_derived_stats(character, progressions)

    def test_payload_reuses_character_sheet_data(self) -> None:
        character = _populated_character()

        assert table_tent_data(character) == character_sheet_data(character)

    def test_renders_identity_and_combat_for_both_faces(self) -> None:
        character = _populated_character()
        derived = self._derived(character)

        text = export_table_tent_text(table_tent_data(character, derived))

        # The name (upper-cased) and player appear once per face → twice total.
        assert text.count("ARAGORN") == 2
        assert text.count("Player: Viggo") == 2
        assert "Human Fighter 5 (LG)" in text
        # Real computed combat numbers, not "?" placeholders.
        assert f"Init {derived.initiative:+d}" in text
        assert f"AC {derived.armor_class}" in text
        assert f"Fort {derived.fortitude:+d}" in text

    def test_top_face_is_inverted_relative_to_bottom_face(self) -> None:
        """Folding the printed card must leave both faces upright."""
        text = export_table_tent_text(table_tent_data(_populated_character()))
        lines = text.splitlines()
        fold_index = next(
            i
            for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"-", " "}
        )

        # Strip the two-line header/instruction preamble from the top face.
        top_face = [ln for ln in lines[2:fold_index] if ln.strip()]
        bottom_face = [ln for ln in lines[fold_index + 1 :] if ln.strip()]

        assert top_face == list(reversed(bottom_face))

    def test_empty_character_renders_without_crashing(self) -> None:
        text = export_table_tent_text(table_tent_data(Character()))

        assert "TABLE TENT" in text
        # A blank character still shows a name placeholder on both faces.
        assert text.count("UNKNOWN HERO") == 2
        # Unknown combat values fall back to the "?" placeholder.
        assert "AC ?" in text

    def test_empty_identity_fields_keep_fixed_panel_rows(self) -> None:
        text = export_table_tent_text(table_tent_data(Character(name="Aragorn")))
        lines = text.splitlines()
        fold_index = next(
            i
            for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"-", " "}
        )

        top_face = lines[3:fold_index]
        bottom_face = lines[fold_index + 1 :]

        assert len(top_face) == 7
        assert len(bottom_face) == 7
        # Player/descriptor/spacer rows are intentionally preserved as blanks.
        assert bottom_face[1].strip() == ""
        assert bottom_face[2].strip() == ""
        assert bottom_face[3].strip() == ""
