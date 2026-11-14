"""Languages tab for HeroForge-Anew.

Languages are loaded from the seeded ``languages`` catalogue, validated against
the character's racial automatic languages and Intelligence-based bonus slots
(PHB p82), and persisted to :attr:`Character.languages`.
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
    QVBoxLayout,
    QWidget,
)

from heroforge.logic.languages import automatic_languages, bonus_language_slots
from heroforge.ui.tabs._tab_helper import pick_from_catalog

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class LanguagesTab(QWidget):
    """Language selection and management backed by the character model."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._build_ui()
        if model:
            model.character_reset.connect(self._sync_from_model)
            model.character_loaded.connect(lambda _id: self._sync_from_model())
            model.derived_stats_changed.connect(self._refresh_automatic)
            self._sync_from_model()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        auto_box = QGroupBox("Automatic Languages")
        auto_layout = QVBoxLayout(auto_box)
        self._auto_lbl = QLabel("Common")
        self._auto_lbl.setWordWrap(True)
        auto_layout.addWidget(self._auto_lbl)
        layout.addWidget(auto_box)

        known_box = QGroupBox("Bonus Languages")
        known_layout = QVBoxLayout(known_box)
        self._slots_lbl = QLabel("Bonus language slots: 0")
        known_layout.addWidget(self._slots_lbl)
        self._known_list = QListWidget()
        known_layout.addWidget(self._known_list)

        add_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Language…")
        self._rm_btn = QPushButton("Remove Selected")
        self._add_btn.clicked.connect(self._add_language)
        self._rm_btn.clicked.connect(self._remove_language)
        add_row.addWidget(self._add_btn)
        add_row.addWidget(self._rm_btn)
        add_row.addStretch()
        known_layout.addLayout(add_row)
        layout.addWidget(known_box)

        layout.addWidget(
            QLabel(
                "<i>Note: Common and racial languages are automatic. A positive "
                "Intelligence modifier grants that many bonus languages "
                "(PHB p82).</i>"
            )
        )
        layout.addStretch()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _bonus_slots(self) -> int:
        if self._model is None:
            return 0
        int_score = int(self._model.character.ability_scores.get("INT", 10))
        return bonus_language_slots(int_score)

    def _automatic(self) -> list[str]:
        if self._model is None:
            return ["Common"]
        return automatic_languages(self._model.character.race)

    def _refresh_automatic(self) -> None:
        """Refresh the automatic-language label and bonus-slot count."""
        self._auto_lbl.setText(", ".join(self._automatic()))
        self._slots_lbl.setText(
            f"Bonus language slots: {len(self._chosen())} / {self._bonus_slots()}"
        )

    def _chosen(self) -> list[str]:
        return [
            item.text()
            for i in range(self._known_list.count())
            if (item := self._known_list.item(i)) is not None
        ]

    def _sync_to_model(self) -> None:
        if self._model is not None:
            self._model.character.languages = self._chosen()
        self._refresh_automatic()

    def add_language(self, name: str) -> bool:
        """Add bonus language *name*, returning ``True`` when accepted.

        Rejects duplicates, automatic languages, and additions beyond the
        Intelligence-based bonus-slot budget.
        """
        name = name.strip()
        if not name:
            return False
        if name in self._automatic() or name in self._chosen():
            return False
        if len(self._chosen()) >= self._bonus_slots():
            return False
        self._known_list.addItem(name)
        self._sync_to_model()
        return True

    def _add_language(self) -> None:
        if len(self._chosen()) >= self._bonus_slots():
            QMessageBox.information(
                self,
                "Add Language",
                "No bonus language slots remaining. Increase Intelligence to "
                "learn more languages (PHB p82).",
            )
            return
        options = self._model.game_data().list_languages() if self._model else []
        # Hide languages already known (automatic or chosen).
        taken = set(self._automatic()) | set(self._chosen())
        options = [o for o in options if o not in taken]
        name = pick_from_catalog(self, "Add Language", "Language:", options)
        if name and not self.add_language(name):
            QMessageBox.information(self, "Add Language", f"Could not add '{name}'.")

    def _remove_language(self) -> None:
        for item in self._known_list.selectedItems():
            self._known_list.takeItem(self._known_list.row(item))
        self._sync_to_model()

    def _sync_from_model(self) -> None:
        self._known_list.clear()
        if self._model is not None:
            for lang in self._model.character.languages:
                self._known_list.addItem(lang)
        self._refresh_automatic()
