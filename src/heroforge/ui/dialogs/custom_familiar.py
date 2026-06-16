"""Custom familiar creation dialog for HeroForge-Anew."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)


class CustomFamiliarDialog(QDialog):
    """Create a custom familiar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
