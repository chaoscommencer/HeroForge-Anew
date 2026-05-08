"""Shared base/helpers for HeroForge-Anew tab widgets."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

def make_placeholder_tab(title: str, description: str = "") -> type[QWidget]:
    """Factory that returns a simple placeholder QWidget subclass."""
    class _Placeholder(QWidget):
        def __init__(self, model=None, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            layout = QVBoxLayout(self)
            lbl = QLabel(f"<h2>{title}</h2>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            if description:
                desc = QLabel(description)
                desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
                desc.setWordWrap(True)
                layout.addWidget(desc)
            layout.addStretch()
    _Placeholder.__name__ = title.replace(" ", "") + "Tab"
    return _Placeholder
