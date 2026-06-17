"""Spells tab for HeroForge-Anew.

Implements full wiring for:
- Bonus spell slots from high ability scores (PHB p. 8).
- Caster level derived from character class levels (PHB Chapter 3).
- Arcane Spell Failure from worn armor/shield (PHB p. 123).
- Deity picker and domain selection with granted-power / domain-spell display
  (PHB Chapter 11).
- Spell selection (prepared / known) with persistence via the character model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.spells import (
    arcane_spell_failure,
    caster_level,
    spells_per_day,
)
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Sentinel value for the "no domain selected" combobox entry.
_NO_DOMAIN = "(none)"
_NO_DEITY = "(none)"
# Slots of owned armor that carry an ASF value.
_ARMOR_SLOTS = {"Body Armor", "Shield"}


class SpellsTab(QWidget):
    """Spell slot tracking and prepared/known spell management."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Widgets built by _build_ui()
        self._slot_base_labels: dict[int, QLabel] = {}
        self._slot_total_labels: dict[int, QLabel] = {}
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.class_levels_changed.connect(self._refresh_slots)
            model.derived_stats_changed.connect(self._refresh_slots)
            model.derived_stats_changed.connect(self._refresh_asf)
            self._sync_from_model()
        else:
            self._load_classes()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Top summary row ──────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Spellcasting Class:"))
        self._class_combo = QComboBox()
        self._class_combo.currentTextChanged.connect(self._on_class_changed)
        top_row.addWidget(self._class_combo)

        top_row.addWidget(QLabel("  Caster Level:"))
        self._cl_label = QLabel("0")
        top_row.addWidget(self._cl_label)

        top_row.addWidget(QLabel("  Arcane Spell Failure:"))
        self._asf_label = QLabel("0%")
        top_row.addWidget(self._asf_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        sub_tabs = QTabWidget()

        # ── Tab 0: Spell Slots ───────────────────────────────────────
        sub_tabs.addTab(self._build_slots_tab(), "Spell Slots")

        # ── Tab 1: Domains / Deity ───────────────────────────────────
        sub_tabs.addTab(self._build_domains_tab(), "Domains")

        # ── Tab 2: Prepared / Known spells ──────────────────────────
        sub_tabs.addTab(self._build_prepared_tab(), "Prepared/Known")

        layout.addWidget(sub_tabs)

    def _build_slots_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        spd_box = QGroupBox("Spell Slots per Day")
        spd_box_layout = QVBoxLayout(spd_box)

        # Header row
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("<b>Level</b>"), 1)
        hdr.addWidget(QLabel("<b>Base</b>"), 1)
        hdr.addWidget(QLabel("<b>+ Ability Bonus</b>"), 1)
        spd_box_layout.addLayout(hdr)

        for lvl in range(10):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"  {lvl}:"), 1)
            base_lbl = QLabel("—")
            total_lbl = QLabel("—")
            self._slot_base_labels[lvl] = base_lbl
            self._slot_total_labels[lvl] = total_lbl
            row.addWidget(base_lbl, 1)
            row.addWidget(total_lbl, 1)
            spd_box_layout.addLayout(row)

        inner_layout.addWidget(spd_box)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_domains_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Deity picker
        deity_row = QHBoxLayout()
        deity_row.addWidget(QLabel("Deity:"))
        self._deity_combo = QComboBox()
        self._deity_combo.setEditable(True)
        self._deity_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._deity_combo.currentTextChanged.connect(self._on_deity_changed)
        deity_row.addWidget(self._deity_combo)
        deity_row.addStretch()
        layout.addLayout(deity_row)

        # Domain selectors
        domain_row1 = QHBoxLayout()
        domain_row1.addWidget(QLabel("Domain 1:"))
        self._domain1_combo = QComboBox()
        self._domain1_combo.currentTextChanged.connect(self._on_domain_changed)
        domain_row1.addWidget(self._domain1_combo)
        domain_row1.addStretch()
        layout.addLayout(domain_row1)

        domain_row2 = QHBoxLayout()
        domain_row2.addWidget(QLabel("Domain 2:"))
        self._domain2_combo = QComboBox()
        self._domain2_combo.currentTextChanged.connect(self._on_domain_changed)
        domain_row2.addWidget(self._domain2_combo)
        domain_row2.addStretch()
        layout.addLayout(domain_row2)

        # Domain spell list + granted power
        info_box = QGroupBox("Domain Info")
        info_layout = QVBoxLayout(info_box)
        self._domain_info = QTextEdit()
        self._domain_info.setReadOnly(True)
        self._domain_info.setMinimumHeight(120)
        info_layout.addWidget(self._domain_info)
        layout.addWidget(info_box)

        self._load_domains()
        return widget

    def _build_prepared_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("New Spell:"))
        add_row.addWidget(QLabel("Class:"))
        self._prep_class_combo = QComboBox()
        add_row.addWidget(self._prep_class_combo)

        add_row.addWidget(QLabel("  Level:"))
        self._prep_level_spin = QSpinBox()
        self._prep_level_spin.setRange(0, 9)
        add_row.addWidget(self._prep_level_spin)
        add_row.addStretch()
        layout.addLayout(add_row)

        layout.addWidget(QLabel("Prepared / Known Spells:"))
        self._prepared_list = QListWidget()
        layout.addWidget(self._prepared_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Spell…")
        add_btn.clicked.connect(self._on_add_spell)
        btn_row.addWidget(add_btn)

        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(self._on_remove_spell)
        btn_row.addWidget(rm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    def _load_classes(self) -> None:
        """Populate the caster-class selectors from the seeded database."""
        if self._model is None:
            return
        names = self._model.game_data().list_caster_classes()
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        self._class_combo.addItems(names)
        self._class_combo.blockSignals(False)

        self._prep_class_combo.clear()
        self._prep_class_combo.addItems(names)

    def _load_domains(self) -> None:
        """Populate deity and domain combo boxes from the seeded database."""
        if self._model is None:
            return
        deities = self._model.game_data().list_deities()
        self._deity_combo.blockSignals(True)
        self._deity_combo.clear()
        self._deity_combo.addItem(_NO_DEITY)
        self._deity_combo.addItems(deities)
        self._deity_combo.blockSignals(False)

        domain_names = [d.name for d in self._model.game_data().list_domains()]
        for combo in (self._domain1_combo, self._domain2_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_NO_DOMAIN)
            combo.addItems(domain_names)
            combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Slot / caster-level / ASF refresh
    # ------------------------------------------------------------------

    def _current_class_level(self, class_name: str) -> int:
        """Return the character's total levels in *class_name*."""
        if self._model is None or not class_name:
            return 0
        return sum(
            lvl for cls, lvl in self._model.character.classes if cls == class_name
        )

    def _ability_mod_for_class(self, class_name: str) -> int:
        """Return the spellcasting ability modifier for *class_name*.

        Returns ``0`` when the selected class has no known spellcasting-ability
        mapping, avoiding incorrect bonus-slot calculations from guesswork.
        Reference: PHB Chapter 3.
        """
        if self._model is None:
            return 0
        spellcasting_abilities = self._model.game_data().get_spellcasting_abilities()
        ability = spellcasting_abilities.get(class_name)
        if ability is None:
            return 0
        score = self._model.character.ability_scores.get(ability, 10)
        return (score - 10) // 2

    def _refresh_slots(self) -> None:
        """Recompute and display spell slots for the currently selected class."""
        class_name = self._class_combo.currentText()
        self._refresh_caster_level(class_name)
        self._update_slot_labels(class_name)

    def _refresh_caster_level(self, class_name: str) -> None:
        """Update the caster-level summary label."""
        if self._model is None or not class_name:
            self._cl_label.setText("0")
            return
        cls_levels = {
            cls: sum(lvl for c, lvl in self._model.character.classes if c == cls)
            for cls in {c for c, _ in self._model.character.classes}
        }
        caster_types = self._model.game_data().get_caster_types()
        cl = caster_level(cls_levels, caster_types)
        self._cl_label.setText(str(cl))

    def _refresh_asf(self) -> None:
        """Recompute arcane spell failure from currently equipped armor."""
        if self._model is None:
            self._asf_label.setText("0%")
            return
        asf_values: list[int] = []
        game_data = self._model.game_data()
        # Build a merged catalog of all armor (game + custom).
        merged: dict[str, int] = {}
        for item in game_data.list_armor():
            merged[item.name] = item.arcane_spell_failure
        for entry in self._model.character.custom_armor:
            name = entry.get("name", "")
            if name:
                merged[name] = int(entry.get("arcane_spell_failure", 0))
        for eq in self._model.character.equipment:
            if eq.get("slot") in _ARMOR_SLOTS:
                item_name = eq.get("item_name", "")
                if item_name in merged:
                    asf_values.append(merged[item_name])
        total_asf = arcane_spell_failure(asf_values)
        self._asf_label.setText(f"{total_asf}%")

    def _update_slot_labels(self, class_name: str) -> None:
        """Fill slot-per-day labels for *class_name* at the character's level."""
        for lvl in range(10):
            self._slot_base_labels[lvl].setText("—")
            self._slot_total_labels[lvl].setText("—")

        if not class_name or self._model is None:
            return

        char_cls_level = self._current_class_level(class_name)
        if char_cls_level == 0:
            # No levels in this class – show max-level progression as preview.
            all_slots = self._model.game_data().spells_per_day(class_name)
            if not all_slots:
                return
            char_cls_level = max(s.caster_level for s in all_slots)

        progression = self._model.game_data().spells_per_day(class_name)
        base_slots_at_level = {
            s.spell_level: s.count
            for s in progression
            if s.caster_level == char_cls_level
        }
        if not base_slots_at_level:
            # Fall back to the highest available caster level.
            if progression:
                best = max(s.caster_level for s in progression)
                base_slots_at_level = {
                    s.spell_level: s.count
                    for s in progression
                    if s.caster_level == best
                }

        # Build base-slot list indexed 0-9.
        base_list = [base_slots_at_level.get(lvl, 0) for lvl in range(10)]

        # Apply bonus slots from the relevant ability score.
        ability_mod = self._ability_mod_for_class(class_name)
        total_list = spells_per_day(base_list, ability_mod)

        for lvl in range(10):
            base = base_list[lvl]
            total = total_list[lvl]
            # Show "—" for levels with no slots (base == 0 and no bonus).
            if base == 0 and total == 0:
                self._slot_base_labels[lvl].setText("—")
                self._slot_total_labels[lvl].setText("—")
            else:
                self._slot_base_labels[lvl].setText(str(base))
                self._slot_total_labels[lvl].setText(str(total))

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_class_changed(self, class_name: str) -> None:
        """Refresh the slot table when the selected caster class changes."""
        self._refresh_caster_level(class_name)
        self._update_slot_labels(class_name)

    def _on_deity_changed(self, deity_text: str) -> None:
        """Persist deity choice to the character model."""
        if self._model is None:
            return
        chosen = "" if deity_text in (_NO_DEITY, "") else deity_text
        if self._model.character.deity != chosen:
            self._model.character.deity = chosen

    def _on_domain_changed(self, _text: str) -> None:
        """Persist domain selections and refresh the domain-info panel."""
        self._sync_domains_to_model()
        self._refresh_domain_info()

    def _refresh_domain_info(self) -> None:
        """Update the domain granted-power and spell list display."""
        if self._model is None:
            self._domain_info.setPlainText("")
            return
        repo = self._model.game_data()
        lines: list[str] = []
        for slot_idx, combo in enumerate(
            (self._domain1_combo, self._domain2_combo), start=1
        ):
            name = combo.currentText()
            if name in (_NO_DOMAIN, ""):
                continue
            domain = repo.get_domain(name)
            if domain is None:
                continue
            lines.append(f"=== Domain {slot_idx}: {domain.name} ===")
            if domain.granted_power:
                lines.append(f"Granted Power: {domain.granted_power}")
            lines.append("Domain Spells:")
            for lvl, spell in enumerate(domain.domain_spells, start=1):
                if spell:
                    lines.append(f"  {lvl}: {spell}")
            lines.append("")
        self._domain_info.setPlainText("\n".join(lines))

    def _on_add_spell(self) -> None:
        """Prompt the user to pick a spell and add it to the prepared list."""
        if self._model is None:
            return
        spell_names = self._model.game_data().list_spell_names()
        spell_name = pick_from_catalog(self, "Add Spell", "Spell:", spell_names)
        if not spell_name:
            return
        class_name = self._prep_class_combo.currentText()
        spell_level = self._prep_level_spin.value()
        entry = {
            "class_name": class_name,
            "spell_level": spell_level,
            "spell_name": spell_name,
        }
        self._model.character.spells_prepared.append(entry)
        label = f"[{class_name}] Lv{spell_level}: {spell_name}"
        self._prepared_list.addItem(label)

    def _on_remove_spell(self) -> None:
        """Remove the selected spell(s) from the prepared list."""
        rows = sorted(
            (
                self._prepared_list.row(item)
                for item in self._prepared_list.selectedItems()
            ),
            reverse=True,
        )
        for row in rows:
            self._prepared_list.takeItem(row)
            if self._model is not None and row < len(
                self._model.character.spells_prepared
            ):
                del self._model.character.spells_prepared[row]

    # ------------------------------------------------------------------
    # Model synchronisation
    # ------------------------------------------------------------------

    def _sync_domains_to_model(self) -> None:
        """Write current domain selections back to the character model."""
        if self._model is None:
            return
        domains: list[str] = []
        for combo in (self._domain1_combo, self._domain2_combo):
            name = combo.currentText()
            if name not in (_NO_DOMAIN, ""):
                domains.append(name)
        self._model.character.domains = domains

    def _sync_from_model(self) -> None:
        """Load all spell-related state from the character model into the UI."""
        if self._model is None:
            return
        self._load_classes()
        self._load_domains()
        char = self._model.character

        # Deity
        deity_text = char.deity or _NO_DEITY
        self._deity_combo.blockSignals(True)
        idx = self._deity_combo.findText(deity_text)
        if idx >= 0:
            self._deity_combo.setCurrentIndex(idx)
        else:
            self._deity_combo.setCurrentText(deity_text)
        self._deity_combo.blockSignals(False)

        # Domains (up to 2)
        for slot, combo in enumerate((self._domain1_combo, self._domain2_combo)):
            domain_name = char.domains[slot] if slot < len(char.domains) else _NO_DOMAIN
            combo.blockSignals(True)
            idx = combo.findText(domain_name)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentText(domain_name)
            combo.blockSignals(False)
        self._refresh_domain_info()

        # Prepared/known spells
        self._prepared_list.clear()
        for spell in char.spells_prepared:
            cn = spell.get("class_name", "")
            sl = spell.get("spell_level", 0)
            sn = spell.get("spell_name", "")
            self._prepared_list.addItem(f"[{cn}] Lv{sl}: {sn}")

        # Refresh computed values
        self._refresh_asf()
        self._refresh_slots()
