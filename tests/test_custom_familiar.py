"""Tests for the Custom Familiar dialog (Excel tab 9c) save path.

These cover the structured serialization helpers
(:mod:`heroforge.logic.familiar`), the dialog's OK/accept handler persisting a
homebrew familiar onto ``Character.custom_content``, its round trip through the
character save file, and the Familiar tab surfacing it as selectable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from heroforge.logic.familiar import (
    CUSTOM_FAMILIAR_CONTENT_TYPE,
    CustomFamiliar,
    custom_familiar_from_content,
    list_custom_familiars,
)
from heroforge.models.character import Character


def test_custom_familiar_round_trips_through_content() -> None:
    """A custom familiar serialises to and from a ``custom_content`` entry."""
    familiar = CustomFamiliar(
        name="Pseudodragon",
        kind="Dragon",
        special_bonus="Master gains +2 on saves vs poison.",
        intelligence=10,
        natural_armor=4,
    )
    entry = familiar.to_content()
    assert entry["content_type"] == CUSTOM_FAMILIAR_CONTENT_TYPE
    assert entry["name"] == "Pseudodragon"
    assert custom_familiar_from_content(entry) == familiar


def test_custom_familiar_from_content_ignores_other_content() -> None:
    """Non-familiar or unnamed entries decode to ``None``."""
    assert custom_familiar_from_content({"content_type": "race", "name": "X"}) is None
    assert (
        custom_familiar_from_content(
            {"content_type": CUSTOM_FAMILIAR_CONTENT_TYPE, "name": "  "}
        )
        is None
    )


def test_custom_familiar_from_content_handles_null_fields() -> None:
    """JSON ``null`` for kind/special_bonus must decode to ``""`` not ``"None"``."""
    entry = {
        "content_type": CUSTOM_FAMILIAR_CONTENT_TYPE,
        "name": "Imp",
        "definition": json.dumps(
            {"kind": None, "special_bonus": None, "intelligence": 8, "natural_armor": 2}
        ),
    }
    familiar = custom_familiar_from_content(entry)
    assert familiar is not None
    assert familiar.kind == ""
    assert familiar.special_bonus == ""
    assert familiar.intelligence == 8
    assert familiar.natural_armor == 2


def test_custom_familiar_from_content_strips_whitespace_from_string_fields() -> None:
    """Leading/trailing whitespace in JSON strings is stripped."""
    entry = {
        "content_type": CUSTOM_FAMILIAR_CONTENT_TYPE,
        "name": "Quasit",
        "definition": json.dumps({"kind": "  Outsider  ", "special_bonus": " bonus "}),
    }
    familiar = custom_familiar_from_content(entry)
    assert familiar is not None
    assert familiar.kind == "Outsider"
    assert familiar.special_bonus == "bonus"


def test_list_custom_familiars_filters_other_content() -> None:
    """Only named familiar entries are returned, in order."""
    content = [
        {"content_type": "race", "name": "Homebrew Race", "definition": None},
        CustomFamiliar(name="Imp").to_content(),
        CustomFamiliar(name="Quasit").to_content(),
    ]
    names = [f.name for f in list_custom_familiars(content)]
    assert names == ["Imp", "Quasit"]


def test_custom_familiar_survives_save_file_round_trip(tmp_path: Path) -> None:
    """A persisted custom familiar is loadable from a ``*.hfc`` save file."""
    from heroforge.db.character_repo import (
        load_character_from_file,
        save_character_to_file,
    )

    character = Character(name="Wizard")
    character.custom_content = [
        CustomFamiliar(
            name="Pseudodragon",
            kind="Dragon",
            special_bonus="Telepathy with master.",
            intelligence=10,
            natural_armor=4,
        ).to_content()
    ]
    save_path = tmp_path / "wizard.hfc"
    save_character_to_file(character, save_path)

    loaded = load_character_from_file(save_path)
    familiars = list_custom_familiars(loaded.custom_content)
    assert len(familiars) == 1
    assert familiars[0] == CustomFamiliar(
        name="Pseudodragon",
        kind="Dragon",
        special_bonus="Telepathy with master.",
        intelligence=10,
        natural_armor=4,
    )


def test_dialog_accept_persists_familiar_to_model(qapp: object) -> None:
    """Accepting the dialog writes the familiar onto the character model."""
    from heroforge.ui.dialogs.custom_familiar import CustomFamiliarDialog
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    dialog = CustomFamiliarDialog(model=model)
    dialog._name_edit.setText("Pseudodragon")
    dialog._kind_edit.setText("Dragon")
    dialog._bonus_edit.setText("Telepathy with master.")
    dialog._int_spin.setValue(10)
    dialog._nat_armor_spin.setValue(4)

    dialog.accept()

    familiars = list_custom_familiars(model.character.custom_content)
    assert familiars == [
        CustomFamiliar(
            name="Pseudodragon",
            kind="Dragon",
            special_bonus="Telepathy with master.",
            intelligence=10,
            natural_armor=4,
        )
    ]


def test_dialog_accept_replaces_same_named_familiar(qapp: object) -> None:
    """Re-saving a familiar with the same name updates rather than duplicates."""
    from heroforge.ui.dialogs.custom_familiar import CustomFamiliarDialog
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    model.character.custom_content = [
        CustomFamiliar(name="Imp", special_bonus="old").to_content()
    ]

    dialog = CustomFamiliarDialog(model=model)
    dialog._name_edit.setText("imp")  # different case – still the same familiar
    dialog._bonus_edit.setText("new")
    dialog.accept()

    familiars = list_custom_familiars(model.character.custom_content)
    assert len(familiars) == 1
    assert familiars[0].name == "imp"
    assert familiars[0].special_bonus == "new"


def test_dialog_accept_requires_name(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepting without a name warns the user and persists nothing."""
    from PyQt6.QtWidgets import QMessageBox

    from heroforge.ui.dialogs.custom_familiar import CustomFamiliarDialog
    from heroforge.ui.main_window import CharacterModel

    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warned.append(args[2] if len(args) > 2 else ""),
    )

    model = CharacterModel()
    dialog = CustomFamiliarDialog(model=model)
    dialog._bonus_edit.setText("orphan bonus")
    dialog.accept()

    assert warned  # a warning was shown
    assert model.character.custom_content == []
    assert dialog.result() != int(dialog.DialogCode.Accepted)


def test_familiar_tab_lists_and_describes_custom_familiar(qapp: object) -> None:
    """A saved custom familiar is selectable on the Familiar tab with its bonus."""
    from heroforge.ui.main_window import CharacterModel
    from heroforge.ui.tabs.familiar import FamiliarTab

    model = CharacterModel()
    model.character.custom_content = [
        CustomFamiliar(
            name="Pseudodragon", special_bonus="Telepathy with master."
        ).to_content()
    ]

    tab = FamiliarTab(model=model)
    assert "Pseudodragon" in [f.name for f in tab._custom_familiars()]

    tab._kind_edit.setText("Pseudodragon")
    tab._refresh_bonus()
    assert tab._bonus_lbl.text() == "Telepathy with master."
