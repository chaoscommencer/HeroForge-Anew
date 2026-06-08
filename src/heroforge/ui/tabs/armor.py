"""Armor tab for HeroForge-Anew.

Body armor and shields are chosen from the seeded ``armor`` catalogue and stored
in :attr:`Character.equipment` under the ``Body Armor`` and ``Shield`` slots.
The AC summary (total/touch/flat-footed) is computed from the equipped items and
the character's Dexterity modifier (capped by the armor's max-Dex bonus) and
refreshes in real time via :func:`heroforge.logic.combat`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic import combat
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.db.data_access import ArmorItem
    from heroforge.ui.main_window import CharacterModel

_BODY_SLOT = "Body Armor"
_SHIELD_SLOT = "Shield"
_OWNED_SLOTS = {_BODY_SLOT, _SHIELD_SLOT}


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

    def _select(self, slot: str) -> None:
        catalog = self._model.game_data().list_armor() if self._model else []
        is_shield = slot == _SHIELD_SLOT
        catalog = [a for a in catalog if a.is_shield == is_shield]
        by_name = {a.name: a for a in catalog}
        name = pick_from_catalog(self, f"Select {slot}", "Item:", list(by_name))
        if name is None:
            return
        self._set_item(slot, by_name.get(name))
        self._sync_to_model()
        self._refresh_summary()

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
            catalog = {a.name: a for a in self._model.game_data().list_armor()}
            for entry in self._model.character.equipment:
                slot = entry.get("slot")
                if slot == _BODY_SLOT:
                    body = catalog.get(entry.get("item_name", ""))
                elif slot == _SHIELD_SLOT:
                    shield = catalog.get(entry.get("item_name", ""))
        self._set_item(_BODY_SLOT, body)
        self._set_item(_SHIELD_SLOT, shield)
        self._refresh_summary()
