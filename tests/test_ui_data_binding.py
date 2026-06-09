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
            "INSERT INTO feat_prerequisites (feat_name, prerequisite) VALUES (?, ?)",
            [("Power Attack", "STR 13"), ("Cleave", "Power Attack")],
        )
        conn.execute(
            "INSERT INTO classes (name, is_prestige, hit_die, bab_progression, "
            "fort_progression, ref_progression, will_progression, "
            "skill_points_per_level, source) VALUES "
            "('Fighter', 0, 10, 'fast', 'good', 'poor', 'poor', 2, 'PHB')"
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
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(str(seeded_db)))


@pytest.fixture()
def empty_model(qapp: object) -> object:
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(None))


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

    def test_reflects_database_content_not_hardcoded_list(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        classes = {
            tab._class_combo.itemText(i) for i in range(tab._class_combo.count())
        }
        # The combo must contain exactly the DB-seeded caster classes, not the
        # old hardcoded PHB list (which included Sorcerer, Bard, Druid, etc.).
        assert classes == {"Cleric", "Wizard"}
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
    def test_game_db_path_threaded_into_model(
        self, qapp: object, seeded_db: Path
    ) -> None:
        from heroforge.ui.main_window import MainWindow

        window = MainWindow(game_db_path=str(seeded_db))
        # The window injects the seeded game data ("ROM") into the model, which
        # exposes it as a read-only repository distinct from character state.
        assert window.model.game_data().db_path == seeded_db
        assert window.model.game_data().available is True


class TestDerivedStatsRealtime:
    """§8.6: changing ability scores updates derived values in real time."""

    def test_strength_updates_attacks_grapple_and_carry(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.tabs.attacks import AttacksTab
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        stats = StatsAndCharacterDetailsTab(model=empty_model)
        attacks = AttacksTab(model=empty_model)

        stats._ability_spinboxes["STR"].setValue(18)

        assert empty_model.character.ability_scores["STR"] == 18
        assert stats._derived_labels["melee"].text() == "+4"
        assert stats._derived_labels["grapple"].text() == "+4"
        assert stats._derived_labels["carry"].text() == "100 / 200 / 300 lb."
        # The Attacks tab tracks the same computed values, not static labels.
        assert attacks._melee_lbl.text() == "+4"
        assert attacks._grapple_lbl.text() == "+4"

    def test_dexterity_updates_initiative_ranged_ac_and_reflex(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.tabs.attacks import AttacksTab
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        stats = StatsAndCharacterDetailsTab(model=empty_model)
        attacks = AttacksTab(model=empty_model)

        stats._ability_spinboxes["DEX"].setValue(16)

        # Initiative is computed via logic.combat.initiative, not hardcoded +0.
        assert stats._init_label.text() == "+3"
        assert stats._derived_labels["ranged"].text() == "+3"
        assert stats._derived_labels["ac"].text() == "13"
        assert stats._derived_labels["ref"].text() == "+3"
        assert attacks._ranged_lbl.text() == "+3"

    def test_constitution_updates_fortitude(self, empty_model: object) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        stats = StatsAndCharacterDetailsTab(model=empty_model)
        stats._ability_spinboxes["CON"].setValue(14)
        assert stats._derived_labels["fort"].text() == "+2"

    def test_wisdom_updates_will(self, empty_model: object) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        stats = StatsAndCharacterDetailsTab(model=empty_model)
        stats._ability_spinboxes["WIS"].setValue(12)
        assert stats._derived_labels["will"].text() == "+1"

    def test_skill_ability_modifier_updates_in_real_time(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        climb_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Climb")

        empty_model.ability_score_changed.emit("STR", 18)

        assert tab._table.item(climb_row, 4).text() == "4"

    def test_familiar_skill_bonus_feeds_total(self, empty_model: object) -> None:
        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        listen_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Listen")
        spot_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Spot")

        # A Bat familiar grants +3 Listen plus the universal Alertness +2
        # Spot/Listen; with no ranks/ability the totals reflect just the familiar.
        empty_model.character.companions = [
            {"companion_type": "familiar", "name": "Echo", "creature": "Bat"}
        ]
        empty_model.derived_stats_changed.emit()

        assert tab._table.item(listen_row, 6).text() == "5"
        assert tab._table.item(spot_row, 6).text() == "2"

    def test_familiar_natural_link_doubles_skill_total(
        self, empty_model: object
    ) -> None:
        import json

        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        listen_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Listen")

        empty_model.character.companions = [
            {
                "companion_type": "familiar",
                "name": "Echo",
                "creature": "Bat",
                "notes": json.dumps({"natural_link": True}),
            }
        ]
        empty_model.derived_stats_changed.emit()

        # (3 + 2) Listen doubled by Natural Link = 10.
        assert tab._table.item(listen_row, 6).text() == "10"


class TestCharacterSheetTabRealData:
    def test_sheet_shows_computed_combat_not_placeholders(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.tabs.character_sheet import CharacterSheetTab

        tab = CharacterSheetTab(model=empty_model)
        empty_model.character.name = "Aragorn"
        empty_model.ability_score_changed.emit("DEX", 16)

        text = tab._text_edit.toPlainText()
        assert "Aragorn" in text
        # The COMBAT block renders real numbers instead of the "?" placeholder.
        assert "Initiative: 3" in text
        assert "AC: 13" in text
        assert "Ref: 3" in text

    def test_loaded_signal_refreshes_from_loaded_character(
        self, empty_model: object
    ) -> None:
        from heroforge.models.character import Character
        from heroforge.ui.tabs.character_sheet import CharacterSheetTab

        tab = CharacterSheetTab(model=empty_model)
        assert "Gandalf" not in tab._text_edit.toPlainText()

        # Simulate a load: swap the active character and announce it.
        empty_model.character = Character(name="Gandalf", race="Maia")
        empty_model.character_loaded.emit(0)

        text = tab._text_edit.toPlainText()
        assert "Gandalf" in text
        assert "Maia" in text

    def test_reset_signal_clears_previous_character(self, empty_model: object) -> None:
        from heroforge.ui.tabs.character_sheet import CharacterSheetTab

        tab = CharacterSheetTab(model=empty_model)
        empty_model.character.name = "Boromir"
        empty_model.character_loaded.emit(0)
        assert "Boromir" in tab._text_edit.toPlainText()

        empty_model.new_character()

        assert "Boromir" not in tab._text_edit.toPlainText()


class TestTableTentTabRealData:
    def test_tent_shows_name_on_both_faces(self, empty_model: object) -> None:
        from heroforge.ui.tabs.table_tent import TableTentTab

        tab = TableTentTab(model=empty_model)
        empty_model.character.name = "Aragorn"
        empty_model.ability_score_changed.emit("DEX", 16)

        text = tab._text_edit.toPlainText()
        # Name is repeated once per folded face.
        assert text.count("ARAGORN") == 2
        # Derived combat values render real numbers, not the "?" placeholder.
        assert "Init +3" in text

    def test_loaded_signal_refreshes_from_loaded_character(
        self, empty_model: object
    ) -> None:
        from heroforge.models.character import Character
        from heroforge.ui.tabs.table_tent import TableTentTab

        tab = TableTentTab(model=empty_model)
        assert "GANDALF" not in tab._text_edit.toPlainText()

        empty_model.character = Character(name="Gandalf", race="Maia")
        empty_model.character_loaded.emit(0)

        assert "GANDALF" in tab._text_edit.toPlainText()

    def test_uses_fixed_width_font_for_alignment(self, empty_model: object) -> None:
        from PyQt6.QtGui import QFont

        from heroforge.ui.tabs.table_tent import TableTentTab

        tab = TableTentTab(model=empty_model)

        assert tab._text_edit.font().styleHint() == QFont.StyleHint.Monospace


class TestFeatsTabPrerequisites:
    def test_unmet_prereq_disables_feat(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        items = {
            tab._avail_list.item(i).text(): tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
        }
        # Power Attack requires STR 13; the default STR 10 leaves it disabled.
        assert not (items["Power Attack"].flags() & Qt.ItemFlag.ItemIsEnabled)

    def test_meeting_prereq_enables_feat_in_real_time(self, model: object) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        model.ability_score_changed.emit("STR", 13)

        power_attack = next(
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Power Attack"
        )
        assert power_attack.flags() & Qt.ItemFlag.ItemIsEnabled


class TestGameDataProgressions:
    def test_class_progressions_loaded(self, model: object) -> None:
        progressions = model.game_data().class_progressions()
        assert "Fighter" in progressions
        assert progressions["Fighter"].bab == "fast"
        assert progressions["Fighter"].fort == "good"

    def test_feat_prerequisites_loaded(self, model: object) -> None:
        prereqs = model.game_data().feat_prerequisites()
        assert prereqs["Power Attack"] == ["STR 13"]
        assert prereqs["Cleave"] == ["Power Attack"]

    def test_derived_stats_uses_class_progressions(self, model: object) -> None:
        model.character.classes = [("Fighter", 5)]
        model.ability_score_changed.emit("CON", 14)
        stats = model.derived_stats()
        assert stats.base_attack_bonus == 5
        assert stats.fortitude == 6


class TestCrossTabSignalPropagation:
    """§8.4/§8.6: the four domain signals are emitted and propagate cross-tab."""

    def test_skill_ranks_changed_emitted_and_recorded(
        self, empty_model: object
    ) -> None:
        from PyQt6.QtTest import QSignalSpy

        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        climb_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Climb")
        spy = QSignalSpy(empty_model.skill_ranks_changed)
        skill_spy = QSignalSpy(empty_model.skill_stats_changed)

        tab._rank_spinboxes[climb_row].setValue(4.0)

        assert len(spy) == 1
        assert list(spy[0]) == ["Climb", 4.0]
        # skill_stats_changed carries the list of affected skill names.
        assert len(skill_spy) == 1
        assert skill_spy[0][0] == ["Climb"]
        # The model records the rank authoritatively for dependent tabs.
        assert empty_model.character.skills["Climb"] == 4.0

        # Setting the same value again must not emit a second time.
        tab._rank_spinboxes[climb_row].setValue(4.0)
        assert len(skill_spy) == 1

        # Setting to 0 treats the skill as "unset" and removes the key.
        tab._rank_spinboxes[climb_row].setValue(0.0)
        assert len(skill_spy) == 2
        assert "Climb" not in empty_model.character.skills

        # Setting to 0 when already absent must not emit again.
        tab._rank_spinboxes[climb_row].setValue(0.0)
        assert len(skill_spy) == 2

    def test_feat_added_emitted_and_enables_dependent_feat(self, model: object) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QSignalSpy

        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        # Meet Power Attack's STR 13 prereq so it can be added.
        model.ability_score_changed.emit("STR", 13)
        spy = QSignalSpy(model.feat_added)

        power_attack = next(
            i
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Power Attack"
        )
        tab._avail_list.setCurrentRow(power_attack)
        tab._add_feat()

        assert len(spy) == 1
        assert list(spy[0]) == ["Power Attack"]
        assert "Power Attack" in model.character.feats
        # Cleave requires Power Attack; it becomes enabled in real time.
        cleave = next(
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Cleave"
        )
        assert cleave.flags() & Qt.ItemFlag.ItemIsEnabled

        # Removing a feat must trigger derived_stats_changed so other tabs refresh.
        derived_spy = QSignalSpy(model.derived_stats_changed)
        power_attack_taken = next(
            i
            for i in range(tab._taken_list.count())
            if tab._taken_list.item(i).text() == "Power Attack"
        )
        tab._taken_list.setCurrentRow(power_attack_taken)
        tab._remove_feat()

        assert len(derived_spy) == 1
        assert "Power Attack" not in model.character.feats

    def test_buff_toggled_emitted_on_add_and_remove(self, empty_model: object) -> None:
        import uuid

        from PyQt6.QtTest import QSignalSpy

        from heroforge.ui.tabs.buffs import BuffsTab

        tab = BuffsTab(model=empty_model)
        spy = QSignalSpy(empty_model.buff_toggled)

        tab.add_buff("Bless")
        first_id: str = spy[-1][0]
        # ID must be a valid UUID string.
        uuid.UUID(first_id)
        assert list(spy[-1])[1:] == ["Bless", True]
        assert any(b["name"] == "Bless" for b in empty_model.character.buffs)

        # Adding the same buff name again is allowed: a buff can come from
        # multiple sources (backward-compatible with the original Excel).
        tab.add_buff("Bless")
        second_id: str = spy[-1][0]
        uuid.UUID(second_id)
        assert second_id != first_id
        assert list(spy[-1])[1:] == ["Bless", True]
        assert sum(1 for b in empty_model.character.buffs if b["name"] == "Bless") == 2

        # Removing the first UI item removes the instance with the first UUID,
        # leaving the second instance (second_id) untouched — the ID-based
        # lookup ensures the correct duplicate is removed even when names match.
        tab._buff_list.setCurrentRow(0)
        tab._remove_buff()
        assert list(spy[-1]) == [first_id, "Bless", False]
        remaining = [b for b in empty_model.character.buffs if b["name"] == "Bless"]
        assert len(remaining) == 1
        assert remaining[0]["id"] == second_id

        # Removing the last instance clears it entirely.
        tab._buff_list.setCurrentRow(0)
        tab._remove_buff()
        assert list(spy[-1]) == [second_id, "Bless", False]
        assert not any(b["name"] == "Bless" for b in empty_model.character.buffs)

    def test_class_levels_changed_updates_attacks_bab(self, model: object) -> None:
        from PyQt6.QtTest import QSignalSpy

        from heroforge.ui.tabs.attacks import AttacksTab
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        prestige = PrestigeClassesTab(model=model)
        attacks = AttacksTab(model=model)

        spy = QSignalSpy(model.class_levels_changed)
        prestige._avail_list.addItem("Fighter")
        prestige._avail_list.setCurrentRow(0)
        prestige._add_prestige_class()
        # Fighter has fast BAB progression; 1 level -> +1.
        prestige._taken_table.cellWidget(0, 1).setValue(5)

        assert len(spy) >= 1
        assert model.character.classes == [("Fighter", 5)]
        # Fighter 5 (fast BAB) -> +5, surfaced on the Attacks tab via the model.
        assert attacks._bab_lbl.text() == "+5"

    def test_buffs_tab_syncs_from_model_on_character_loaded(
        self, empty_model: object
    ) -> None:
        import uuid

        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.buffs import BuffsTab

        tab = BuffsTab(model=empty_model)

        # Pre-populate the character with two buffs (as if loaded from disk).
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        empty_model.character.buffs = [
            {"id": id1, "name": "Bless"},
            {"id": id2, "name": "Haste"},
        ]
        empty_model.character_loaded.emit(0)

        # The tab must reflect both buffs with correct names and stored IDs.
        assert tab._buff_list.count() == 2
        assert tab._buff_list.item(0).text() == "Bless"
        assert tab._buff_list.item(0).data(Qt.ItemDataRole.UserRole) == id1
        assert tab._buff_list.item(1).text() == "Haste"
        assert tab._buff_list.item(1).data(Qt.ItemDataRole.UserRole) == id2

        # A subsequent character_reset must clear the list.
        empty_model.new_character()
        assert tab._buff_list.count() == 0


class TestDialogMenuWiring:
    """§8.3: every configuration / custom dialog is reachable from the UI."""

    @staticmethod
    def _find_action(window: object, path: tuple[str, ...]) -> object:
        """Return the QAction reached by walking *path* of menu/action texts."""
        actions = window.menuBar().actions()
        target = None
        for text in path:
            target = next(a for a in actions if a.text() == text)
            menu = target.menu()
            actions = menu.actions() if menu is not None else []
        return target

    def test_tools_menu_exposes_each_dialog(self, qapp: object) -> None:
        from heroforge.ui.main_window import MainWindow

        window = MainWindow()
        tools = next(
            a.menu() for a in window.menuBar().actions() if a.text() == "&Tools"
        )
        assert tools is not None
        labels = {a.text() for a in tools.actions()}
        assert {"&Options…", "Select &Sources…", "Template &Info…"} <= labels

        custom = next(a.menu() for a in tools.actions() if a.text() == "Create &Custom")
        assert custom is not None
        custom_labels = {a.text() for a in custom.actions()}
        assert custom_labels == {
            "Custom &Race…",
            "Custom &Template…",
            "Custom &Class…",
            "Custom &Familiar…",
        }

    @pytest.mark.parametrize(
        ("path", "dialog_name"),
        [
            (("&Tools", "&Options…"), "OptionsDialog"),
            (("&Tools", "Select &Sources…"), "SourceSelectDialog"),
            (("&Tools", "Template &Info…"), "TemplateInfoDialog"),
            (("&Tools", "Create &Custom", "Custom &Race…"), "CustomRaceDialog"),
            (
                ("&Tools", "Create &Custom", "Custom &Template…"),
                "CustomTemplateDialog",
            ),
            (("&Tools", "Create &Custom", "Custom &Class…"), "CustomClassDialog"),
            (
                ("&Tools", "Create &Custom", "Custom &Familiar…"),
                "CustomFamiliarDialog",
            ),
        ],
    )
    def test_triggering_action_opens_expected_dialog(
        self,
        qapp: object,
        monkeypatch: pytest.MonkeyPatch,
        path: tuple[str, ...],
        dialog_name: str,
    ) -> None:
        from heroforge.ui.main_window import MainWindow

        # Capture (instead of modally exec'ing) the dialog so the test never
        # blocks while still exercising the real construction/parenting path.
        opened: list[object] = []
        monkeypatch.setattr(
            MainWindow,
            "_open_dialog",
            lambda self, dialog: (opened.append(dialog), dialog)[1],
        )

        window = MainWindow()
        action = self._find_action(window, path)
        action.trigger()

        assert len(opened) == 1
        dialog = opened[0]
        assert type(dialog).__name__ == dialog_name
        # Dialogs must be parented to the main window (§8.3 requirement).
        assert dialog.parent() is window

    def test_file_and_help_actions_still_present(self, qapp: object) -> None:
        from heroforge.ui.main_window import MainWindow

        window = MainWindow()
        menu_titles = [a.text() for a in window.menuBar().actions()]
        assert "&File" in menu_titles
        assert "&Help" in menu_titles

        file_menu = next(
            a.menu() for a in window.menuBar().actions() if a.text() == "&File"
        )
        file_labels = {a.text() for a in file_menu.actions()}
        assert "&New Character" in file_labels
        assert "E&xit" in file_labels
