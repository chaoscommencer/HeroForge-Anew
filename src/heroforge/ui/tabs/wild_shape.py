"""Wild Shape tab for HeroForge-Anew (Excel tab 9d).

Reference: PHB p37 (Druid class feature).  A druid of 5th level or higher can
assume the form of an animal (and, at higher levels, larger animals, plants,
elementals and magical beasts).  This tab lets the user pick an available form
from the seeded ``creatures`` catalogue — gated by Druid level per
:func:`heroforge.logic.wild_shape.available_forms` — and toggle it active.  When
active the form's size, physical ability scores and natural armor flow into the
character's derived stats via :meth:`CharacterModel.derived_stats`.

The selection is persisted to :attr:`Character.companions` as a single
``companion_type == "wild_shape"`` entry (the active flag is serialised into the
``notes`` column as JSON) so it round-trips through save/load, mirroring the
Animal Companion and Familiar tabs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.wild_shape import (
    COMPANION_TYPE,
    available_forms,
    druid_wild_shape_level,
)
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.db.data_access import Creature
    from heroforge.ui.main_window import CharacterModel

_NO_FORM = "(No form selected — see PHB p37.)"


class WildShapeTab(QWidget):
    """Druid Wild Shape form selection and activation, backed by the model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._loading = False
        self._form: Creature | None = None
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            # Re-evaluate availability when class levels (Druid level) change.
            model.class_levels_changed.connect(self._refresh_availability)
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

        select_box = QGroupBox("Wild Shape Form")
        select_form = QFormLayout(select_box)
        self._level_label = QLabel("0")
        select_form.addRow("Druid level:", self._level_label)

        self._form_edit = QLineEdit()
        self._form_edit.setReadOnly(True)
        self._form_edit.setPlaceholderText(_NO_FORM)
        form_row = QHBoxLayout()
        form_row.addWidget(self._form_edit)
        self._select_btn = QPushButton("Select…")
        self._select_btn.clicked.connect(self._select_form)
        form_row.addWidget(self._select_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear_form)
        form_row.addWidget(self._clear_btn)
        select_form.addRow("Form:", form_row)

        self._active_check = QCheckBox("Wild Shape active (apply form to character)")
        self._active_check.toggled.connect(self._on_changed)
        select_form.addRow("", self._active_check)
        inner_layout.addWidget(select_box)

        form_box = QGroupBox("Form Statistics")
        form_layout = QFormLayout(form_box)
        self._size_label = QLabel("—")
        self._type_label = QLabel("—")
        self._str_label = QLabel("—")
        self._dex_label = QLabel("—")
        self._con_label = QLabel("—")
        self._natural_armor_label = QLabel("—")
        self._speed_label = QLabel("—")
        self._hd_label = QLabel("—")
        form_layout.addRow("Size:", self._size_label)
        form_layout.addRow("Type:", self._type_label)
        form_layout.addRow("Strength:", self._str_label)
        form_layout.addRow("Dexterity:", self._dex_label)
        form_layout.addRow("Constitution:", self._con_label)
        form_layout.addRow("Natural Armor:", self._natural_armor_label)
        form_layout.addRow("Speed:", self._speed_label)
        form_layout.addRow("Hit Dice:", self._hd_label)
        inner_layout.addWidget(form_box)

        self._help_label = QLabel(
            "While Wild Shape is active the form's size, Strength, Dexterity, "
            "Constitution and natural armor replace your own; your mental scores "
            "(Int, Wis, Cha) are retained (PHB p37)."
        )
        self._help_label.setWordWrap(True)
        inner_layout.addWidget(self._help_label)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self._refresh_form_labels()

    # ------------------------------------------------------------------
    # Availability / selection
    # ------------------------------------------------------------------

    def _druid_level(self) -> int:
        """Return the character's Druid class level (PHB p37)."""
        if self._model is None:
            return 0
        return druid_wild_shape_level(self._model.character.classes)

    def _available_forms(self) -> list[Creature]:
        """Return the catalogue forms the druid can currently assume."""
        if self._model is None or not self._model.game_data().available:
            return []
        creatures = self._model.game_data().list_creatures()
        return available_forms(self._druid_level(), creatures)

    def _refresh_availability(self) -> None:
        """Update the Druid-level readout and enable/disable selection."""
        level = self._druid_level()
        self._level_label.setText(str(level))
        can_shape = level >= 5
        self._select_btn.setEnabled(can_shape)
        if not can_shape:
            self._active_check.setEnabled(False)
        else:
            self._active_check.setEnabled(self._form is not None)

    def _select_form(self) -> None:
        forms = self._available_forms()
        by_name = {c.name: c for c in forms}
        if not by_name:
            return
        name = pick_from_catalog(self, "Select Wild Shape Form", "Form:", list(by_name))
        if name is None:
            return
        self._form = by_name.get(name)
        self._form_edit.setText(name)
        self._refresh_form_labels()
        self._refresh_availability()
        self._on_changed()

    def _clear_form(self) -> None:
        self._form = None
        self._form_edit.clear()
        self._active_check.setChecked(False)
        self._refresh_form_labels()
        self._refresh_availability()
        self._on_changed()

    def _refresh_form_labels(self) -> None:
        """Refresh the read-only display of the selected form's statistics."""
        form = self._form
        if form is None:
            for label in (
                self._size_label,
                self._type_label,
                self._str_label,
                self._dex_label,
                self._con_label,
                self._natural_armor_label,
                self._speed_label,
                self._hd_label,
            ):
                label.setText("—")
            return
        type_text = form.type or "—"
        if form.subtype:
            type_text = f"{type_text} ({form.subtype})"
        self._size_label.setText(form.size or "—")
        self._type_label.setText(type_text)
        self._str_label.setText(str(form.ability_scores.get("STR", "—")))
        self._dex_label.setText(str(form.ability_scores.get("DEX", "—")))
        self._con_label.setText(str(form.ability_scores.get("CON", "—")))
        self._natural_armor_label.setText(f"+{form.natural_armor}")
        self._speed_label.setText(form.speed or "—")
        self._hd_label.setText(form.hit_dice or "—")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _entry(self) -> dict | None:  # type: ignore[type-arg]
        form_name = self._form_edit.text().strip()
        if not form_name:
            return None
        notes = {"active": self._active_check.isChecked()}
        return {
            "companion_type": COMPANION_TYPE,
            "name": "",
            "creature": form_name,
            "notes": json.dumps(notes),
        }

    def _sync_to_model(self) -> None:
        if self._model is None:
            return
        others = [
            c
            for c in self._model.character.companions
            if c.get("companion_type") != COMPANION_TYPE
        ]
        entry = self._entry()
        self._model.character.companions = (
            others + [entry] if entry is not None else others
        )
        # An active form changes size and physical scores, so announce the
        # change to refresh every dependent tab (PHB p37).
        self._model.derived_stats_changed.emit()

    def _on_changed(self, *_args: object) -> None:
        if not self._loading:
            self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._loading = True
        self._form = None
        self._form_edit.clear()
        self._active_check.setChecked(False)
        if self._model is not None:
            for entry in self._model.character.companions:
                if entry.get("companion_type") != COMPANION_TYPE:
                    continue
                form_name = entry.get("creature", "")
                self._form_edit.setText(form_name)
                notes = entry.get("notes", "")
                try:
                    data = json.loads(notes) if notes else {}
                except (TypeError, ValueError):
                    data = {}
                self._active_check.setChecked(bool(data.get("active", False)))
                if form_name and self._model.game_data().available:
                    self._form = self._model.game_data().get_creature(form_name)
                break
        self._loading = False
        self._refresh_form_labels()
        self._refresh_availability()


__all__ = ["WildShapeTab"]
