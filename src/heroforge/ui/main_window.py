"""Main application window for HeroForge-Anew.

Hosts all tab pages inside a QTabWidget and provides the
File / Help menu bar.  A CharacterModel QObject is used as the
central data bus between tabs via Qt signals.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
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
from heroforge.db.data_access import GameDataRepository
from heroforge.env_paths import dir_from_env
from heroforge.logic.derived_stats import DerivedStats, compute_derived_stats
from heroforge.logic.familiar import (
    STANDARD_FAMILIAR_BONUSES,
    familiar_natural_link,
    selected_familiar_kind,
)
from heroforge.logic.familiar import save_bonuses as familiar_save_bonuses
from heroforge.logic.legacy_import import import_hfg
from heroforge.models.character import Character
from heroforge.models.options import point_buy_budget as _options_point_buy_budget
from heroforge.ui.dialogs.custom_class import CustomClassDialog
from heroforge.ui.dialogs.custom_familiar import CustomFamiliarDialog
from heroforge.ui.dialogs.custom_race import CustomRaceDialog
from heroforge.ui.dialogs.custom_template import CustomTemplateDialog
from heroforge.ui.dialogs.options import OptionsDialog
from heroforge.ui.dialogs.source_select import SourceSelectDialog
from heroforge.ui.dialogs.template_info import TemplateInfoDialog
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
from heroforge.ui.tabs.lg_game_log import LGGameLogTab
from heroforge.ui.tabs.lg_item_access import LGItemAccessTab
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
from heroforge.ui.tabs.table_tent import TableTentTab
from heroforge.ui.tabs.traits_and_flaws import TraitsAndFlawsTab

logger = logging.getLogger(__name__)


def _default_save_dir() -> str:
    """Return the directory the Open/Save dialogs should default to.

    Mirrors :func:`heroforge.app._data_home`: when ``HEROFORGE_DATA_DIR`` is set
    (as it is in the containerised QA stack, pointing at the writable
    ``/app/userdata`` volume) character files default there, so saves land on a
    persistent, writable mount rather than the read-only container filesystem.
    An empty string lets Qt fall back to the platform default when unset or when
    the override is malformed / not creatable.
    """
    data_home = dir_from_env("HEROFORGE_DATA_DIR", None)
    if data_home is None:
        return ""
    try:
        data_home.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.warning(
            "Could not create the data directory %s from HEROFORGE_DATA_DIR; "
            "falling back to the platform default save location.",
            data_home,
            exc_info=True,
        )
        return ""
    return str(data_home)


# ---------------------------------------------------------------------------
# CharacterModel – central data bus
# ---------------------------------------------------------------------------


class CharacterModel(QObject):
    """Holds the active character's selections and emits change signals.

    This is the **per-character** model (the volatile, user-owned choices that
    are persisted to ``.hfc`` save files via :mod:`heroforge.db.character_repo`).
    It is distinct from the read-only, application-wide game data ("ROM"): that
    lives in a :class:`~heroforge.db.data_access.GameDataRepository`, which is
    injected here so tabs can reach it through :meth:`game_data` without this
    model owning or persisting it.

    All tabs should connect to these signals to stay in sync.
    """

    ability_score_changed = pyqtSignal(str, int)
    """Emitted when an ability score changes. Args: (ability_name, new_score)."""

    class_levels_changed = pyqtSignal()
    """Emitted when class/level selections change."""

    derived_stats_changed = pyqtSignal()
    """Emitted whenever a derived combat/save value may have changed.

    Tabs that display computed values (BAB, AC, saves, initiative, attacks …)
    connect to this and re-read :meth:`derived_stats` to refresh in real time
    (``docs/conversion-plan.md`` §8.6).
    """

    feat_added = pyqtSignal(str)
    """Emitted when a feat is added. Args: (feat_name,)."""

    skill_ranks_changed = pyqtSignal(str, float)
    """Emitted when skill ranks change. Args: (skill_name, new_ranks)."""

    skill_stats_changed = pyqtSignal(list)
    """Emitted after skill ranks are persisted, carrying the affected skill names.

    Args: (changed_skills,) – ``list[str]`` of the skill names whose stored
    ranks actually changed.  Listeners that only watch specific skills can
    connect here and inspect the list before doing any work, avoiding
    unnecessary recalculations.  This signal is also bridged to
    :attr:`derived_stats_changed` so tabs connected to the broader signal
    still refresh automatically.
    """

    buff_toggled = pyqtSignal(str, str, bool)
    """Emitted when a buff is enabled/disabled. Args: (buff_id, buff_name, active)."""

    character_loaded = pyqtSignal(int)
    """Emitted after a character file is loaded from disk.

    Args: (character_id,) – loaded character id; ``0`` for unsaved imports.
    """

    character_reset = pyqtSignal()
    """Emitted when a new blank character is created."""

    options_changed = pyqtSignal()
    """Emitted when build / house-rule options change (e.g. point-buy budget).

    Tabs whose behaviour depends on an option (such as the Stats tab's
    point-buy readout) connect here to refresh when the user edits options via
    the :class:`~heroforge.ui.dialogs.options.OptionsDialog`.
    """

    def __init__(
        self,
        parent: QObject | None = None,
        game_data: GameDataRepository | None = None,
    ) -> None:
        super().__init__(parent)
        # The shared, read-only game data (ROM). Kept separate from the
        # per-character state below; this model never mutates or persists it.
        self._game_data: GameDataRepository = game_data or GameDataRepository(None)
        self._character = Character()

        # Keep the active character's state in sync with the UI and re-broadcast
        # a derived-stats refresh so every dependent tab updates in real time.
        # Connected here (before any tab) so the model's own state is current by
        # the time tab handlers for derived_stats_changed run.  Each domain
        # signal funnels through a slot that persists the change into the
        # authoritative character state, then announces derived-stat updates so
        # dependent tabs recalculate (``docs/conversion-plan.md`` §8.4/§8.6).
        self.ability_score_changed.connect(self._on_ability_score_changed)
        self.skill_ranks_changed.connect(self._on_skill_ranks_changed)
        self.feat_added.connect(self._on_feat_added)
        self.buff_toggled.connect(self._on_buff_toggled)
        self.class_levels_changed.connect(self.derived_stats_changed)
        self.character_reset.connect(self.derived_stats_changed)
        self.character_loaded.connect(lambda _id: self.derived_stats_changed.emit())
        # Bridge: skill_stats_changed → derived_stats_changed so tabs that only
        # connect to the broader signal still refresh when skill ranks change.
        self.skill_stats_changed.connect(
            lambda _skills: self.derived_stats_changed.emit()
        )

    def alloc_buff_id(self) -> str:
        """Allocate and return a unique buff instance ID (UUID).

        The UI calls this before emitting :attr:`buff_toggled` so that the
        returned ID is both stored in the :class:`~PyQt6.QtWidgets.QListWidgetItem`
        and forwarded through the signal to the model, keeping UI and model in
        sync for the lifetime of the current session.  UUIDs are globally
        unique so no counter synchronisation is needed after save/load.
        """
        return str(uuid.uuid4())

    def _on_ability_score_changed(self, ability: str, value: int) -> None:
        """Persist an ability-score change and announce derived-stat updates."""
        self._character.ability_scores[ability] = value
        self.derived_stats_changed.emit()

    def _on_skill_ranks_changed(self, skill: str, ranks: float) -> None:
        """Persist a skill-rank change and announce which skills were affected.

        Treats zero ranks as "unset": the key is removed from
        ``character.skills`` rather than stored as ``0.0``, keeping saved
        characters lean.  Only emits :attr:`skill_stats_changed` (which is
        bridged to :attr:`derived_stats_changed`) when the stored value
        actually changes, preventing redundant recalculations triggered by
        tab initialisation or programmatic spinbox resets.
        """
        if ranks == 0.0:
            if skill not in self._character.skills:
                return  # already absent – nothing to update
            del self._character.skills[skill]
        else:
            if self._character.skills.get(skill) == ranks:
                return  # unchanged – skip redundant emission
            self._character.skills[skill] = ranks
        self.skill_stats_changed.emit([skill])

    def _on_feat_added(self, feat: str) -> None:
        """Record a newly-selected feat and announce derived-stat updates.

        Kept idempotent so the authoritative feat list stays consistent even if
        the emitting tab also maintains its own copy.
        """
        if feat not in self._character.feats:
            self._character.feats.append(feat)
        self.derived_stats_changed.emit()

    def _on_buff_toggled(self, buff_id: str, buff: str, active: bool) -> None:
        """Activate/deactivate a buff and announce derived-stat updates.

        Each buff instance is tracked by a unique *buff_id* so that duplicate
        buff names (e.g. two castings of "Bless" from different sources) can
        be managed individually.  ``active=True`` appends a new
        ``{"id": buff_id, "name": buff}`` entry; ``active=False`` removes
        exactly the entry whose ``id`` matches *buff_id*, leaving any other
        instances with the same name intact.

        Only emits :attr:`derived_stats_changed` when the collection actually
        changes, preventing redundant recalculations from stale or repeated
        signals (mirrors the emit-on-change guard in
        :meth:`_on_skill_ranks_changed`).
        """
        if active:
            if not any(entry.get("id") == buff_id for entry in self._character.buffs):
                self._character.buffs.append({"id": buff_id, "name": buff})
                self.derived_stats_changed.emit()
        else:
            for i, entry in enumerate(self._character.buffs):
                if entry.get("id") == buff_id:
                    del self._character.buffs[i]
                    self.derived_stats_changed.emit()
                    break

    def derived_stats(self) -> DerivedStats:
        """Compute the active character's derived combat/save values.

        Combat and saving-throw math lives in the logic layer; this method
        simply feeds the active character and the seeded class progressions
        into :func:`heroforge.logic.derived_stats.compute_derived_stats`.

        A standard familiar's non-situational saving-throw benefit (e.g. a
        Rat's +2 Fortitude or a Weasel's +2 Reflex) is applied mechanically
        here, sourced from the same structured ``familiar_bonuses`` data that
        produces the Familiar tab's helper text.  When the familiar's Natural
        Link flag is set those bonuses double (PHB p52).
        """
        progressions = (
            self._game_data.class_progressions() if self._game_data.available else {}
        )
        kind = selected_familiar_kind(self._character.companions)
        familiar_bonus_records = (
            self._game_data.get_familiar_bonus_records() or STANDARD_FAMILIAR_BONUSES
        )
        familiar_saves = (
            familiar_save_bonuses(
                kind,
                familiar_bonus_records,
                natural_link=familiar_natural_link(self._character.companions),
            )
            if kind
            else {}
        )
        return compute_derived_stats(
            self._character, progressions, save_bonuses=familiar_saves
        )

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
        self.character_loaded.emit(character.id or 0)
        return character

    def save_character(self, path: str) -> Character:
        """Persist the active character to *path* in the ``.hfc`` format."""
        save_character_to_file(self._character, path)
        return self._character

    def game_data(self) -> GameDataRepository:
        """Return the shared, read-only game-data (ROM) repository.

        This is application-wide reference data, distinct from the per-character
        state held by this model.  Every tab and dialog reads seeded game data
        through it instead of issuing raw SQLite queries.  The repository
        degrades gracefully to empty results when no database is configured.
        """
        return self._game_data

    # ------------------------------------------------------------------
    # Build / house-rule options (Options dialog, tab 11b)
    # ------------------------------------------------------------------

    def options(self) -> dict[str, str]:
        """Return the active character's stored build options.

        These are persisted with the character via the ``character_options``
        table (see :mod:`heroforge.db.character_repo`).
        """
        return self._character.options

    def set_options(self, options: Mapping[str, object]) -> None:
        """Store *options* on the active character and announce the change.

        Values are stringified to match the ``dict[str, str]`` shape used by
        :class:`~heroforge.models.character.Character` and the persistence
        layer.  Emits :attr:`options_changed` so dependent tabs refresh, and
        :attr:`derived_stats_changed` because options (e.g. the point-buy
        budget) can influence computed readouts.
        """
        self._character.options = {
            str(name): str(value) for name, value in options.items()
        }
        self.options_changed.emit()
        self.derived_stats_changed.emit()

    def point_buy_budget(self) -> int:
        """Return the configured point-buy budget for the active character.

        Reads the persisted option, falling back to the standard 25-point
        budget when unset (DMG p169).
        """
        return _options_point_buy_budget(self._character.options)


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
        ("Table Tent", TableTentTab),
        ("Game Log", GameLogTab),
        ("LG Game Log", LGGameLogTab),
        ("LG Item Access", LGItemAccessTab),
        ("Initiative Card", InitiativeCardTab),
    ]

    #: Labels of deprecated/legacy tabs (Living Greyhawk content).  These are
    #: kept for backwards compatibility but flagged in the UI via a tooltip.
    _DEPRECATED_TABS: frozenset[str] = frozenset({"LG Game Log", "LG Item Access"})

    # Custom-content dialogs sharing a ``(parent)``-only constructor.  Declared
    # as data so new homebrew dialogs can be exposed by adding a single row.
    _CUSTOM_DIALOG_REGISTRY: list[tuple[str, type[QDialog]]] = [
        ("Custom &Race…", CustomRaceDialog),
        ("Custom &Template…", CustomTemplateDialog),
        ("Custom &Class…", CustomClassDialog),
        ("Custom &Familiar…", CustomFamiliarDialog),
    ]

    def __init__(self, game_db_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("HeroForge Anew – D&D 3.5 Character Builder")
        self.resize(800, 960)

        # Read-only game data ("ROM"): seeded reference data shared by every
        # tab.  It is injected into the per-character model rather than owned by
        # it, keeping application data and character state cleanly separated.
        game_data = GameDataRepository(game_db_path)
        self.model = CharacterModel(self, game_data=game_data)
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

        # Tools menu – configuration and custom-content dialogs (§8.3)
        tools_menu = menubar.addMenu("&Tools")
        assert tools_menu is not None

        act_options = tools_menu.addAction("&Options…")
        assert act_options is not None
        act_options.triggered.connect(self._on_options)

        act_sources = tools_menu.addAction("Select &Sources…")
        assert act_sources is not None
        act_sources.triggered.connect(self._on_select_sources)

        act_template_info = tools_menu.addAction("Template &Info…")
        assert act_template_info is not None
        act_template_info.triggered.connect(self._on_template_info)

        tools_menu.addSeparator()

        custom_menu = tools_menu.addMenu("Create &Custom")
        assert custom_menu is not None
        for label, dialog_cls in self._CUSTOM_DIALOG_REGISTRY:
            action = custom_menu.addAction(label)
            assert action is not None
            # Bind the class per-iteration so each action opens its own dialog.
            action.triggered.connect(
                lambda _checked=False, cls=dialog_cls: self._open_dialog(
                    cls(parent=self)
                )
            )

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
            index = self._tab_widget.addTab(tab, label)
            if label in self._DEPRECATED_TABS:
                self._tab_widget.setTabToolTip(
                    index,
                    "Deprecated: Living Greyhawk content is legacy and will be "
                    "removed in a future release.",
                )
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
            _default_save_dir(),
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
            _default_save_dir(),
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

    # ------------------------------------------------------------------
    # Dialog actions (§8.3)
    # ------------------------------------------------------------------

    def _open_dialog(self, dialog: QDialog) -> QDialog:
        """Parent *dialog* to this window and show it modally.

        Centralises dialog parenting so every dialog is correctly owned by the
        main window (correct stacking, modality and lifetime) and kept in the
        UI layer.
        """
        if dialog.parent() is None:
            dialog.setParent(self)
        dialog.exec()
        return dialog

    def _on_options(self) -> None:
        dialog = OptionsDialog(options=self.model.options(), parent=self)
        if self._open_dialog(dialog).result() == QDialog.DialogCode.Accepted:
            self.model.set_options(dialog.get_options())

    def _on_select_sources(self) -> None:
        self._open_dialog(SourceSelectDialog(repo=self.model.game_data(), parent=self))

    def _on_template_info(self) -> None:
        self._open_dialog(TemplateInfoDialog(parent=self))
