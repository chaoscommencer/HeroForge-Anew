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
            "INSERT INTO classes (name, is_prestige, hit_die, bab_progression, "
            "fort_progression, ref_progression, will_progression, "
            "skill_points_per_level, spellcasting_ability, caster_type, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "Wizard",
                    0,
                    4,
                    "slow",
                    "poor",
                    "poor",
                    "good",
                    2,
                    "INT",
                    "full",
                    "PHB",
                ),
                (
                    "Cleric",
                    0,
                    8,
                    "medium",
                    "good",
                    "poor",
                    "good",
                    2,
                    "WIS",
                    "full",
                    "PHB",
                ),
                (
                    "Arcane Archer",
                    1,
                    8,
                    "fast",
                    "poor",
                    "good",
                    "poor",
                    4,
                    None,
                    None,
                    "DMG",
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO class_weapons_armor (class_name, proficiency) VALUES (?, ?)",
            [
                ("Fighter", "All simple weapons"),
                ("Fighter", "Heavy armor"),
            ],
        )
        conn.executemany(
            "INSERT INTO class_abilities (class_name, level, ability_name, "
            "description) VALUES (?, ?, ?, ?)",
            [("Fighter", 1, "Bonus Feat", "A fighter gains a bonus feat.")],
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
        conn.executemany(
            "INSERT INTO skill_synergies (from_skill, to_skill, bonus, condition) "
            "VALUES (?, ?, ?, ?)",
            [
                ("Tumble", "Balance", 2, None),
                ("Tumble", "Jump", 2, None),
                ("Knowledge (arcana)", "Spellcraft", 2, None),
            ],
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

    def test_slot_count_displayed(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        model.character.classes = [("Fighter", 4)]
        tab = FeatsTab(model=model)
        tab._update_slots_label()
        # Fighter 4: general feats at 1,3 = 2; fighter bonus at 1,2,4 = 3.
        assert "5 available" in tab._slots_label.text()
        assert "0 used" in tab._slots_label.text()

    def test_slot_count_updates_reactively(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        model.character.classes = [("Wizard", 5)]
        # Recompute via the derived-stats refresh signal the model bridges.
        model.class_levels_changed.emit()
        # Wizard 5: general feats at 1,3 = 2; wizard bonus at 1,5 = 2.
        assert "4 available" in tab._slots_label.text()

    def test_used_count_increments_when_feat_added(self, model: object) -> None:
        from heroforge.ui.tabs.feats import FeatsTab

        tab = FeatsTab(model=model)
        assert "0 used" in tab._slots_label.text()
        # Meet Power Attack's STR 13 prereq so it can be added.
        model.ability_score_changed.emit("STR", 13)
        power_attack = next(
            i
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Power Attack"
        )
        tab._avail_list.setCurrentRow(power_attack)
        tab._add_feat()
        assert "1 used" in tab._slots_label.text()
        # Removing it decrements the used count again.
        tab._taken_list.setCurrentRow(0)
        tab._remove_feat()
        assert "0 used" in tab._slots_label.text()


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

    def test_refresh_variants_preserves_outer_loading_guard(
        self, model: object
    ) -> None:
        from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab

        tab = RaceAndTemplatesTab(model=model)
        tab._loading = True
        tab._refresh_variants("Elf")
        assert tab._loading is True


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
        assert tab._slot_base_labels[0].text() == "3"
        assert tab._slot_total_labels[0].text() == "3"
        assert tab._slot_base_labels[1].text() == "2"
        assert tab._slot_total_labels[1].text() == "2"

    def test_slots_column_header_matches_total_values(self, model: object) -> None:
        from PyQt6.QtWidgets import QLabel

        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        labels = {label.text() for label in tab.findChildren(QLabel)}
        assert "<b>Total (Base + Bonus)</b>" in labels

    def test_slot_fallback_uses_progression_not_above_class_level(
        self, model: object
    ) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        db_path = model.game_data().db_path
        assert db_path is not None
        conn = initialize_database(db_path)
        try:
            conn.execute(
                "INSERT INTO classes (name, is_prestige, hit_die, bab_progression, "
                "fort_progression, ref_progression, will_progression, "
                "skill_points_per_level, spellcasting_ability, caster_type, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "Paladin",
                    0,
                    10,
                    "fast",
                    "good",
                    "poor",
                    "poor",
                    2,
                    "CHA",
                    "half",
                    "PHB",
                ),
            )
            conn.execute(
                "INSERT INTO spells_per_day (class_name, caster_level, spell_level, slots) "
                "VALUES (?, ?, ?, ?)",
                ("Paladin", 4, 1, 1),
            )
            conn.commit()
        finally:
            conn.close()

        model.character.classes = [("Paladin", 1)]
        tab = SpellsTab(model=model)
        tab._class_combo.setCurrentText("Paladin")

        assert tab._slot_base_labels[1].text() == "—"
        assert tab._slot_total_labels[1].text() == "—"

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

    def test_derived_stats_refresh_updates_bonus_slots(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        model.character.classes = [("Wizard", 1)]
        model.character.ability_scores["INT"] = 10
        tab = SpellsTab(model=model)
        tab._class_combo.setCurrentText("Wizard")

        assert tab._slot_total_labels[1].text() == "2"

        model.ability_score_changed.emit("INT", 14)

        assert tab._slot_total_labels[1].text() == "3"

    def test_unknown_spellcasting_ability_returns_no_bonus(self, model: object) -> None:
        from heroforge.ui.tabs.spells import SpellsTab

        model.character.ability_scores["INT"] = 18
        tab = SpellsTab(model=model)

        assert tab._ability_mod_for_class("Unknown Class") == 0

    def test_prepared_tab_labels_new_spell_controls(self, model: object) -> None:
        from PyQt6.QtWidgets import QLabel

        from heroforge.ui.tabs.spells import SpellsTab

        tab = SpellsTab(model=model)
        labels = {label.text() for label in tab.findChildren(QLabel)}

        assert "New Spell:" in labels
        assert "Level:" in labels

    def test_remove_spell_deletes_selected_rows_from_end(self, model: object) -> None:
        from PyQt6.QtWidgets import QAbstractItemView

        from heroforge.ui.tabs.spells import SpellsTab

        model.character.spells_prepared = [
            {"class_name": "Wizard", "spell_level": 1, "spell_name": "Magic Missile"},
            {"class_name": "Wizard", "spell_level": 2, "spell_name": "Invisibility"},
            {"class_name": "Wizard", "spell_level": 3, "spell_name": "Fireball"},
        ]
        tab = SpellsTab(model=model)
        tab._prepared_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        tab._prepared_list.item(0).setSelected(True)
        tab._prepared_list.item(2).setSelected(True)

        tab._on_remove_spell()

        assert model.character.spells_prepared == [
            {"class_name": "Wizard", "spell_level": 2, "spell_name": "Invisibility"}
        ]
        assert tab._prepared_list.count() == 1
        assert tab._prepared_list.item(0).text() == "[Wizard] Lv2: Invisibility"


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


class TestOptionsDialog:
    def test_get_options_returns_selected_values(self, qapp: object) -> None:
        from heroforge.ui.dialogs.options import OptionsDialog

        dialog = OptionsDialog(options={"point_buy_budget": "32"})
        assert dialog.point_buy_budget == 32
        assert dialog.get_options() == {"point_buy_budget": "32"}

    def test_prepopulates_from_stored_options(self, qapp: object) -> None:
        from heroforge.ui.dialogs.options import OptionsDialog

        dialog = OptionsDialog()
        dialog.set_options({"point_buy_budget": "28"})
        assert dialog.get_options()["point_buy_budget"] == "28"

    def test_invalid_stored_value_falls_back_to_default(self, qapp: object) -> None:
        from heroforge.ui.dialogs.options import OptionsDialog

        dialog = OptionsDialog(options={"point_buy_budget": "garbage"})
        assert dialog.point_buy_budget == 25

    def test_model_round_trip_stores_and_reads_options(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.dialogs.options import OptionsDialog

        dialog = OptionsDialog(options=empty_model.options())
        dialog.set_options({"point_buy_budget": "30"})

        received: list[None] = []
        empty_model.options_changed.connect(lambda: received.append(None))
        empty_model.set_options(dialog.get_options())

        assert received  # options_changed emitted
        assert empty_model.options() == {"point_buy_budget": "30"}
        assert empty_model.point_buy_budget() == 30
        # Persisted on the character so character_repo saves it.
        assert empty_model.character.options == {"point_buy_budget": "30"}

    def test_set_options_merges_into_existing_options(
        self, empty_model: object
    ) -> None:
        """set_options must not wipe unrelated keys (e.g. psionic_total_pp)."""
        # Simulate another tab writing its own key first.
        empty_model.character.options["psionic_total_pp"] = "5"

        empty_model.set_options({"point_buy_budget": "28"})

        assert empty_model.character.options["point_buy_budget"] == "28"
        # The pre-existing key must be preserved.
        assert empty_model.character.options["psionic_total_pp"] == "5"

    def test_options_returns_copy_not_live_reference(self, empty_model: object) -> None:
        """options() must return a copy; mutating it must not affect the model."""
        empty_model.set_options({"point_buy_budget": "25"})

        snapshot = empty_model.options()
        # Mutate the returned dict directly.
        snapshot["point_buy_budget"] = "99"
        snapshot["injected_key"] = "surprise"

        # Internal state must be unchanged.
        assert empty_model.options()["point_buy_budget"] == "25"
        assert "injected_key" not in empty_model.options()

    def test_set_options_no_signal_when_unchanged(self, empty_model: object) -> None:
        """set_options must not emit signals when no stored value changes."""
        empty_model.set_options({"point_buy_budget": "28"})

        received: list[None] = []
        empty_model.options_changed.connect(lambda: received.append(None))
        empty_model.derived_stats_changed.connect(lambda: received.append(None))

        # Setting the same value again must be a no-op (no signals).
        empty_model.set_options({"point_buy_budget": "28"})

        assert not received

    def test_set_options_emits_signal_when_changed(self, empty_model: object) -> None:
        """set_options must emit both signals when at least one value changes."""
        empty_model.set_options({"point_buy_budget": "25"})

        options_received: list[None] = []
        derived_received: list[None] = []
        empty_model.options_changed.connect(lambda: options_received.append(None))
        empty_model.derived_stats_changed.connect(lambda: derived_received.append(None))

        empty_model.set_options({"point_buy_budget": "32"})

        assert options_received
        assert derived_received


class TestStatsTabPointBuyApplied:
    def test_summary_reflects_configured_budget(self, empty_model: object) -> None:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        tab = StatsAndCharacterDetailsTab(model=empty_model)
        # Default budget of 25, all-10 scores cost 12.
        assert tab._point_buy_label.text() == "Point-Buy: 12 / 25"

        empty_model.set_options({"point_buy_budget": "15"})
        empty_model.ability_score_changed.emit("STR", 18)
        # Five 10s (10) plus one 18 (16) = 26 spent against a 15-point budget.
        assert tab._point_buy_label.text() == "Point-Buy: 26 / 15 — over budget!"


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

    def test_synergy_bonus_applied_at_five_ranks(self, model: object) -> None:
        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=model)
        tumble_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Tumble")
        balance_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Balance")
        jump_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Jump")

        # Below the 5-rank threshold there is no synergy yet.
        tab._rank_spinboxes[tumble_row].setValue(4.0)
        assert tab._table.item(balance_row, 6).text() == "0"

        # At 5 ranks Tumble grants +2 Balance and +2 Jump (PHB p65).
        tab._rank_spinboxes[tumble_row].setValue(5.0)
        assert tab._table.item(balance_row, 6).text() == "2"
        assert tab._table.item(jump_row, 6).text() == "2"

        # Synergy pairs stored with the workbook's lower-case Knowledge naming
        # still match the tab's title-cased rows (case-insensitive mapping).
        arcana_row = next(
            i for i, s in enumerate(_SKILLS) if s[0] == "Knowledge (Arcana)"
        )
        spellcraft_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Spellcraft")
        tab._rank_spinboxes[arcana_row].setValue(5.0)
        assert tab._table.item(spellcraft_row, 6).text() == "2"

    def test_armor_check_penalty_applied_to_relevant_skills(
        self, empty_model: object
    ) -> None:
        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        climb_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Climb")
        appraise_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Appraise")

        empty_model.character.custom_armor = [
            {"name": "Full Plate", "type": "Armor", "check_penalty": -6}
        ]
        empty_model.character.equipment = [
            {"item_name": "Full Plate", "slot": "Body Armor", "quantity": 1}
        ]
        empty_model.derived_stats_changed.emit()

        # Climb takes the armor check penalty; Appraise does not.
        assert tab._table.item(climb_row, 6).text() == "-6"
        assert tab._table.item(appraise_row, 6).text() == "0"

    def test_max_ranks_enforced_for_class_and_cross_class(
        self, empty_model: object
    ) -> None:
        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=empty_model)
        climb_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Climb")

        empty_model.character.classes = [("Fighter", 5)]
        empty_model.class_levels_changed.emit()

        # No seeded class skills → cross-class cap = (5 + 3) / 2 = 4.0.
        assert tab._rank_spinboxes[climb_row].maximum() == 4.0
        tab._rank_spinboxes[climb_row].setValue(8.0)
        assert tab._rank_spinboxes[climb_row].value() == 4.0

        # Marking the skill as a class skill raises the cap to level + 3 = 8.
        tab._table.item(climb_row, 2).setCheckState(Qt.CheckState.Checked)
        assert tab._rank_spinboxes[climb_row].maximum() == 8.0
        tab._rank_spinboxes[climb_row].setValue(8.0)
        assert tab._rank_spinboxes[climb_row].value() == 8.0

    def test_skill_point_budget_tracked_and_displayed(self, model: object) -> None:
        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        tab = SkillsTab(model=model)

        # Fighter 1 (2 base, +0 INT): first level quadrupled → 8 points available.
        model.character.classes = [("Fighter", 1)]
        model.class_levels_changed.emit()
        assert tab._points_label.text() == "8 / 8"

        # Spend a cross-class rank: 1 rank costs 2 points → 6 remaining.
        balance_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Balance")
        tab._rank_spinboxes[balance_row].setValue(1.0)
        assert tab._points_label.text() == "6 / 8"

    def test_class_skills_derived_from_character_classes(self, model: object) -> None:
        import sqlite3

        from PyQt6.QtCore import Qt

        from heroforge.ui.tabs.skills import _SKILLS, SkillsTab

        # Seed a class skill for Fighter into the shared game database.
        conn = sqlite3.connect(model.game_data().db_path)
        try:
            conn.execute(
                "INSERT INTO class_skills (class_name, skill_name) VALUES (?, ?)",
                ("Fighter", "Climb"),
            )
            conn.commit()
        finally:
            conn.close()

        tab = SkillsTab(model=model)
        climb_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Climb")
        jump_row = next(i for i, s in enumerate(_SKILLS) if s[0] == "Jump")

        model.character.classes = [("Fighter", 3)]
        model.class_levels_changed.emit()

        assert tab._table.item(climb_row, 2).checkState() == Qt.CheckState.Checked
        assert tab._table.item(jump_row, 2).checkState() == Qt.CheckState.Unchecked


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


class TestClassesTab:
    """Base-class picker (Excel tab 1b) is DB-backed and persists levels."""

    def test_available_classes_populated_from_db(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        names = {tab._avail_list.item(i).text() for i in range(tab._avail_list.count())}
        # Only base classes appear; the prestige class is excluded.
        assert names == {"Cleric", "Fighter", "Wizard"}
        assert "Arcane Archer" not in names

    def test_add_class_persists_levels(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        items = [
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Fighter"
        ]
        tab._avail_list.setCurrentItem(items[0])
        tab._add_class()
        tab._taken_table.cellWidget(0, 1).setValue(5)

        assert model.character.classes == [("Fighter", 5)]

    def test_add_class_twice_bumps_level(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        items = [
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Fighter"
        ]
        tab._avail_list.setCurrentItem(items[0])
        tab._add_class()
        tab._add_class()

        assert tab._taken_table.rowCount() == 1
        assert model.character.classes == [("Fighter", 2)]

    def test_remove_class(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        items = [
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Fighter"
        ]
        tab._avail_list.setCurrentItem(items[0])
        tab._add_class()
        button = tab._taken_table.cellWidget(0, 2)
        tab._remove_row(button)

        assert tab._taken_table.rowCount() == 0
        assert model.character.classes == []

    def test_prestige_levels_are_preserved(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        # A prestige level recorded by another tab must survive a base-class edit.
        model.character.classes = [("Arcane Archer", 3)]
        items = [
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Fighter"
        ]
        tab._avail_list.setCurrentItem(items[0])
        tab._add_class()

        assert ("Arcane Archer", 3) in model.character.classes
        assert ("Fighter", 1) in model.character.classes

    def test_sync_preserves_order_taken(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        # Order taken: base class, then a prestige level, then another base
        # class. Editing a base-class level must not reorder the list.
        model.character.classes = [
            ("Fighter", 2),
            ("Arcane Archer", 3),
            ("Wizard", 1),
        ]
        tab._sync_from_model()
        # Bump Fighter's level via its spinbox (row order follows the model).
        fighter_row = next(
            r
            for r in range(tab._taken_table.rowCount())
            if tab._taken_table.item(r, 0).text() == "Fighter"
        )
        tab._taken_table.cellWidget(fighter_row, 1).setValue(5)

        assert model.character.classes == [
            ("Fighter", 5),
            ("Arcane Archer", 3),
            ("Wizard", 1),
        ]

    def test_restore_shows_only_base_classes(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        model.character.classes = [("Fighter", 4), ("Arcane Archer", 2)]
        model.character_loaded.emit(0)

        shown = {
            tab._taken_table.item(r, 0).text()
            for r in range(tab._taken_table.rowCount())
        }
        assert shown == {"Fighter"}

    def test_features_surface_proficiencies_and_abilities(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        tab._show_features("Fighter")
        profs = {tab._prof_list.item(i).text() for i in range(tab._prof_list.count())}
        assert profs == {"All simple weapons", "Heavy armor"}
        abilities = [
            tab._ability_list.item(i).text() for i in range(tab._ability_list.count())
        ]
        assert abilities == ["L1: Bonus Feat"]

    def test_levels_feed_derived_stats(self, model: object) -> None:
        from heroforge.ui.tabs.classes import ClassesTab

        tab = ClassesTab(model=model)
        items = [
            tab._avail_list.item(i)
            for i in range(tab._avail_list.count())
            if tab._avail_list.item(i).text() == "Fighter"
        ]
        tab._avail_list.setCurrentItem(items[0])
        tab._add_class()
        tab._taken_table.cellWidget(0, 1).setValue(5)

        stats = model.derived_stats()
        assert stats.base_attack_bonus == 5
        # The same signal must refresh saving throws (Fighter has a good Fort
        # progression: +4 at level 5 with a +0 CON modifier).
        assert stats.fortitude == 4


class TestStatsTabHitPointsAndLevels:
    """Issue #58: computed HP, aggregated AC, and total level / ECL on Stats."""

    def _stats_tab(self, model: object) -> object:
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        return StatsAndCharacterDetailsTab(model=model)

    def test_hp_auto_computed_from_class_and_con(self, model: object) -> None:
        # Fighter (d10) 3 with +2 CON: 10 + 6 + 6 + (2 * 3) = 28.
        model.character.classes = [("Fighter", 3)]
        model.ability_score_changed.emit("CON", 14)
        tab = self._stats_tab(model)
        model.derived_stats_changed.emit()
        assert tab._hp_spin.value() == 28
        assert tab._hp_spin.isReadOnly()

    def test_total_level_and_ecl_displayed(self, model: object) -> None:
        model.character.classes = [("Fighter", 5)]
        tab = self._stats_tab(model)
        model.derived_stats_changed.emit()
        assert tab._derived_labels["total_level"].text() == "5"
        assert tab._derived_labels["ecl"].text() == "5"

    def test_manual_override_persists_to_model(self, model: object) -> None:
        model.character.classes = [("Fighter", 2)]
        tab = self._stats_tab(model)
        model.derived_stats_changed.emit()
        tab._hp_auto_check.setChecked(False)
        assert not tab._hp_spin.isReadOnly()
        tab._hp_spin.setValue(99)
        assert model.character.hit_points == 99
        # Re-enabling auto clears the override.
        tab._hp_auto_check.setChecked(True)
        assert model.character.hit_points is None

    def test_override_restored_on_sync(self, model: object) -> None:
        model.character.hit_points = 42
        tab = self._stats_tab(model)
        tab._sync_from_model()
        assert not tab._hp_auto_check.isChecked()
        assert tab._hp_spin.value() == 42

    def test_hp_override_changes_emit_derived_stats_changed(
        self, model: object
    ) -> None:
        from PyQt6.QtTest import QSignalSpy

        model.character.classes = [("Fighter", 2)]
        tab = self._stats_tab(model)
        spy = QSignalSpy(model.derived_stats_changed)

        tab._hp_auto_check.setChecked(False)
        assert len(spy) == 1

        tab._hp_spin.setValue(tab._hp_spin.value() + 1)
        assert len(spy) == 2

        tab._hp_auto_check.setChecked(True)
        assert len(spy) == 3
