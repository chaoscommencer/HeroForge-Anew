"""Custom class creation dialog for HeroForge-Anew."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QSpinBox, QWidget,
)
from heroforge.models.class_ import Class


class CustomClassDialog(QDialog):
    """Create a custom homebrew class."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Custom Class")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._name_edit = QLineEdit()
        self._is_prestige = QCheckBox()
        self._hit_die = QSpinBox(); self._hit_die.setRange(4, 12); self._hit_die.setValue(8)
        self._bab_combo = QComboBox(); self._bab_combo.addItems(["fast", "medium", "slow"])
        self._fort_combo = QComboBox(); self._fort_combo.addItems(["good", "poor"])
        self._ref_combo = QComboBox(); self._ref_combo.addItems(["good", "poor"])
        self._will_combo = QComboBox(); self._will_combo.addItems(["good", "poor"])
        self._sp_spin = QSpinBox(); self._sp_spin.setRange(2, 10); self._sp_spin.setValue(4)
        layout.addRow("Class Name:", self._name_edit)
        layout.addRow("Prestige Class:", self._is_prestige)
        layout.addRow("Hit Die:", self._hit_die)
        layout.addRow("BAB Progression:", self._bab_combo)
        layout.addRow("Fort Progression:", self._fort_combo)
        layout.addRow("Ref Progression:", self._ref_combo)
        layout.addRow("Will Progression:", self._will_combo)
        layout.addRow("Skill Points/Level:", self._sp_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_class(self) -> Class:
        return Class(
            name=self._name_edit.text().strip(),
            is_prestige=self._is_prestige.isChecked(),
            hit_die=self._hit_die.value(),
            bab_progression=self._bab_combo.currentText(),
            fort_progression=self._fort_combo.currentText(),
            ref_progression=self._ref_combo.currentText(),
            will_progression=self._will_combo.currentText(),
            skill_points_per_level=self._sp_spin.value(),
        )
