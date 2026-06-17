"""Tests for the Custom Class dialog (Excel *Custom Class* sheet) save path.

These cover the dialog's OK/accept handler persisting a homebrew class onto
``Character.custom_content``, its round trip through the character save file,
and the Prestige Classes tab surfacing a custom prestige class as selectable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heroforge.logic.prestige import (
    custom_class_to_content,
    list_custom_classes,
    list_custom_prestige_classes,
)
from heroforge.models.character import Character
from heroforge.models.class_ import Class


def test_dialog_accept_persists_class_to_model(qapp: object) -> None:
    """Accepting the dialog writes the class onto the character model."""
    from heroforge.ui.dialogs.custom_class import CustomClassDialog
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    dialog = CustomClassDialog(model=model)
    dialog._name_edit.setText("Spellblade")
    dialog._is_prestige.setChecked(True)
    dialog._hit_die.setValue(8)
    dialog._bab_combo.setCurrentText("fast")
    dialog._sp_spin.setValue(4)
    dialog._prereq_edit.setText("+5 BAB; Spellcraft 8 ranks")

    dialog.accept()

    classes = list_custom_classes(model.character.custom_content)
    assert len(classes) == 1
    cls = classes[0]
    assert cls.name == "Spellblade"
    assert cls.is_prestige is True
    assert cls.bab_progression == "fast"
    assert cls.skill_points_per_level == 4
    assert cls.prerequisites == ["+5 BAB", "Spellcraft 8 ranks"]


def test_dialog_accept_replaces_same_named_class(qapp: object) -> None:
    """Re-saving a class with the same name updates rather than duplicates."""
    from heroforge.ui.dialogs.custom_class import CustomClassDialog
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    model.character.custom_content = [
        custom_class_to_content(Class(name="Spellblade", hit_die=6))
    ]

    dialog = CustomClassDialog(model=model)
    dialog._name_edit.setText("spellblade")  # different case – same class
    dialog._hit_die.setValue(10)
    dialog.accept()

    classes = list_custom_classes(model.character.custom_content)
    assert len(classes) == 1
    assert classes[0].name == "spellblade"
    assert classes[0].hit_die == 10


def test_dialog_accept_requires_name(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepting without a name warns the user and persists nothing."""
    from PyQt6.QtWidgets import QMessageBox

    from heroforge.ui.dialogs.custom_class import CustomClassDialog
    from heroforge.ui.main_window import CharacterModel

    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warned.append(args[2] if len(args) > 2 else ""),
    )

    model = CharacterModel()
    dialog = CustomClassDialog(model=model)
    dialog._hit_die.setValue(8)
    dialog.accept()

    assert warned  # a warning was shown
    assert model.character.custom_content == []
    assert dialog.result() != int(dialog.DialogCode.Accepted)


def test_dialog_accept_emits_custom_content_changed(qapp: object) -> None:
    """Persisting a custom class notifies listeners so tabs can refresh."""
    from PyQt6.QtTest import QSignalSpy

    from heroforge.ui.dialogs.custom_class import CustomClassDialog
    from heroforge.ui.main_window import CharacterModel

    model = CharacterModel()
    spy = QSignalSpy(model.custom_content_changed)
    dialog = CustomClassDialog(model=model)
    dialog._name_edit.setText("Spellblade")
    dialog.accept()

    assert len(spy) >= 1


def test_custom_class_survives_save_file_round_trip(tmp_path: Path) -> None:
    """A persisted custom class is loadable from a ``*.hfc`` save file."""
    from heroforge.db.character_repo import (
        load_character_from_file,
        save_character_to_file,
    )

    character = Character(name="Hero")
    character.custom_content = [
        custom_class_to_content(
            Class(
                name="Spellblade",
                is_prestige=True,
                hit_die=8,
                bab_progression="fast",
                skill_points_per_level=4,
                prerequisites=["+5 BAB"],
            )
        )
    ]
    save_path = tmp_path / "hero.hfc"
    save_character_to_file(character, save_path)

    loaded = load_character_from_file(save_path)
    classes = list_custom_prestige_classes(loaded.custom_content)
    assert len(classes) == 1
    assert classes[0].name == "Spellblade"
    assert classes[0].is_prestige is True
    assert classes[0].prerequisites == ["+5 BAB"]


def test_prestige_tab_lists_custom_prestige_class(qapp: object) -> None:
    """A saved custom prestige class appears in the Prestige tab's available list."""
    from heroforge.ui.main_window import CharacterModel
    from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

    model = CharacterModel()
    model.character.custom_content = [
        custom_class_to_content(
            Class(name="Homebrew Knight", is_prestige=True, prerequisites=[])
        )
    ]

    tab = PrestigeClassesTab(model=model)
    tab._load_available()
    names = {tab._avail_list.item(i).text() for i in range(tab._avail_list.count())}
    assert "Homebrew Knight" in names
