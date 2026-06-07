"""Main application window for HeroForge-Anew.

Hosts all tab pages inside a QTabWidget and provides the
File / Help menu bar.  A CharacterModel QObject is used as the
central data bus between tabs via Qt signals.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from heroforge.db.character_repo import (
    load_character_from_file,
    save_character_to_file,
)
from heroforge.logic.legacy_import import import_hfg
from heroforge.models.character import Character
from heroforge.ui.tabs.animal_companion import AnimalCompanionTab
from heroforge.ui.tabs.armor import ArmorTab
from heroforge.ui.tabs.attacks import AttacksTab
from heroforge.ui.tabs.buffs import BuffsTab
from heroforge.ui.tabs.character_sheet import CharacterSheetTab
from heroforge.ui.tabs.enhancements import EnhancementsTab
from heroforge.ui.tabs.familiar import FamiliarTab
from heroforge.ui.tabs.feats import FeatsTab
from heroforge.ui.tabs.game_log import GameLogTab
from heroforge.ui.tabs.grafts import GraftsTab
from heroforge.ui.tabs.initiative_card import InitiativeCardTab
from heroforge.ui.tabs.languages import LanguagesTab
from heroforge.ui.tabs.magic_equipment import MagicEquipmentTab
from heroforge.ui.tabs.maneuvers_and_stances import ManeuversAndStancesTab
from heroforge.ui.tabs.prestige_classes import PrestigeClassesTab
from heroforge.ui.tabs.psionics import PsionicsTab
from heroforge.ui.tabs.race_and_templates import RaceAndTemplatesTab
from heroforge.ui.tabs.skill_tricks import SkillTricksTab
from heroforge.ui.tabs.skills import SkillsTab
from heroforge.ui.tabs.soulmelds import SoulmeldsTab
from heroforge.ui.tabs.spells import SpellsTab

# Tab imports
from heroforge.ui.tabs.stats_and_character_details import StatsAndCharacterDetailsTab
from heroforge.ui.tabs.traits_and_flaws import TraitsAndFlawsTab

# ---------------------------------------------------------------------------
# CharacterModel – central data bus
# ---------------------------------------------------------------------------


class CharacterModel(QObject):
    """Holds the active character state and emits signals when it changes.

    All tabs should connect to these signals to stay in sync.
    """

    ability_score_changed = pyqtSignal(str, int)
    """Emitted when an ability score changes. Args: (ability_name, new_score)."""

    class_levels_changed = pyqtSignal()
    """Emitted when class/level selections change."""

    feat_added = pyqtSignal(str)
    """Emitted when a feat is added. Args: (feat_name,)."""

    skill_ranks_changed = pyqtSignal(str, float)
    """Emitted when skill ranks change. Args: (skill_name, new_ranks)."""

    buff_toggled = pyqtSignal(str, bool)
    """Emitted when a buff is enabled/disabled. Args: (buff_name, active)."""

    character_loaded = pyqtSignal(Character)
    """Emitted after a character file is loaded from disk.

    Args: (character,) – the freshly loaded :class:`Character`.
    """

    character_reset = pyqtSignal()
    """Emitted when a new blank character is created."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._db_path: str | None = None
        self._character = Character()

    @property
    def character(self) -> Character:
        """The active character. Always present (a blank one by default)."""
        return self._character

    @character.setter
    def character(self, value: Character) -> None:
        self._character = value

    def new_character(self) -> Character:
        """Replace the active character with a fresh blank one and announce it."""
        self._character = Character()
        self.character_reset.emit()
        return self._character

    def load_character(self, path: str) -> Character:
        """Load a character from *path* and emit :attr:`character_loaded`.

        ``.hfg`` files are imported via the one-way legacy importer; all
        other files are read as the new ``.hfc`` save format.
        """
        if path.lower().endswith(".hfg"):
            character = import_hfg(path)
        else:
            character = load_character_from_file(path)
        self._character = character
        self.character_loaded.emit(character)
        return character

    def save_character(self, path: str) -> Character:
        """Persist the active character to *path* in the ``.hfc`` format."""
        save_character_to_file(self._character, path)
        return self._character

    @property
    def db_path(self) -> str | None:
        """Path to the heroforge.db SQLite database, if set."""
        return self._db_path

    @db_path.setter
    def db_path(self, value: str | None) -> None:
        self._db_path = value


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """Primary application window containing all tab pages."""

    # Tab registry: (display_label, widget_class)
    _TAB_REGISTRY: list[tuple[str, type[QWidget]]] = [
        ("Stats & Details", StatsAndCharacterDetailsTab),
        ("Race & Templates", RaceAndTemplatesTab),
        ("Prestige Classes", PrestigeClassesTab),
        ("Skills", SkillsTab),
        ("Skill Tricks", SkillTricksTab),
        ("Languages", LanguagesTab),
        ("Grafts", GraftsTab),
        ("Traits & Flaws", TraitsAndFlawsTab),
        ("Maneuvers", ManeuversAndStancesTab),
        ("Feats", FeatsTab),
        ("Armor", ArmorTab),
        ("Attacks", AttacksTab),
        ("Enhancements", EnhancementsTab),
        ("Magic Equipment", MagicEquipmentTab),
        ("Buffs", BuffsTab),
        ("Soulmelds", SoulmeldsTab),
        ("Spells", SpellsTab),
        ("Psionics", PsionicsTab),
        ("Animal Companion", AnimalCompanionTab),
        ("Familiar", FamiliarTab),
        ("Character Sheet", CharacterSheetTab),
        ("Game Log", GameLogTab),
        ("Initiative Card", InitiativeCardTab),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HeroForge Anew – D&D 3.5 Character Builder")
        self.resize(1200, 800)

        self.model = CharacterModel(self)
        self._current_file: str | None = None

        self._build_menu()
        self._build_tabs()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        assert menubar is not None

        # File menu
        file_menu = menubar.addMenu("&File")
        assert file_menu is not None

        act_new = file_menu.addAction("&New Character")
        assert act_new is not None
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._on_new_character)

        act_open = file_menu.addAction("&Open Character…")
        assert act_open is not None
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._on_open_character)

        act_save = file_menu.addAction("&Save Character")
        assert act_save is not None
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._on_save_character)

        act_save_as = file_menu.addAction("Save Character &As…")
        assert act_save_as is not None
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._on_save_character_as)

        file_menu.addSeparator()

        act_exit = file_menu.addAction("E&xit")
        assert act_exit is not None
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        assert help_menu is not None

        act_about = help_menu.addAction("&About HeroForge Anew…")
        assert act_about is not None
        act_about.triggered.connect(self._on_about)

    def _build_tabs(self) -> None:
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self._tab_widget.setMovable(False)
        self._tab_widget.setDocumentMode(True)

        self._tabs: dict[str, QWidget] = {}
        for label, tab_class in self._TAB_REGISTRY:
            try:
                tab = tab_class(model=self.model)
            except TypeError:
                tab = tab_class()  # type: ignore[call-arg]
            self._tab_widget.addTab(tab, label)
            self._tabs[label] = tab

        self.setCentralWidget(self._tab_widget)

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready – no character loaded.", 5000)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _on_new_character(self) -> None:
        self._current_file = None
        self.model.new_character()
        self.setWindowTitle("HeroForge Anew – New Character")
        self._status_bar.showMessage("New character created.", 4000)

    def _on_open_character(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Character",
            "",
            "HeroForge Character (*.hfc);;"
            "Legacy HeroForge Save (*.hfg);;"
            "All files (*)",
        )
        if not path:
            return
        try:
            self.model.load_character(path)
        except Exception as exc:  # noqa: BLE001 – surfaced to the user
            QMessageBox.critical(
                self, "Open Character", f"Could not open character:\n{exc}"
            )
            self._status_bar.showMessage(f"Failed to load: {path}", 4000)
            return

        if path.lower().endswith(".hfg"):
            # Legacy files are read-only; migrate to the new format on save.
            self._current_file = None
            self.setWindowTitle(f"HeroForge Anew – {path} (imported)")
            self._status_bar.showMessage(f"Imported legacy save: {path}", 4000)
        else:
            self._current_file = path
            self.setWindowTitle(f"HeroForge Anew – {path}")
            self._status_bar.showMessage(f"Loaded: {path}", 4000)

    def _on_save_character(self) -> None:
        if self._current_file:
            self._save_to(self._current_file)
        else:
            self._on_save_character_as()

    def _on_save_character_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Character As",
            "",
            "HeroForge Character (*.hfc);;All files (*)",
        )
        if path:
            if not path.endswith(".hfc"):
                path += ".hfc"
            self._current_file = path
            self._save_to(path)

    def _save_to(self, path: str) -> None:
        try:
            self.model.save_character(path)
        except Exception as exc:  # noqa: BLE001 – surfaced to the user
            QMessageBox.critical(
                self, "Save Character", f"Could not save character:\n{exc}"
            )
            self._status_bar.showMessage(f"Failed to save: {path}", 4000)
            return
        self._current_file = path
        self._status_bar.showMessage(f"Saved: {path}", 4000)
        self.setWindowTitle(f"HeroForge Anew – {path}")

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About HeroForge Anew",
            "<h2>HeroForge Anew</h2>"
            "<p>D&amp;D 3.5 character builder – Python/PyQt6 edition.</p>"
            "<p>Version 8.0.0</p>",
        )
