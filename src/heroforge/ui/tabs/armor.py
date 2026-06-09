"""Armor tab for HeroForge-Anew.

Body armor and shields are chosen from the seeded ``armor`` catalogue and stored
in :attr:`Character.equipment` under the ``Body Armor`` and ``Shield`` slots.
The AC summary (total/touch/flat-footed) is computed from the equipped items and
the character's Dexterity modifier (capped by the armor's max-Dex bonus) and
refreshes in real time via :func:`heroforge.logic.combat`.

Custom armor/shield entries not present in the game catalogue are persisted to
the ``character_custom_armor`` table in the character save file and merged back
into the catalogue on load.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heroforge.db.data_access import ArmorItem
from heroforge.logic import combat
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

_BODY_SLOT = "Body Armor"
_SHIELD_SLOT = "Shield"
_OWNED_SLOTS = {_BODY_SLOT, _SHIELD_SLOT}


class _CustomArmorDialog(QDialog):
    """Dialog for specifying stats of a custom armor or shield entry."""

    def __init__(
        self, name: str, is_shield: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Custom {'Shield' if is_shield else 'Armor'}: {name}")
        layout = QFormLayout(self)

        self._ac = QSpinBox()
        self._ac.setRange(0, 99)
        layout.addRow("AC Bonus:", self._ac)

        self._maxdex = QSpinBox()
        self._maxdex.setRange(-1, 99)
        self._maxdex.setSpecialValueText("—")
        self._maxdex.setValue(-1)
        layout.addRow("Max Dex Bonus:", self._maxdex)

        self._acp = QSpinBox()
        self._acp.setRange(-99, 0)
        layout.addRow("Check Penalty:", self._acp)

        self._asf = QSpinBox()
        self._asf.setRange(0, 100)
        self._asf.setSuffix("%")
        layout.addRow("Arcane Spell Failure:", self._asf)

        self._weight = QDoubleSpinBox()
        self._weight.setRange(0, 9999)
        self._weight.setDecimals(1)
        self._weight.setSuffix(" lb")
        layout.addRow("Weight:", self._weight)

        self._is_shield = QCheckBox()
        self._is_shield.setChecked(is_shield)
        layout.addRow("Shield:", self._is_shield)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def result_item(self, name: str) -> ArmorItem:
        """Return an :class:`ArmorItem` from the dialog's current field values."""
        max_dex = None if self._maxdex.value() < 0 else self._maxdex.value()
        item_type = "Shield" if self._is_shield.isChecked() else "Armor"
        return ArmorItem(
            name=name,
            type=item_type,
            ac_bonus=self._ac.value(),
            max_dex_bonus=max_dex,
            check_penalty=self._acp.value(),
            arcane_spell_failure=self._asf.value(),
            weight=self._weight.value(),
            source="",
        )


