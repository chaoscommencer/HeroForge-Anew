"""Traits & Flaws tab for HeroForge-Anew.

Reference: Unearthed Arcana p86 (traits), p91 (flaws).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class TraitsAndFlawsTab(QWidget):
    """Trait and flaw selection (Unearthed Arcana optional rules)."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        for section, label_text in (
            ("Traits", "Traits (max 2, UA p86):"),
            ("Flaws", "Flaws (grant bonus feats, UA p91):"),
        ):
            box = QGroupBox(label_text)
            box_layout = QVBoxLayout(box)
            lst = QListWidget()
            box_layout.addWidget(lst)
            btn_row = QHBoxLayout()
            rm_btn = QPushButton("Remove Selected")
            rm_btn.clicked.connect(lambda _, lst_=lst: self._remove(lst_))
            btn_row.addWidget(QPushButton(f"Add {section}…"))
            btn_row.addWidget(rm_btn)
            btn_row.addStretch()
            box_layout.addLayout(btn_row)
            inner_layout.addWidget(box)
            setattr(self, f"_{section.lower()}_list", lst)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _remove(self, lst: QListWidget) -> None:
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))
