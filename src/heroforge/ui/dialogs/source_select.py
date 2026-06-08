"""Source book selection dialog for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.db.data_access import GameDataRepository


class SourceSelectDialog(QDialog):
    """Select which sourcebooks to include in lists.

    The sourcebook list is loaded from the ``sources`` table via the shared
    :class:`~heroforge.db.data_access.GameDataRepository` rather than being
    hardcoded, so it always reflects the seeded database.
    """

    def __init__(
        self,
        repo: GameDataRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setWindowTitle("Select Sources")
        self.setMinimumSize(400, 400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enable sourcebooks to include in lookups:"))
        self._source_list = QListWidget()
        self._source_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        if self._repo is not None:
            for source in self._repo.list_sources():
                self._source_list.addItem(source.label)
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
            item.text().split(" – ")[0] for item in self._source_list.selectedItems()
        ]
