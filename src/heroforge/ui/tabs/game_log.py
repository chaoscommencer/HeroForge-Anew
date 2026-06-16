"""Game Log tab for HeroForge-Anew.

Free-text session notes for a character.  Each entry is a timestamped line that
is persisted to :attr:`Character.game_log` (stored in the ``character_notes``
table) so the log survives save/load and reloads with the character.  The
Living Greyhawk variant lives in
:class:`~heroforge.ui.tabs.lg_game_log.LGGameLogTab`.
"""

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
    """Simple session notes and game log backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            self._sync_from_model()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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
        clear_btn.clicked.connect(self.clear_log)
        entry_row.addWidget(self._entry_edit)
        entry_row.addWidget(add_btn)
        entry_row.addWidget(clear_btn)
        layout.addLayout(entry_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(self, text: str, timestamp: str | None = None) -> bool:
        """Append a log entry and persist it to the model.

        Returns ``True`` if the entry was added, ``False`` for empty text.
        """
        content = text.strip()
        if not content:
            return False
        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
        if self._model is not None:
            self._model.character.game_log.append(
                {"timestamp": ts, "content": content}
            )
        self._append_line(ts, content)
        return True

    def clear_log(self) -> None:
        """Clear all log entries from the view and the model."""
        self._log_view.clear()
        if self._model is not None:
            self._model.character.game_log = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_entry(self) -> None:
        if self.add_entry(self._entry_edit.text()):
            self._entry_edit.clear()

    def _append_line(self, timestamp: str, content: str) -> None:
        self._log_view.append(f"[{timestamp}] {content}")

    def _sync_from_model(self) -> None:
        self._log_view.clear()
        if self._model is None:
            return
        for entry in self._model.character.game_log:
            self._append_line(
                entry.get("timestamp") or "", entry.get("content") or ""
            )
