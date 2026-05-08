"""Source book selection dialog for HeroForge-Anew."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)


class SourceSelectDialog(QDialog):
    """Select which sourcebooks to include in lists."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Sources")
        self.setMinimumSize(400, 400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enable sourcebooks to include in lookups:"))
        self._source_list = QListWidget()
        self._source_list.addItems(
            [
                "PHB – Player's Handbook",
                "DMG – Dungeon Master's Guide",
                "MM – Monster Manual",
                "CAd – Complete Adventurer",
                "CAr – Complete Arcane",
                "CD – Complete Divine",
                "CW – Complete Warrior",
                "MoI – Magic of Incarnum",
                "ToB – Tome of Battle",
                "XPH – Expanded Psionics Handbook",
                "UA – Unearthed Arcana",
            ]
        )
        layout.addWidget(self._source_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def selected_sources(self) -> list[str]:
        return [
            item.text().split(" – ")[0]
            for item in [
                self._source_list.item(i) for i in range(self._source_list.count())
            ]
            if item is not None
        ]