class ArmorTab(QWidget):
    """Armor and shield selection with AC calculation backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        # Selected catalogue items (None = none equipped).
        self._body: ArmorItem | None = None
        self._shield: ArmorItem | None = None
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

        self._labels: dict[str, dict[str, QLabel]] = {}
        for slot in (_BODY_SLOT, _SHIELD_SLOT):
            box = QGroupBox(slot)
            form = QFormLayout(box)
            name_lbl = QLabel("(none)")
            ac_lbl = QLabel("0")
            acp_lbl = QLabel("0")
            asf_lbl = QLabel("0%")
            maxdex_lbl = QLabel("—")
            form.addRow("Equipped:", name_lbl)
            form.addRow("AC Bonus:", ac_lbl)
            form.addRow("Check Penalty:", acp_lbl)
            form.addRow("Arcane Spell Failure:", asf_lbl)
            form.addRow("Max Dex Bonus:", maxdex_lbl)
            btn_row = QHBoxLayout()
            select_btn = QPushButton("Select…")
            clear_btn = QPushButton("Remove")
            select_btn.clicked.connect(lambda _, s=slot: self._select(s))
            clear_btn.clicked.connect(lambda _, s=slot: self._clear(s))
            btn_row.addWidget(select_btn)
            btn_row.addWidget(clear_btn)
            btn_row.addStretch()
            form.addRow(btn_row)
            self._labels[slot] = {
                "name": name_lbl,
                "ac": ac_lbl,
                "acp": acp_lbl,
                "asf": asf_lbl,
                "maxdex": maxdex_lbl,
            }
            inner_layout.addWidget(box)

        summary_box = QGroupBox("AC Summary")
        summary_form = QFormLayout(summary_box)
        self._total_ac_lbl = QLabel("10")
        self._touch_ac_lbl = QLabel("10")
        self._ff_ac_lbl = QLabel("10")
        self._acp_lbl = QLabel("0")
        summary_form.addRow("Total AC:", self._total_ac_lbl)
        summary_form.addRow("Touch AC:", self._touch_ac_lbl)
        summary_form.addRow("Flat-Footed AC:", self._ff_ac_lbl)
        summary_form.addRow("Armor Check Penalty:", self._acp_lbl)
        inner_layout.addWidget(summary_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _slot_attr(self, slot: str) -> str:
        return "_body" if slot == _BODY_SLOT else "_shield"

    def _set_item(self, slot: str, item: ArmorItem | None) -> None:
        setattr(self, self._slot_attr(slot), item)
        lbls = self._labels[slot]
        if item is None:
            lbls["name"].setText("(none)")
            lbls["ac"].setText("0")
            lbls["acp"].setText("0")
            lbls["asf"].setText("0%")
            lbls["maxdex"].setText("—")
        else:
            lbls["name"].setText(item.name)
            lbls["ac"].setText(str(item.ac_bonus))
            lbls["acp"].setText(str(item.check_penalty))
            lbls["asf"].setText(f"{item.arcane_spell_failure}%")
            lbls["maxdex"].setText(
                "—" if item.max_dex_bonus is None else str(item.max_dex_bonus)
            )

    def _merged_catalog(self, is_shield: bool) -> dict[str, ArmorItem]:
        """Return the merged game + character-custom catalog for this slot type."""
        game_items = self._model.game_data().list_armor() if self._model else []
        merged = {a.name: a for a in game_items if a.is_shield == is_shield}
        if self._model:
            for entry in self._model.character.custom_armor:
                name = entry.get("name", "")
                if not name:
                    continue
                # Compare against the canonical value set by _CustomArmorDialog.
                item_is_shield = entry.get("type") == "Shield"
                if item_is_shield != is_shield:
                    continue
                raw_maxdex = entry.get("max_dex_bonus")
                try:
                    maxdex = None if raw_maxdex in (None, "", "—") else int(raw_maxdex)
                except (TypeError, ValueError):
                    maxdex = None
                merged[name] = ArmorItem(
                    name=name,
                    type=entry.get("type", "Shield" if is_shield else "Armor"),
                    ac_bonus=int(entry.get("ac_bonus", 0)),
                    max_dex_bonus=maxdex,
                    check_penalty=int(entry.get("check_penalty", 0)),
                    arcane_spell_failure=int(entry.get("arcane_spell_failure", 0)),
                    weight=float(entry.get("weight", 0)),
                    source="",
                )
        return merged

    def _select(self, slot: str) -> None:
        is_shield = slot == _SHIELD_SLOT
        by_name = self._merged_catalog(is_shield)
        name = pick_from_catalog(self, f"Select {slot}", "Item:", list(by_name))
        if name is None:
            return
        if name in by_name:
            item = by_name[name]
        else:
            # New custom entry — collect stats via dialog.
            dlg = _CustomArmorDialog(name, is_shield, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            item = dlg.result_item(name)
            self._add_to_custom_armor(item)
        self._set_item(slot, item)
        self._sync_to_model()
        self._refresh_summary()

    def _add_to_custom_armor(self, item: ArmorItem) -> None:
        """Persist *item* to :attr:`Character.custom_armor`.

        This only updates the in-memory character; the entry is written to the
        character DB on next save.
        """
        if self._model is None:
            return
        existing = self._model.character.custom_armor
        # Replace any pre-existing entry with the same name.
        self._model.character.custom_armor = [
            e for e in existing if e.get("name") != item.name
        ] + [
            {
                "name": item.name,
                "type": item.type,
                "ac_bonus": item.ac_bonus,
                "max_dex_bonus": item.max_dex_bonus,
                "check_penalty": item.check_penalty,
                "arcane_spell_failure": item.arcane_spell_failure,
                "weight": item.weight,
            }
        ]

    def _clear(self, slot: str) -> None:
        self._set_item(slot, None)
        self._sync_to_model()
        self._refresh_summary()

    def _entries(self) -> list[dict]:  # type: ignore[type-arg]
        result: list[dict] = []  # type: ignore[type-arg]
        for slot, item in ((_BODY_SLOT, self._body), (_SHIELD_SLOT, self._shield)):
            if item is not None:
                result.append(
                    {
                        "item_name": item.name,
                        "quantity": 1,
                        "weight": item.weight,
                        "equipped": 1,
                        "slot": slot,
                        "notes": "",
                    }
                )
        return result

    def _sync_to_model(self) -> None:
        if self._model is None:
            return
        others = [
            e
            for e in self._model.character.equipment
            if e.get("slot") not in _OWNED_SLOTS
        ]
        self._model.character.equipment = others + self._entries()

    # ------------------------------------------------------------------
    # AC summary
    # ------------------------------------------------------------------

    def _refresh_summary(self) -> None:
        dex_mod = 0
        if self._model is not None:
            dex_mod = self._model.derived_stats().ability_modifiers.get("DEX", 0)
        caps = [
            i.max_dex_bonus
            for i in (self._body, self._shield)
            if i is not None and i.max_dex_bonus is not None
        ]
        effective_dex = dex_mod
        if caps:
            effective_dex = min(dex_mod, min(caps))
        armor_bonus = self._body.ac_bonus if self._body else 0
        shield_bonus = self._shield.ac_bonus if self._shield else 0
        total = combat.armor_class(
            effective_dex, armor=armor_bonus, shield=shield_bonus
        )
        touch = combat.touch_ac(effective_dex)
        flat = combat.flat_footed_ac(armor=armor_bonus, shield=shield_bonus)
        check_penalty = sum(
            i.check_penalty for i in (self._body, self._shield) if i is not None
        )
        self._total_ac_lbl.setText(str(total))
        self._touch_ac_lbl.setText(str(touch))
        self._ff_ac_lbl.setText(str(flat))
        self._acp_lbl.setText(str(check_penalty))

    def _sync_from_model(self) -> None:
        body = shield = None
        if self._model is not None:
            # Merged catalog: game entries + character's custom armor.
            merged_armor = self._merged_catalog(is_shield=False)
            merged_shields = self._merged_catalog(is_shield=True)
            merged_all = {**merged_armor, **merged_shields}
            for entry in self._model.character.equipment:
                slot = entry.get("slot")
                item_name = entry.get("item_name", "")
                if not item_name or slot not in _OWNED_SLOTS:
                    continue
                is_shield = slot == _SHIELD_SLOT
                item = merged_all.get(item_name)
                if item is None:
                    # Legacy save with inline stats — migrate to custom_armor.
                    item = ArmorItem(
                        name=item_name,
                        type=entry.get("item_type")
                        or ("Shield" if is_shield else "Armor"),
                        ac_bonus=int(entry.get("ac_bonus") or 0),
                        max_dex_bonus=(
                            None
                            if entry.get("max_dex_bonus") in (None, "", "—")
                            else int(entry.get("max_dex_bonus"))
                        ),
                        check_penalty=int(entry.get("check_penalty") or 0),
                        arcane_spell_failure=int(
                            entry.get("arcane_spell_failure") or 0
                        ),
                        weight=float(entry.get("weight") or 0.0),
                        source="",
                    )
                    self._add_to_custom_armor(item)
                if slot == _BODY_SLOT:
                    body = item
                elif slot == _SHIELD_SLOT:
                    shield = item
        self._set_item(_BODY_SLOT, body)
        self._set_item(_SHIELD_SLOT, shield)
        self._refresh_summary()
