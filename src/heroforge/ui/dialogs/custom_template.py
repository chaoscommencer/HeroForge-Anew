"""Custom template creation dialog for HeroForge-Anew."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLineEdit, QSpinBox, QWidget,
)


class CustomTemplateDialog(QDialog):
    """Create a custom homebrew template."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Custom Template")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._name_edit = QLineEdit()
        self._cr_adj = QDoubleSpinBox(); self._cr_adj.setRange(-5, 20)
        self._la_spin = QSpinBox(); self._la_spin.setRange(-5, 10)
        layout.addRow("Name:", self._name_edit)
        layout.addRow("CR Adjustment:", self._cr_adj)
        layout.addRow("Level Adjustment:", self._la_spin)
        for ab in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
            spin = QSpinBox(); spin.setRange(-20, 20)
            layout.addRow(f"{ab} Adj:", spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
