"""Race & Templates tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


class RaceAndTemplatesTab(QWidget):
    """Race selection, template application, and race variants."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._available_templates: list[str] = []
        self._loading = False
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.derived_stats_changed.connect(self._refresh_summary)
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        # Race selection
        race_box = QGroupBox("Race")
        race_form = QFormLayout(race_box)
        self._race_combo = QComboBox()
        self._race_combo.setEditable(True)
        self._race_combo.setPlaceholderText("Select or type race name…")
        race_form.addRow("Race:", self._race_combo)

        self._race_info = QLabel("Select a race to view details.")
        self._race_info.setWordWrap(True)
        race_form.addRow("Info:", self._race_info)
        inner_layout.addWidget(race_box)

        # Race variants
        variant_box = QGroupBox("Race Variants")
        variant_layout = QVBoxLayout(variant_box)
        self._variants_list = QListWidget()
        self._variants_list.setToolTip(
            "Optional variants for the selected race; check any that apply"
        )
        variant_layout.addWidget(self._variants_list)
        self._variants_hint = QLabel("Select a race to view available variants.")
        self._variants_hint.setWordWrap(True)
        variant_layout.addWidget(self._variants_hint)
        inner_layout.addWidget(variant_box)

        # Templates
        tmpl_box = QGroupBox("Applied Templates")
        tmpl_layout = QVBoxLayout(tmpl_box)
        self._template_list = QListWidget()
        tmpl_layout.addWidget(self._template_list)

        btn_row = QHBoxLayout()
        self._add_template_btn = QPushButton("Add Template…")
        self._remove_template_btn = QPushButton("Remove Selected")
        btn_row.addWidget(self._add_template_btn)
        btn_row.addWidget(self._remove_template_btn)
        btn_row.addStretch()
        tmpl_layout.addLayout(btn_row)
        inner_layout.addWidget(tmpl_box)

        # Adjustments summary (ability adjustments, size, LA, ECL)
        summary_box = QGroupBox("Racial & Template Adjustments")
        summary_form = QFormLayout(summary_box)
        self._size_label = QLabel("Medium")
        self._adjust_label = QLabel("None")
        self._adjust_label.setWordWrap(True)
        self._la_label = QLabel("+0")
        self._ecl_label = QLabel("0")
        summary_form.addRow("Size:", self._size_label)
        summary_form.addRow("Ability Adjustments:", self._adjust_label)
        summary_form.addRow("Level Adjustment:", self._la_label)
        summary_form.addRow("ECL (level + LA):", self._ecl_label)
        inner_layout.addWidget(summary_box)

        # Racial traits
        traits_box = QGroupBox("Racial Traits")
        traits_layout = QVBoxLayout(traits_box)
        self._traits_list = QListWidget()
        self._traits_list.setToolTip("Special abilities granted by the selected race")
        traits_layout.addWidget(self._traits_list)
        inner_layout.addWidget(traits_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._remove_template_btn.clicked.connect(self._remove_template)
        self._add_template_btn.clicked.connect(self._add_template)
        self._race_combo.currentTextChanged.connect(self._on_race_changed)
        self._variants_list.itemChanged.connect(self._on_variant_toggled)
        self._load_data()

    def _load_data(self) -> None:
        """Populate race and template controls from the seeded database."""
        if self._model is None:
            return
        self._loading = True
        try:
            repo = self._model.game_data()
            self._race_combo.clear()
            self._race_combo.addItems(repo.list_races())
            self._race_combo.setCurrentIndex(-1)
            self._available_templates = repo.list_templates()
        finally:
            self._loading = False

    def _on_race_changed(self, race_name: str) -> None:
        """Refresh racial traits/variants and record the chosen race."""
        self._refresh_traits(race_name)
        if self._loading or self._model is None:
            self._refresh_variants(race_name)
            return
        self._model.character.race = race_name
        # Selecting a different race invalidates previously-chosen race
        # variants, so drop them before repopulating and recomputing.
        self._prune_race_variants(keep_race=race_name)
        self._refresh_variants(race_name)
        # Race affects size, speed, and ability adjustments, so trigger a
        # full derived-stat refresh (also updates the Stats tab's mirror).
        self._model.derived_stats_changed.emit()

    def _refresh_traits(self, race_name: str) -> None:
        """Populate the racial-traits list for ``race_name``."""
        self._traits_list.clear()
        if not race_name or self._model is None:
            return
        repo = self._model.game_data()
        for ability in repo.list_racial_abilities(race_name):
            self._traits_list.addItem(ability.ability_name)

    def _refresh_variants(self, race_name: str) -> None:
        """Populate the race-variant checklist for ``race_name``."""
        self._loading = True
        try:
            self._variants_list.clear()
            if not race_name or self._model is None:
                self._variants_hint.setText("Select a race to view available variants.")
                return
            selected = self._selected_variant_names(race_name)
            variants = self._model.game_data().list_race_variants(race_name)
            if not variants:
                self._variants_hint.setText("No variants available for this race.")
                return
            self._variants_hint.setText("")
            for variant in variants:
                item = QListWidgetItem(variant.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                state = (
                    Qt.CheckState.Checked
                    if variant.name in selected
                    else Qt.CheckState.Unchecked
                )
                item.setCheckState(state)
                if variant.description:
                    item.setToolTip(variant.description)
                self._variants_list.addItem(item)
        finally:
            self._loading = False

    def _selected_variant_names(self, race_name: str) -> set[str]:
        """Names of variants already selected for *race_name* on the character."""
        if self._model is None:
            return set()
        target = race_name.casefold()
        names: set[str] = set()
        for entry in self._model.character.variants:
            if (
                isinstance(entry, dict)
                and (entry.get("class_name") or "").casefold() == target
            ):
                name = entry.get("variant_name")
                if name:
                    names.add(name)
        return names

    def _on_variant_toggled(self, _item: QListWidgetItem) -> None:
        """Record a race-variant selection change on the character."""
        if self._loading or self._model is None:
            return
        self._sync_variants_to_model()

    def _sync_variants_to_model(self) -> None:
        """Rewrite the active character's race variants from the checklist."""
        if self._model is None:
            return
        race_name = self._race_combo.currentText()
        char = self._model.character
        # Keep variants tied to other races/classes untouched.
        kept: list[str | dict[str, str | None]] = [
            entry
            for entry in char.variants
            if not (isinstance(entry, dict) and entry.get("class_name") == race_name)
        ]
        for i in range(self._variants_list.count()):
            item = self._variants_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                kept.append({"variant_name": item.text(), "class_name": race_name})
        char.variants = kept

    def _prune_race_variants(self, keep_race: str) -> None:
        """Drop structured race variants that belong to a different race.

        A variant is treated as a race variant when its ``class_name`` matches a
        known race name; stale entries (from a previously selected race) are
        removed when the race changes.
        """
        if self._model is None:
            return
        repo = self._model.game_data()
        race_names = {name.casefold() for name in repo.list_races()}
        char = self._model.character
        char.variants = [
            entry
            for entry in char.variants
            if not (
                isinstance(entry, dict)
                and (entry.get("class_name") or "").casefold() in race_names
                and entry.get("class_name") != keep_race
            )
        ]

    def _add_template(self) -> None:
        """Add a database-backed template that is not already applied."""
        applied: set[str] = set()
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            if item is not None:
                applied.add(item.text())
        for name in self._available_templates:
            if name not in applied:
                self._template_list.addItem(name)
                break
        self._sync_to_model()

    def _remove_template(self) -> None:
        for item in self._template_list.selectedItems():
            self._template_list.takeItem(self._template_list.row(item))
        self._sync_to_model()

    def _sync_to_model(self) -> None:
        """Write the selected race and applied templates into the character."""
        if self._loading or self._model is None:
            return
        char = self._model.character
        char.race = self._race_combo.currentText()
        char.templates = [
            self._template_list.item(i).text()
            for i in range(self._template_list.count())
            if self._template_list.item(i) is not None
        ]
        # Templates contribute ability adjustments and LA, so refresh stats.
        self._model.derived_stats_changed.emit()

    def _refresh_summary(self) -> None:
        """Update the size / ability-adjustment / LA / ECL readout."""
        if self._model is None:
            return
        stats = self._model.derived_stats()
        self._size_label.setText(stats.size or "Medium")
        base = self._model.character.ability_scores
        parts: list[str] = []
        for ability in _ABILITIES:
            effective = stats.effective_ability_scores.get(ability, 10)
            delta = effective - int(base.get(ability, 10))
            if delta:
                parts.append(f"{ability} {delta:+d}")
        self._adjust_label.setText(", ".join(parts) if parts else "None")
        self._la_label.setText(f"{stats.level_adjustment:+d}")
        self._ecl_label.setText(str(stats.effective_character_level))

    def _sync_from_model(self) -> None:
        """Restore race and templates from the active character (load/reset)."""
        if self._model is None:
            return
        self._loading = True
        try:
            char = self._model.character
            self._race_combo.setCurrentText(char.race)
            self._refresh_traits(char.race)
            self._template_list.clear()
            for name in char.templates:
                self._template_list.addItem(name)
        finally:
            self._loading = False
        self._refresh_variants(char.race)
        self._refresh_summary()
