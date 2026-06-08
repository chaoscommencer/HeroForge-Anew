"""Traits & Flaws tab for HeroForge-Anew.

Reference: Unearthed Arcana p86 (traits), p91 (flaws).  Options are loaded from
the seeded ``traits``/``flaws`` catalogues and selections persist to
:attr:`Character.traits` (each entry ``{"trait_name", "is_flaw"}``).  A
character may take at most two traits and two flaws (each flaw grants one bonus
feat).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel

# Optional-rule limits (Unearthed Arcana p86/p91).
_MAX_TRAITS = 2
_MAX_FLAWS = 2


class TraitsAndFlawsTab(QWidget):
    """Trait and flaw selection (Unearthed Arcana optional rules)."""

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

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        for section, label_text in (
            ("traits", "Traits (max 2, UA p86):"),
            ("flaws", "Flaws (grant bonus feats, UA p91):"),
        ):
            box = QGroupBox(label_text)
            box_layout = QVBoxLayout(box)
            lst = QListWidget()
            box_layout.addWidget(lst)
            btn_row = QHBoxLayout()
            add_btn = QPushButton(f"Add {section.capitalize()[:-1]}…")
            rm_btn = QPushButton("Remove Selected")
            add_btn.clicked.connect(lambda _, s=section: self._add(s))
            rm_btn.clicked.connect(lambda _, s=section: self._remove(s))
            btn_row.addWidget(add_btn)
            btn_row.addWidget(rm_btn)
            btn_row.addStretch()
            box_layout.addLayout(btn_row)
            inner_layout.addWidget(box)
            setattr(self, f"_{section}_list", lst)

        self._feat_lbl = QLabel("Bonus feats from flaws: 0")
        inner_layout.addWidget(self._feat_lbl)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def _list(self, section: str) -> QListWidget:
        return getattr(self, f"_{section}_list")  # type: ignore[no-any-return]

    def _names(self, section: str) -> list[str]:
        lst = self._list(section)
        return [
            item.text() for i in range(lst.count()) if (item := lst.item(i)) is not None
        ]

    def _sync_to_model(self) -> None:
        if self._model is not None:
            entries: list[dict] = []  # type: ignore[type-arg]
            for name in self._names("traits"):
                entries.append({"trait_name": name, "is_flaw": False})
            for name in self._names("flaws"):
                entries.append({"trait_name": name, "is_flaw": True})
            self._model.character.traits = entries
        self._feat_lbl.setText(f"Bonus feats from flaws: {len(self._names('flaws'))}")

    def add_trait(self, name: str, *, is_flaw: bool = False) -> bool:
        """Add a trait or flaw, enforcing the per-category limit. Returns OK."""
        section = "flaws" if is_flaw else "traits"
        limit = _MAX_FLAWS if is_flaw else _MAX_TRAITS
        name = name.strip()
        if not name or name in self._names(section):
            return False
        if len(self._names(section)) >= limit:
            return False
        self._list(section).addItem(name)
        self._sync_to_model()
        return True

    def _add(self, section: str) -> None:
        is_flaw = section == "flaws"
        limit = _MAX_FLAWS if is_flaw else _MAX_TRAITS
        if len(self._names(section)) >= limit:
            QMessageBox.information(
                self,
                f"Add {section.capitalize()[:-1]}",
                f"A character may take at most {limit} {section}.",
            )
            return
        if self._model is not None:
            options = (
                self._model.game_data().list_flaws()
                if is_flaw
                else self._model.game_data().list_traits()
            )
        else:
            options = []
        options = [o for o in options if o not in self._names(section)]
        name = pick_from_catalog(
            self, f"Add {section.capitalize()[:-1]}", "Name:", options
        )
        if name and not self.add_trait(name, is_flaw=is_flaw):
            QMessageBox.information(
                self,
                f"Add {section.capitalize()[:-1]}",
                f"Could not add '{name}'.",
            )

    def _remove(self, section: str) -> None:
        lst = self._list(section)
        for item in lst.selectedItems():
            lst.takeItem(lst.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._list("traits").clear()
        self._list("flaws").clear()
        if self._model is not None:
            for entry in self._model.character.traits:
                name = entry.get("trait_name", "")
                if not name:
                    continue
                section = "flaws" if entry.get("is_flaw") else "traits"
                self._list(section).addItem(name)
        self._sync_to_model()
