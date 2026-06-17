"""Custom familiar creation dialog for HeroForge-Anew.

Mirrors the workbook's *Custom Familiar* sheet (Excel tab 9c).  Accepting the
dialog persists the homebrew familiar onto the character model's
``custom_content`` list (so it round-trips through save/load) and makes it
selectable on the Familiar tab.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from heroforge.logic.familiar import (
    CUSTOM_FAMILIAR_CONTENT_TYPE,
    CustomFamiliar,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class CustomFamiliarDialog(QDialog):
    """Create a custom familiar and persist it to the character model."""

    def __init__(
        self,
        model: CharacterModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Create Custom Familiar")
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._name_edit = QLineEdit()
        self._kind_edit = QLineEdit()
        self._bonus_edit = QLineEdit()
        self._int_spin = QSpinBox()
        self._int_spin.setRange(1, 30)
        self._int_spin.setValue(6)
        self._nat_armor_spin = QSpinBox()
        self._nat_armor_spin.setRange(0, 20)
        layout.addRow("Name:", self._name_edit)
        layout.addRow("Kind/Species:", self._kind_edit)
        layout.addRow("Special Bonus:", self._bonus_edit)
        layout.addRow("Intelligence:", self._int_spin)
        layout.addRow("Natural Armor:", self._nat_armor_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_familiar(self) -> CustomFamiliar:
        """Return the custom familiar described by the current field values."""
        return CustomFamiliar(
            name=self._name_edit.text().strip(),
            kind=self._kind_edit.text().strip(),
            special_bonus=self._bonus_edit.text().strip(),
            intelligence=self._int_spin.value(),
            natural_armor=self._nat_armor_spin.value(),
        )

    def accept(self) -> None:
        """Validate input, persist the familiar, then close the dialog.

        The familiar is stored on the character model's ``custom_content`` list
        as a single ``content_type == "familiar"`` entry.  An existing custom
        familiar with the same (case-insensitive) name is replaced so re-saving
        updates rather than duplicates.
        """
        familiar = self.get_familiar()
        if not familiar.name:
            QMessageBox.warning(
                self,
                "Create Custom Familiar",
                "Please enter a name for the custom familiar.",
            )
            return
        if self._model is not None:
            self._persist(familiar)
        super().accept()

    def _persist(self, familiar: CustomFamiliar) -> None:
        assert self._model is not None
        character = self._model.character
        name_key = familiar.name.casefold()
        retained = [
            entry
            for entry in character.custom_content
            if not (
                entry.get("content_type") == CUSTOM_FAMILIAR_CONTENT_TYPE
                and str(entry.get("name", "")).strip().casefold() == name_key
            )
        ]
        character.custom_content = retained + [familiar.to_content()]
