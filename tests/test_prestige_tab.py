"""Widget tests for the Prestige Classes tab's met / unmet prerequisite status.

A small game database is seeded with prestige classes and prerequisite rows,
a :class:`CharacterModel` is pointed at it, and the tab is driven through the
same model signals the other tabs emit (skill ranks, class levels, feats) to
prove the available list enables, disables and annotates classes correctly.

Reference: DMG Chapter 2 (Prestige Classes).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from heroforge.db.schema import initialize_database

_CLASS_COLUMNS = (
    "INSERT INTO classes (name, is_prestige, hit_die, bab_progression, "
    "fort_progression, ref_progression, will_progression, "
    "skill_points_per_level, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


@pytest.fixture()
def prestige_db(tmp_path: Path) -> Path:
    """Seed base classes, prestige classes and their prerequisite rows."""
    db_path = tmp_path / "prestige_tab.db"
    conn = initialize_database(db_path)
    try:
        conn.executemany(
            _CLASS_COLUMNS,
            [
                ("Fighter", 0, 10, "fast", "good", "poor", "poor", 2, "PHB"),
                ("Wizard", 0, 4, "slow", "poor", "poor", "good", 2, "PHB"),
                ("Arcane Archer", 1, 8, "fast", "good", "good", "poor", 4, "DMG"),
                ("Mystic Theurge", 1, 4, "slow", "poor", "poor", "good", 2, "DMG"),
                ("Loremaster", 1, 4, "slow", "poor", "poor", "good", 4, "DMG"),
            ],
        )
        conn.executemany(
            "INSERT INTO prestige_class_prerequisites (class_name, prerequisite) "
            "VALUES (?, ?)",
            [
                ("Arcane Archer", "+6 BAB"),
                ("Arcane Archer", "Knowledge (arcana) 4 ranks"),
                ("Mystic Theurge", "Knowledge (arcana) 6 ranks"),
                ("Mystic Theurge", "Knowledge (religion) 6 ranks"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture()
def model(qapp: object, prestige_db: Path) -> object:
    from heroforge.db.data_access import GameDataRepository
    from heroforge.ui.main_window import CharacterModel

    return CharacterModel(game_data=GameDataRepository(str(prestige_db)))


def _item(tab: object, name: str) -> object:
    from PyQt6.QtCore import Qt

    items = tab._avail_list.findItems(name, Qt.MatchFlag.MatchExactly)
    assert len(items) == 1, f"{name!r} should appear exactly once"
    return items[0]


def _enabled(item: object) -> bool:
    from PyQt6.QtCore import Qt

    return bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)


def _skills_tab_name(prefix: str) -> str:
    """Return the Skills tab's own spelling of the skill starting with *prefix*."""
    from heroforge.ui.tabs.skills import _SKILLS

    matches = [name for name, *_ in _SKILLS if name.startswith(prefix)]
    assert len(matches) == 1, matches
    return matches[0]


class TestPrestigePrerequisiteStatus:
    def test_skill_ranks_from_skills_tab_satisfy_seeded_knowledge_prereqs(
        self, model: object
    ) -> None:
        """Ranks entered under the Skills tab's spelling meet DMG prereq text."""
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        theurge = _item(tab, "Mystic Theurge")
        assert not _enabled(theurge)

        model.skill_ranks_changed.emit(_skills_tab_name("Knowledge (Arc"), 6.0)
        model.skill_ranks_changed.emit(_skills_tab_name("Knowledge (Rel"), 6.0)

        assert _enabled(theurge)
        assert theurge.toolTip() == ""

    def test_unmet_class_is_disabled_until_bab_and_skills_are_met(
        self, model: object
    ) -> None:
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        archer = _item(tab, "Arcane Archer")
        assert not _enabled(archer)
        assert "[ ] +6 BAB" in archer.toolTip()
        assert "[ ] Knowledge (arcana) 4 ranks" in archer.toolTip()

        model.character.classes = [("Fighter", 6)]
        model.class_levels_changed.emit()
        assert not _enabled(archer)
        assert "[X] +6 BAB" in archer.toolTip()
        assert "[ ] Knowledge (arcana) 4 ranks" in archer.toolTip()

        model.skill_ranks_changed.emit(_skills_tab_name("Knowledge (Arc"), 4.0)
        assert _enabled(archer)
        assert archer.toolTip() == ""


class TestMalformedCustomPrerequisites:
    def test_malformed_cast_tag_on_custom_class_does_not_raise(
        self, model: object
    ) -> None:
        from heroforge.logic.prestige import custom_class_to_content
        from heroforge.models.class_ import Class
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        model.character.custom_content.append(
            custom_class_to_content(
                Class(
                    name="Homebrew Mage",
                    is_prestige=True,
                    prerequisites=["CAST:Arcane:3rd"],
                )
            )
        )
        tab._load_available()  # must not raise ValueError

        item = _item(tab, "Homebrew Mage")
        assert not _enabled(item)
        assert "[ ] CAST:Arcane:3rd" in item.toolTip()


