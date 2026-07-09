"""Custom class creation dialog for HeroForge-Anew.

Mirrors the workbook's *Custom Class* sheet.  Accepting the dialog persists the
homebrew class onto the character model's ``custom_content`` list (so it
round-trips through save/load); custom prestige classes then become selectable
on the Prestige Classes tab (Excel tab 3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from heroforge.logic.prestige import (
    CUSTOM_CLASS_CONTENT_TYPE,
    custom_class_to_content,
)
from heroforge.models.class_ import Class

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class CustomClassDialog(QDialog):
    """Create a custom homebrew class and persist it to the character model."""

    def __init__(
        self,
        model: CharacterModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Create Custom Class")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._name_edit = QLineEdit()
        self._is_prestige = QCheckBox()
        self._hit_die = QSpinBox()
        self._hit_die.setRange(4, 12)
        self._hit_die.setValue(8)
        self._bab_combo = QComboBox()
        self._bab_combo.addItems(["fast", "medium", "slow"])
        self._fort_combo = QComboBox()
        self._fort_combo.addItems(["good", "poor"])
        self._ref_combo = QComboBox()
        self._ref_combo.addItems(["good", "poor"])
        self._will_combo = QComboBox()
        self._will_combo.addItems(["good", "poor"])
        self._sp_spin = QSpinBox()
        self._sp_spin.setRange(2, 10)
        self._sp_spin.setValue(4)
        self._prereq_edit = QLineEdit()
        self._prereq_edit.setPlaceholderText(
            "Semicolon-separated, e.g. +6 BAB; Dodge; Tumble 5 ranks"
        )
        layout.addRow("Class Name:", self._name_edit)
        layout.addRow("Prestige Class:", self._is_prestige)
        layout.addRow("Hit Die:", self._hit_die)
        layout.addRow("BAB Progression:", self._bab_combo)
        layout.addRow("Fort Progression:", self._fort_combo)
        layout.addRow("Ref Progression:", self._ref_combo)
        layout.addRow("Will Progression:", self._will_combo)
        layout.addRow("Skill Points/Level:", self._sp_spin)
        layout.addRow("Prerequisites:", self._prereq_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_class(self) -> Class:
        """Return the class described by the current field values."""
        prerequisites = [
            part.strip() for part in self._prereq_edit.text().split(";") if part.strip()
        ]
        return Class(
            name=self._name_edit.text().strip(),
            is_prestige=self._is_prestige.isChecked(),
            hit_die=self._hit_die.value(),
            bab_progression=self._bab_combo.currentText(),
            fort_progression=self._fort_combo.currentText(),
            ref_progression=self._ref_combo.currentText(),
            will_progression=self._will_combo.currentText(),
            skill_points_per_level=self._sp_spin.value(),
            prerequisites=prerequisites,
        )

    def accept(self) -> None:
        """Validate input, persist the class, then close the dialog.

        The class is stored on the character model's ``custom_content`` list as
        a single ``content_type == "class"`` entry.  An existing custom class
        with the same (case-insensitive) name is replaced so re-saving updates
        rather than duplicates.
        """
        cls = self.get_class()
        if not cls.name:
            QMessageBox.warning(
                self,
                "Create Custom Class",
                "Please enter a name for the custom class.",
            )
            return
        if self._model is not None:
            self._persist(cls)
            self._model.custom_content_changed.emit()
        super().accept()

    def _persist(self, cls: Class) -> None:
        assert self._model is not None
        character = self._model.character
        name_key = cls.name.casefold()
        retained = [
            entry
            for entry in character.custom_content
            if not (
                entry.get("content_type") == CUSTOM_CLASS_CONTENT_TYPE
                and str(entry.get("name", "")).strip().casefold() == name_key
            )
        ]
        character.custom_content = retained + [custom_class_to_content(cls)]
