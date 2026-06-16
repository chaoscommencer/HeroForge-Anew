"""Options dialog for HeroForge-Anew."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)


class OptionsDialog(QDialog):
    """Application options and preferences."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.setMinimumWidth(350)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._point_buy_spin = QSpinBox()
        self._point_buy_spin.setRange(15, 40)
        self._point_buy_spin.setValue(25)
        layout.addRow("Point-Buy Budget:", self._point_buy_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
