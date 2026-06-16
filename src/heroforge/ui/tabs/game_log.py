"""Game Log tab for HeroForge-Anew."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class GameLogTab(QWidget):
    """Simple session notes and game log."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        layout.addWidget(self._log_view)

        entry_row = QHBoxLayout()
        self._entry_edit = QLineEdit()
        self._entry_edit.setPlaceholderText("Enter a log entry and press Add…")
        self._entry_edit.returnPressed.connect(self._add_entry)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_entry)
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._log_view.clear)
        entry_row.addWidget(self._entry_edit)
        entry_row.addWidget(add_btn)
        entry_row.addWidget(clear_btn)
        layout.addLayout(entry_row)

    def _add_entry(self) -> None:
        text = self._entry_edit.text().strip()
        if text:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._log_view.append(f"[{ts}] {text}")
            self._entry_edit.clear()
