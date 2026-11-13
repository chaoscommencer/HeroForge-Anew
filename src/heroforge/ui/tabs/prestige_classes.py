"""Prestige Classes tab for HeroForge-Anew (Excel sheet "Prestige Classes", tab 3).

Surfaces the prestige classes from the seeded game database (plus any homebrew
prestige classes saved on the character), shows which ones the character
currently qualifies for, and lets the user add prestige-class levels.  Met /
unmet prerequisite status is evaluated against the live character state via
:func:`heroforge.logic.prestige.evaluate_prestige_prerequisite` and refreshed in
real time as ability scores, BAB, skills, feats, and class levels change.

Base-class levels (managed by :class:`~heroforge.ui.tabs.classes.ClassesTab`)
are left untouched so the two pickers can coexist over the shared
``character.classes`` list.

Reference: DMG Chapter 2 (Prestige Classes); ``docs/conversion-plan.md`` §7.2.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.prestige import (
    PrereqStatus,
    evaluate_prestige_prerequisite,
    list_custom_prestige_classes,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

logger = logging.getLogger(__name__)

# Maximum level selectable for a single prestige-class entry (most prestige
# classes cap at 10 levels; allow headroom for higher-level supplements).
_MAX_PRESTIGE_LEVEL = 20

# Tooltip markers for each prerequisite's evaluation outcome.
_STATUS_MARKERS: dict[PrereqStatus, str] = {
    PrereqStatus.MET: "[X]",
    PrereqStatus.UNMET: "[ ]",
    PrereqStatus.UNVERIFIED: "[?]",
}

# Shown for prestige classes with no recorded prerequisite data.
_UNRECORDED_TEXT = "Prerequisites not recorded - verify manually."


class PrestigeClassesTab(QWidget):
    """Prestige class selection and level tracking (Excel tab 3)."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Names of the prestige classes this tab owns (database + homebrew).
        # Anything in ``character.classes`` that is *not* in this set (e.g. a
        # base class) is preserved untouched when syncing.
        self._managed_names: set[str] = set()
        # Prestige class name -> list of prerequisite strings.
        self._prereq_map: dict[str, list[str]] = {}
        self._build_ui()
        self._load_available()
        if model:
            model.character_reset.connect(self._reset)
            model.character_loaded.connect(lambda _id: self._on_character_loaded())
            model.derived_stats_changed.connect(self._apply_prereq_status)
            model.custom_content_changed.connect(self._load_available)
            self._sync_from_model()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        # Available prestige classes
        avail_box = QGroupBox("Available Prestige Classes")
        avail_layout = QVBoxLayout(avail_box)
        avail_layout.addWidget(
            QLabel(
                "Prestige classes (qualifying classes are enabled; italic "
                "classes have prerequisites that must be verified manually; "
                "hover a class to see its prerequisites):"
            )
        )
        self._avail_list = QListWidget()
        self._avail_list.currentTextChanged.connect(self._show_prerequisites)
        avail_layout.addWidget(self._avail_list)
        self._prereq_label = QLabel("")
        self._prereq_label.setObjectName("prestigePrereqLabel")
        self._prereq_label.setWordWrap(True)
        avail_layout.addWidget(self._prereq_label)
        inner_layout.addWidget(avail_box)

        # Taken prestige classes
        taken_box = QGroupBox("Taken Prestige Classes")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_table = QTableWidget(0, 3)
        self._taken_table.setHorizontalHeaderLabels(["Class", "Levels", "Remove"])
        self._taken_table.horizontalHeader().setStretchLastSection(True)
        taken_layout.addWidget(self._taken_table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Selected Class")
        self._add_btn.clicked.connect(self._add_prestige_class)
        btn_row.addWidget(self._add_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_available(self) -> None:
        """Populate the available prestige-class list from the database.

        Combines the seeded prestige classes with any homebrew prestige classes
        stored on the character, records the prerequisite mapping (database
        prerequisites plus per-custom-class prerequisites), then refreshes the
        met / unmet status of every entry.
        """
        self._avail_list.clear()
        self._managed_names = set()
        self._prereq_map = {}
        if self._model is None:
            return

        repo = self._model.game_data()
        self._prereq_map = repo.prestige_class_prerequisites()
        names: list[str] = [info.name for info in repo.list_prestige_classes()]
        db_names = set(names)

        # Homebrew prestige classes saved on the character.  Custom content
        # takes priority: a name clash with a database class (compared
        # case-insensitively) replaces the database entry and its
        # prerequisites, and is logged in case the clash was unintentional.
        by_cf = {n.casefold(): n for n in names}
        for cls in list_custom_prestige_classes(self._model.character.custom_content):
            existing = by_cf.get(cls.name.casefold())
            if existing is not None:
                if existing in db_names:
                    logger.warning(
                        "Custom prestige class %r overrides database prestige "
                        "class %r with the same name",
                        cls.name,
                        existing,
                    )
                names.remove(existing)
                self._prereq_map.pop(existing, None)
            names.append(cls.name)
            by_cf[cls.name.casefold()] = cls.name
            self._prereq_map[cls.name] = list(cls.prerequisites)

        self._managed_names = set(names)
        for name in sorted(names):
            self._avail_list.addItem(name)
        self._apply_prereq_status()

    def _character_classes(self) -> dict[str, int]:
        """Return a mapping of class name -> total levels for the character.

        Levels for repeated class entries are summed; the keys preserve the
        stored casing while :func:`check_prestige_prerequisites` matches them
        case-insensitively.
        """
        levels: dict[str, int] = {}
        if self._model is None:
            return levels
        for name, level in self._model.character.classes:
            levels[name] = levels.get(name, 0) + int(level)
        return levels

    def _apply_prereq_status(self) -> None:
        """Enable / disable available classes by prerequisite satisfaction.

        Each prerequisite is evaluated individually with
        :func:`heroforge.logic.prestige.evaluate_prestige_prerequisite` and
        listed in the item's tooltip as ``[X]`` (met), ``[ ]`` (unmet) or
        ``[?]`` (cannot be checked automatically, e.g. spellcasting ability).
        A class with any unmet prerequisite is disabled; one whose only open
        prerequisites are unverifiable stays selectable but is shown in italics
        so the user knows to verify it manually.
        """
        if self._model is None:
            return
        stats = self._model.derived_stats()
        char = self._model.character
        classes = self._character_classes()
        for i in range(self._avail_list.count()):
            item = self._avail_list.item(i)
            if item is None:
                continue
            prereqs = self._prereq_map.get(item.text(), [])

            lines: list[str] = []
            unmet = unverified = 0
            for p in prereqs:
                if not p.strip():
                    continue
                # The character model does not track castable spell levels yet,
                # so spellcasting is passed as unknown (None): CAST: tags come
                # back as UNVERIFIED rather than failing outright.
                status = evaluate_prestige_prerequisite(
                    p,
                    stats.base_attack_bonus,
                    char.ability_scores,
                    char.skills,
                    char.feats,
                    char.total_level,
                    classes,
                    character_alignment=char.alignment,
                    character_race=char.race,
                    character_spellcasting=None,
                )
                lines.append(f"{_STATUS_MARKERS[status]} {p}")
                if status is PrereqStatus.UNMET:
                    unmet += 1
                elif status is PrereqStatus.UNVERIFIED:
                    unverified += 1

            flags = item.flags()
            font = item.font()
            if item.text() not in self._prereq_map:
                # No prerequisite data is recorded for this class (most
                # supplement prestige classes): keep it selectable, but do not
                # present it as qualifying.
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(_UNRECORDED_TEXT)
                font.setItalic(True)
            elif unmet:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("Prerequisites not met:\n" + "\n".join(lines))
                font.setItalic(False)
            elif unverified:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(
                    "Some prerequisites cannot be checked automatically "
                    "- verify manually:\n" + "\n".join(lines)
                )
                font.setItalic(True)
            else:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("")
                font.setItalic(False)
            item.setFont(font)
        self._show_prerequisites(self._selected_avail_name() or "")

    def _selected_avail_name(self) -> str | None:
        item = self._avail_list.currentItem()
        return item.text() if item is not None else None

    def _show_prerequisites(self, name: str) -> None:
        """Show the prerequisites for *name* under the available list."""
        if not name:
            self._prereq_label.setText("")
            return
        prereqs = self._prereq_map.get(name, [])
        if prereqs:
            self._prereq_label.setText("Prerequisites: " + "; ".join(prereqs))
        else:
            self._prereq_label.setText(f"Prerequisites: {_UNRECORDED_TEXT}")

    # ------------------------------------------------------------------
    # Add / remove rows
    # ------------------------------------------------------------------

    def _add_prestige_class(self) -> None:
        selected = self._avail_list.selectedItems()
        if not selected:
            return
        name = selected[0].text()
        # If already taken, bump its level instead of duplicating.
        for row in range(self._taken_table.rowCount()):
            name_item = self._taken_table.item(row, 0)
            level_widget = self._taken_table.cellWidget(row, 1)
            if (
                name_item is not None
                and name_item.text().casefold() == name.casefold()
                and isinstance(level_widget, QSpinBox)
            ):
                level_widget.setValue(level_widget.value() + 1)
                return
        self._append_row(name, 1)
        self._sync_classes()

    def _append_row(self, name: str, level: int) -> None:
        """Add a class row to the taken table.

        The level spinbox's ``valueChanged`` handler is connected *after* the
        initial value is set, so building or restoring rows here does not itself
        write to the model; only subsequent user edits trigger ``_sync_classes``.
        """
        row = self._taken_table.rowCount()
        self._taken_table.insertRow(row)
        self._taken_table.setItem(row, 0, QTableWidgetItem(name))
        spin = QSpinBox()
        spin.setRange(1, _MAX_PRESTIGE_LEVEL)
        spin.setValue(max(1, int(level)))
        spin.valueChanged.connect(lambda _: self._sync_classes())
        self._taken_table.setCellWidget(row, 1, spin)
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda _, b=rm_btn: self._remove_prestige_row(b))
        self._taken_table.setCellWidget(row, 2, rm_btn)

    def _remove_prestige_row(self, button: QPushButton) -> None:
        for row in range(self._taken_table.rowCount()):
            if self._taken_table.cellWidget(row, 2) is button:
                self._taken_table.removeRow(row)
                self._sync_classes()
                return

    # ------------------------------------------------------------------
    # Model synchronisation
    # ------------------------------------------------------------------

    def _taken_rows(self) -> list[tuple[str, int]]:
        rows: list[tuple[str, int]] = []
        for row in range(self._taken_table.rowCount()):
            name_item = self._taken_table.item(row, 0)
            level_widget = self._taken_table.cellWidget(row, 1)
            if name_item is None or not isinstance(level_widget, QSpinBox):
                continue
            rows.append((name_item.text(), int(level_widget.value())))
        return rows

    def _sync_classes(self) -> None:
        """Write taken prestige-class levels into the character.

        Base-class entries already present in ``character.classes`` are
        preserved so the base-class picker's selection is never clobbered.
        Broadcasts :attr:`CharacterModel.class_levels_changed` (§8.4) so derived
        displays (BAB, saves, attacks, character sheet) recalculate in real time.
        """
        if self._model is None:
            return
        prestige_rows = self._taken_rows()
        # Names owned by this tab: the known prestige classes plus whatever is
        # currently displayed in this tab's table.
        owned = self._managed_names | {name for name, _ in prestige_rows}
        new_levels = dict(prestige_rows)
        # Merge in place so the original "order taken" of every entry is kept
        # (see ``Character.classes`` docstring): walk the existing list,
        # updating the levels of prestige classes this tab owns and dropping any
        # it no longer holds, while leaving base/other entries untouched.
        merged: list[tuple[str, int]] = []
        seen: set[str] = set()
        for name, level in self._model.character.classes:
            if name in owned:
                if name in new_levels:
                    merged.append((name, new_levels[name]))
                    seen.add(name)
                # else: a prestige class removed in this tab -- drop it.
            else:
                merged.append((name, level))
        # Append prestige classes newly added in this tab, in table order.
        merged.extend(
            (name, level) for name, level in prestige_rows if name not in seen
        )
        self._model.character.classes = merged
        self._model.class_levels_changed.emit()

    def _reset(self) -> None:
        self._taken_table.setRowCount(0)
        self._load_available()
        self._sync_classes()

    def _on_character_loaded(self) -> None:
        """Refresh available classes (homebrew may differ) then restore rows."""
        self._load_available()
        self._sync_from_model()

    def _sync_from_model(self) -> None:
        """Rebuild the taken-class table from the loaded character.

        Only prestige classes (those owned by this tab) are shown; base-class
        levels are displayed by :class:`~heroforge.ui.tabs.classes.ClassesTab`.
        """
        self._taken_table.setRowCount(0)
        if self._model is None:
            return
        for class_name, level in self._model.character.classes:
            if class_name in self._managed_names:
                self._append_row(class_name, level)
        self._apply_prereq_status()
