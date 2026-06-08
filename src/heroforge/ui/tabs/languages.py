"""Languages tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class LanguagesTab(QWidget):
    """Language selection and management."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        known_box = QGroupBox("Known Languages")
        known_layout = QVBoxLayout(known_box)
        self._known_list = QListWidget()
        known_layout.addWidget(self._known_list)

        add_row = QHBoxLayout()
        self._lang_edit = QLineEdit()
        self._lang_edit.setPlaceholderText("Language name…")
        self._add_btn = QPushButton("Add")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add_language)
        self._rm_btn.clicked.connect(self._remove_language)
        add_row.addWidget(self._lang_edit)
        add_row.addWidget(self._add_btn)
        add_row.addWidget(self._rm_btn)
        known_layout.addLayout(add_row)
        layout.addWidget(known_box)

        # Automatic languages note
        layout.addWidget(
            QLabel(
                "<i>Note: Characters automatically know Common and their racial "
                "language. Additional languages granted by high INT are added "
                "here.</i>"
            )
        )
        layout.addStretch()

    def _add_language(self) -> None:
        text = self._lang_edit.text().strip()
        if text:
            self._known_list.addItem(text)
            self._lang_edit.clear()

    def _remove_language(self) -> None:
        for item in self._known_list.selectedItems():
            self._known_list.takeItem(self._known_list.row(item))
