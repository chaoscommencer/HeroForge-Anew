"""Widget tests proving UI controls populate from a seeded SQLite database.

These exercise the DB-backed data-access path end to end: a small game database
is seeded, a :class:`CharacterModel` is pointed at it, and each tab/dialog is
asserted to surface that data instead of hardcoded or empty content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
    """Create a small seeded game database for widget tests."""
    db_path = tmp_path / "game.db"
    conn = initialize_database(db_path)
    try:
        conn.executemany(
            "INSERT INTO sources (abbreviation, full_name) VALUES (?, ?)",
            [("PHB", "Player's Handbook"), ("CAr", "Complete Arcane")],
        )
        conn.executemany(
            "INSERT INTO feats (name, type, description, source) VALUES (?, ?, ?, ?)",
            [
                ("Power Attack", "General", "Trade accuracy for damage.", "PHB"),
                ("Cleave", "General", "Extra attack on a drop.", "PHB"),
            ],
        )
        conn.executemany(
            "INSERT INTO races (name, source) VALUES (?, ?)",
            [("Human", "PHB"), ("Elf", "PHB")],
        )
        conn.executemany(
            "INSERT INTO templates (name, source) VALUES (?, ?)",
            [("Celestial", "PHB"), ("Fiendish", "PHB")],
        )
        conn.executemany(
            "INSERT INTO spells_per_day (class_name, caster_level, spell_level, slots) "
            "VALUES (?, ?, ?, ?)",
            [("Wizard", 1, 0, 3), ("Wizard", 1, 1, 2), ("Cleric", 1, 0, 4)],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def model(qapp: object, seeded_db: Path) -> object:
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(db_path=str(seeded_db))


@pytest.fixture()
def empty_model(qapp: object) -> object:
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(db_path=None)


class TestFeatsTab:
    def test_available_feats_populated(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        names = {tab._avail_list.item(i).text() for i in range(tab._avail_list.count())}
        assert names == {"Cleave", "Power Attack"}

    def test_selecting_feat_shows_description(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        tab._avail_list.setCurrentRow(0)
        assert tab._desc_text.toPlainText() != ""

    def test_empty_without_db(self, empty_model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=empty_model)
        assert tab._avail_list.count() == 0


class TestRaceAndTemplatesTab:
    def test_races_populated(self, model: object) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=model)
        races = {tab._race_combo.itemText(i) for i in range(tab._race_combo.count())}
        assert races == {"Elf", "Human"}

    def test_templates_loaded_and_addable(self, model: object) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=model)
        assert tab._available_templates == ["Celestial", "Fiendish"]
        tab._add_template()
        assert tab._template_list.count() == 1
        assert tab._template_list.item(0).text() == "Celestial"

    def test_empty_without_db(self, empty_model: object) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=empty_model)
        assert tab._race_combo.count() == 0
        assert tab._available_templates == []


class TestSpellsTab:
    def test_caster_classes_populated(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        classes = {
            tab._class_combo.itemText(i) for i in range(tab._class_combo.count())
        }
        assert classes == {"Cleric", "Wizard"}

    def test_selecting_class_fills_slot_totals(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        tab._class_combo.setCurrentText("Wizard")
        assert tab._slot_spins[0].value() == 3
        assert tab._slot_spins[1].value() == 2

    def test_not_hardcoded_to_phb_classes(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        classes = {
            tab._class_combo.itemText(i) for i in range(tab._class_combo.count())
        }
        # The old hardcoded list contained Sorcerer/Bard/etc; the DB here has none.
        assert "Sorcerer" not in classes
        assert "Bard" not in classes


class TestSourceSelectDialog:
    def test_sources_loaded_from_db(self, model: object) -> None:
        from heroforge.ui.dialogs.source_select import SourceSelectDialog

        dialog = SourceSelectDialog(repo=model.game_data())
        labels = {
            dialog._source_list.item(i).text()
            for i in range(dialog._source_list.count())
        }
        assert "PHB – Player's Handbook" in labels
        assert "CAr – Complete Arcane" in labels

    def test_empty_without_repo(self, qapp: object) -> None:
        from heroforge.ui.dialogs.source_select import SourceSelectDialog

        dialog = SourceSelectDialog()
        assert dialog._source_list.count() == 0


class TestMainWindowWiring:
    def test_db_path_threaded_into_model(self, qapp: object, seeded_db: Path) -> None:
        from heroforge.ui.main_window import MainWindow

        window = MainWindow(db_path=str(seeded_db))
        assert window.model.db_path == str(seeded_db)
        # The shared repository is reachable and DB-backed.
        assert window.model.game_data().available is True