class TestUnverifiablePrerequisites:
    def test_cast_tag_is_shown_as_unverified_not_unmet(self, model: object) -> None:
        from heroforge.logic.prestige import custom_class_to_content
        from heroforge.models.class_ import Class
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        model.character.custom_content.append(
            custom_class_to_content(
                Class(
                    name="Homebrew Mage",
                    is_prestige=True,
                    prerequisites=["CAST:Arcane:3"],
                )
            )
        )
        tab._load_available()

        item = _item(tab, "Homebrew Mage")
        assert _enabled(item)
        assert "[?] CAST:Arcane:3" in item.toolTip()
        assert "verify" in item.toolTip().lower()
        assert item.font().italic()

    def test_unmet_prerequisite_still_disables_alongside_cast(
        self, model: object
    ) -> None:
        from heroforge.logic.prestige import custom_class_to_content
        from heroforge.models.class_ import Class
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        model.character.custom_content.append(
            custom_class_to_content(
                Class(
                    name="Homebrew Mage",
                    is_prestige=True,
                    prerequisites=["CAST:Arcane:3", "+6 BAB"],
                )
            )
        )
        tab._load_available()

        item = _item(tab, "Homebrew Mage")
        assert not _enabled(item)
        assert "[?] CAST:Arcane:3" in item.toolTip()
        assert "[ ] +6 BAB" in item.toolTip()


class TestUnrecordedPrerequisites:
    def test_class_without_prereq_rows_is_flagged_not_reported_as_met(
        self, model: object
    ) -> None:
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        lore = _item(tab, "Loremaster")
        # Still selectable (the data may simply be missing) ...
        assert _enabled(lore)
        # ... but clearly marked as unverified rather than qualifying.
        assert "not recorded" in lore.toolTip()
        assert "verify manually" in lore.toolTip()
        assert lore.font().italic()

        tab._avail_list.setCurrentItem(lore)
        assert "verify manually" in tab._prereq_label.text()

    def test_met_class_is_not_flagged(self, model: object) -> None:
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        model.character.classes = [("Fighter", 6)]
        model.character.skills["Knowledge (Arcana)"] = 4.0
        tab = PrestigeClassesTab(model=model)
        archer = _item(tab, "Arcane Archer")
        assert _enabled(archer)
        assert archer.toolTip() == ""
        assert not archer.font().italic()


class TestStandardPrerequisiteSkillNames:
    def test_every_seeded_skill_prereq_names_a_skills_tab_skill(self) -> None:
        """Seeded skill prereqs must use the Skills tab's exact spelling."""
        import re

        from heroforge.logic.prestige import STANDARD_PRESTIGE_PREREQUISITES
        from heroforge.ui.tabs.skills import _SKILLS

        skills_tab_names = {name for name, *_ in _SKILLS}
        for cls, prereqs in STANDARD_PRESTIGE_PREREQUISITES.items():
            for prereq in prereqs:
                m = re.match(r"^(.+?)\s+\d+\s*ranks?$", prereq)
                if m:
                    assert m.group(1) in skills_tab_names, (cls, prereq)


class TestCustomClassNameClash:
    @staticmethod
    def _add_custom(model: object, name: str, prereqs: list[str]) -> None:
        from heroforge.logic.prestige import custom_class_to_content
        from heroforge.models.class_ import Class

        model.character.custom_content.append(
            custom_class_to_content(
                Class(name=name, is_prestige=True, prerequisites=prereqs)
            )
        )

    def test_custom_class_overrides_db_class_case_insensitively(
        self, model: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        self._add_custom(model, "mystic theurge", ["+1 BAB"])
        with caplog.at_level(logging.WARNING):
            tab._load_available()

        names = [tab._avail_list.item(i).text() for i in range(tab._avail_list.count())]
        assert [n for n in names if n.casefold() == "mystic theurge"] == [
            "mystic theurge"
        ]
        assert tab._prereq_map["mystic theurge"] == ["+1 BAB"]
        assert "Mystic Theurge" not in tab._prereq_map
        assert any(
            "mystic theurge" in r.getMessage().lower() and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_custom_class_without_prereqs_fully_overrides_db_prereqs(
        self, model: object
    ) -> None:
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab

        tab = PrestigeClassesTab(model=model)
        self._add_custom(model, "Mystic Theurge", [])
        tab._load_available()

        item = _item(tab, "Mystic Theurge")
        assert tab._prereq_map["Mystic Theurge"] == []
        assert _enabled(item)
        assert item.toolTip() == ""


class TestRelevantChangeReevaluation:
    def test_alignment_edit_on_stats_tab_refreshes_status(self, model: object) -> None:
        from heroforge.logic.prestige import custom_class_to_content
        from heroforge.models.class_ import Class
        from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab
        from heroforge.ui.tabs.stats_and_character_details import (
            StatsAndCharacterDetailsTab,
        )

        model.character.custom_content.append(
            custom_class_to_content(
                Class(name="Evil Order", is_prestige=True, prerequisites=["ALIGN:Evil"])
            )
        )
        stats = StatsAndCharacterDetailsTab(model=model)
        tab = PrestigeClassesTab(model=model)
        item = _item(tab, "Evil Order")
        assert not _enabled(item)

        # Simulate the user typing an alignment into the Stats tab.
        stats._alignment_edit.setText("Neutral Evil")
        stats._alignment_edit.textEdited.emit("Neutral Evil")

        assert model.character.alignment == "Neutral Evil"
        assert _enabled(item)

    def test_irrelevant_derived_stat_changes_skip_reevaluation(
        self, model: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from heroforge.ui.tabs import prestige_classes

        tab = prestige_classes.PrestigeClassesTab(model=model)
        calls: list[str] = []
        real = prestige_classes.evaluate_prestige_prerequisite

        def counting(prereq: str, *args: object, **kwargs: object) -> object:
            calls.append(prereq)
            return real(prereq, *args, **kwargs)

        monkeypatch.setattr(
            prestige_classes, "evaluate_prestige_prerequisite", counting
        )

        # e.g. a buff toggled: derived stats change, prereq inputs do not.
        model.derived_stats_changed.emit()
        assert calls == []

        model.skill_ranks_changed.emit(_skills_tab_name("Knowledge (Arc"), 4.0)
        assert calls, "a skill-rank change must trigger re-evaluation"
