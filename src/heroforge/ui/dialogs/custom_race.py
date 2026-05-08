"""Custom race creation dialog for HeroForge-Anew."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QSpinBox, QWidget,
)
from heroforge.models.race import Race


class CustomRaceDialog(QDialog):
    """Create a custom homebrew race."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Custom Race")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        self._name_edit = QLineEdit()
        self._size_edit = QLineEdit("Medium")
        self._type_edit = QLineEdit("Humanoid")
        self._speed_spin = QSpinBox(); self._speed_spin.setRange(0, 120); self._speed_spin.setValue(30)
        self._la_spin = QSpinBox(); self._la_spin.setRange(0, 10)
        ability_spins = {}
        for ab in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
            spin = QSpinBox(); spin.setRange(-10, 10)
            layout.addRow(f"{ab} Adj:", spin)
            ability_spins[ab] = spin
        self._ability_spins = ability_spins
        layout.insertRow(0, "Name:", self._name_edit)
        layout.insertRow(1, "Size:", self._size_edit)
        layout.insertRow(2, "Type:", self._type_edit)
        layout.insertRow(3, "Base Speed:", self._speed_spin)
        layout.insertRow(4, "Level Adj:", self._la_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_race(self) -> Race:
        return Race(
            name=self._name_edit.text().strip(),
            size=self._size_edit.text().strip(),
            type=self._type_edit.text().strip(),
            base_land_speed=self._speed_spin.value(),
            level_adjustment=self._la_spin.value(),
            **{f"{ab.lower()}_adj": self._ability_spins[ab].value()
               for ab in ("STR", "DEX", "CON", "INT", "WIS", "CHA")},
        )
