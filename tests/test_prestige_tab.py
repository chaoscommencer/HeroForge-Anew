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
