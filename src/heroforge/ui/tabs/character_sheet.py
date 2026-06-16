"""Character Sheet summary tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.export import character_sheet_data, export_character_sheet_text

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class CharacterSheetTab(QWidget):
    """Read-only plain-text character sheet summary with export."""

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

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Sheet")
        refresh_btn.clicked.connect(self._refresh)
        export_btn = QPushButton("Export to Text…")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(self._text_edit.font())
        layout.addWidget(self._text_edit)
        self._refresh()

    def _refresh(self) -> None:
        data: dict = {}  # type: ignore[type-arg]
        if self._model is not None:
            data = character_sheet_data(
                self._model.character, self._model.derived_stats()
            )
        text = export_character_sheet_text(data)
        self._text_edit.setPlainText(text)

    def _export(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Character Sheet", "", "Text Files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text_edit.toPlainText())
