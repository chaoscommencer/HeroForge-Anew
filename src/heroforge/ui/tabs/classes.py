"""Base Classes tab for HeroForge-Anew (Excel sheet "Classes", tab 1b).

Provides the base-class picker: the available base classes are loaded from the
seeded game database, the user adds class levels, and the selection is written
back to the central :class:`~heroforge.ui.main_window.CharacterModel` so that
derived stats (BAB, saving throws, HP, skill points …) recalculate in real
time.  Prestige-class levels (managed by :class:`PrestigeClassesTab`) are left
untouched so the two pickers can coexist over the shared ``character.classes``
list.

Reference: PHB Chapter 3 (Classes); ``docs/conversion-plan.md`` §8.2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Maximum level selectable for a single class entry (D&D 3.5 epic-aware cap).
_MAX_CLASS_LEVEL = 40


class ClassesTab(QWidget):
    """Base-class selection and level tracking (Excel tab 1b)."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Names of the classes this tab owns (base classes from the database).
        # Anything in ``character.classes`` that is *not* in this set (e.g. a
        # prestige class) is preserved untouched when syncing.
        self._base_class_names: set[str] = set()
        self._build_ui()
        self._load_data()
        if model:
            model.character_reset.connect(self._reset)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
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

        # Available base classes (populated from the database).
        avail_box = QGroupBox("Available Base Classes")
        avail_layout = QVBoxLayout(avail_box)
        self._avail_list = QListWidget()
        self._avail_list.currentItemChanged.connect(
            lambda *_: self._show_features(self._selected_avail_name())
        )
        avail_layout.addWidget(QLabel("Base classes you can add levels in:"))
        avail_layout.addWidget(self._avail_list)
        inner_layout.addWidget(avail_box)

        # Taken base classes.
        taken_box = QGroupBox("Class Levels")
        taken_layout = QVBoxLayout(taken_box)
        self._taken_table = QTableWidget(0, 3)
        self._taken_table.setHorizontalHeaderLabels(["Class", "Levels", "Remove"])
        self._taken_table.horizontalHeader().setStretchLastSection(True)
        self._taken_table.itemSelectionChanged.connect(self._on_taken_selection)
        taken_layout.addWidget(self._taken_table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Selected Class")
        self._add_btn.clicked.connect(self._add_class)
        btn_row.addWidget(self._add_btn)
        btn_row.addStretch()
        taken_layout.addLayout(btn_row)
        inner_layout.addWidget(taken_box)

        # Class features: proficiencies and special abilities.
        features_box = QGroupBox("Class Features")
        features_layout = QHBoxLayout(features_box)

        prof_col = QVBoxLayout()
        prof_col.addWidget(QLabel("Weapon & Armor Proficiencies:"))
        self._prof_list = QListWidget()
        prof_col.addWidget(self._prof_list)
        features_layout.addLayout(prof_col)

        ability_col = QVBoxLayout()
        ability_col.addWidget(QLabel("Special Abilities:"))
        self._ability_list = QListWidget()
        ability_col.addWidget(self._ability_list)
        features_layout.addLayout(ability_col)

        inner_layout.addWidget(features_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        """Populate the available base-class list from the database."""
        self._avail_list.clear()
        if self._model is None:
            return
        repo = self._model.game_data()
        names = [info.name for info in repo.list_classes()]
        self._base_class_names = set(names)
        self._avail_list.addItems(names)

    def _selected_avail_name(self) -> str | None:
        item = self._avail_list.currentItem()
        return item.text() if item is not None else None

    # ------------------------------------------------------------------
    # Class features display
    # ------------------------------------------------------------------

    def _show_features(self, class_name: str | None) -> None:
        """Show the proficiencies and abilities granted by *class_name*."""
        self._prof_list.clear()
        self._ability_list.clear()
        if not class_name or self._model is None:
            return
        repo = self._model.game_data()
        for proficiency in repo.class_proficiencies(class_name):
            self._prof_list.addItem(proficiency)
        for ability in repo.class_abilities(class_name):
            self._ability_list.addItem(f"L{ability.level}: {ability.ability_name}")

    def _on_taken_selection(self) -> None:
        row = self._taken_table.currentRow()
        if row < 0:
            return
        name_item = self._taken_table.item(row, 0)
        if name_item is not None:
            self._show_features(name_item.text())

    # ------------------------------------------------------------------
    # Add / remove rows
    # ------------------------------------------------------------------

    def _add_class(self) -> None:
        name = self._selected_avail_name()
        if not name:
            return
        # If the class is already taken, bump its level instead of duplicating.
        for row in range(self._taken_table.rowCount()):
            name_item = self._taken_table.item(row, 0)
            level_widget = self._taken_table.cellWidget(row, 1)
            if (
                name_item is not None
                and name_item.text() == name
                and isinstance(level_widget, QSpinBox)
            ):
                level_widget.setValue(level_widget.value() + 1)
                return
        self._append_row(name, 1)
        self._sync_classes()

    def _append_row(self, name: str, level: int) -> None:
        """Add a class row to the taken table.

        The level spinbox's ``valueChanged`` handler is connected *after* the
        initial value is set so building or restoring rows here does not itself
        write to the model; only subsequent user edits trigger ``_sync_classes``.
        """
        row = self._taken_table.rowCount()
        self._taken_table.insertRow(row)
        self._taken_table.setItem(row, 0, QTableWidgetItem(name))
        spin = QSpinBox()
        spin.setRange(1, _MAX_CLASS_LEVEL)
        spin.setValue(max(1, int(level)))
        spin.valueChanged.connect(lambda _: self._sync_classes())
        self._taken_table.setCellWidget(row, 1, spin)
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(lambda _, b=rm_btn: self._remove_row(b))
        self._taken_table.setCellWidget(row, 2, rm_btn)

    def _remove_row(self, button: QPushButton) -> None:
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
        """Write base-class levels into the character and announce the change.

        Prestige-class entries already present in ``character.classes`` are
        preserved so the prestige picker's selection is never clobbered.
        Broadcasts :attr:`CharacterModel.class_levels_changed` (§8.4) so derived
        displays (BAB, saves, HP, skill points …) recalculate in real time.
        """
        if self._model is None:
            return
        base_rows = self._taken_rows()
        owned = {name for name, _ in base_rows}
        # Preserve any class entry this tab does not own (prestige/custom).
        preserved = [
            (name, level)
            for name, level in self._model.character.classes
            if name not in self._base_class_names and name not in owned
        ]
        self._model.character.classes = base_rows + preserved
        self._model.class_levels_changed.emit()

    def _reset(self) -> None:
        self._taken_table.setRowCount(0)
        self._prof_list.clear()
        self._ability_list.clear()
        self._sync_classes()

    def _sync_from_model(self) -> None:
        """Rebuild the taken-class table from the loaded character.

        Only base classes (those owned by this tab) are shown; prestige levels
        are displayed by :class:`PrestigeClassesTab`.
        """
        self._taken_table.setRowCount(0)
        if self._model is None:
            return
        for class_name, level in self._model.character.classes:
            if class_name in self._base_class_names:
                self._append_row(class_name, level)
