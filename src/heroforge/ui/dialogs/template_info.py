"""Template info dialog for HeroForge-Anew."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout, QWidget,
)


class TemplateInfoDialog(QDialog):
    """Display detailed information about a creature template."""

    def __init__(self, template_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Template: {template_name or 'Unknown'}")
        self.setMinimumSize(500, 400)
        self._build_ui(template_name)

    def _build_ui(self, name: str) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h3>{name}</h3>"))
        self._info_text = QTextEdit()
        self._info_text.setReadOnly(True)
        self._info_text.setPlainText("(Template details loaded from database.)")
        layout.addWidget(self._info_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
