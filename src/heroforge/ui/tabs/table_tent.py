"""Table Tent tab for HeroForge-Anew.

The Table Tent is the folded name-card a player stands on the table so their
character name and key combat numbers are visible from across the table.  It is
a read-only, printable summary derived from the active character, rendered via
:func:`~heroforge.logic.export.export_table_tent_text` and kept in sync with the
character model exactly like the Character Sheet tab.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.export import export_table_tent_text, table_tent_data

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class TableTentTab(QWidget):
    """Read-only printable folded name-card summary with export."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.character_reset.connect(self._refresh)
            model.character_loaded.connect(self._refresh)
            model.derived_stats_changed.connect(self._refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(
            QLabel(
                "<b>Table Tent</b> – a printable folded name-card. Print, fold "
                "along the centre line, and stand it on the table."
            )
        )

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Tent")
        refresh_btn.clicked.connect(self._refresh)
        export_btn = QPushButton("Export to Text…")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        # A fixed-pitch font keeps the centred panels aligned when printed.
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_edit.setFont(fixed_font)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text_edit)
        self._refresh()

    def _refresh(self) -> None:
        data: dict = {}  # type: ignore[type-arg]
        if self._model is not None:
            data = table_tent_data(self._model.character, self._model.derived_stats())
        text = export_table_tent_text(data)
        self._text_edit.setPlainText(text)

    def _export(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Table Tent", "", "Text Files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text_edit.toPlainText())
