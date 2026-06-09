"""Race & Templates tab for HeroForge-Anew."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from heroforge.ui.main_window import CharacterModel


class RaceAndTemplatesTab(QWidget):
    """Race selection and template application."""

    def __init__(
        self, model: CharacterModel | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._available_templates: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(10)

        # Race selection
        race_box = QGroupBox("Race")
        race_form = QFormLayout(race_box)
        self._race_combo = QComboBox()
        self._race_combo.setEditable(True)
        self._race_combo.setPlaceholderText("Select or type race name…")
        race_form.addRow("Race:", self._race_combo)

        self._race_info = QLabel("Select a race to view details.")
        self._race_info.setWordWrap(True)
        race_form.addRow("Info:", self._race_info)
        inner_layout.addWidget(race_box)

        # Templates
        tmpl_box = QGroupBox("Applied Templates")
        tmpl_layout = QVBoxLayout(tmpl_box)
        self._template_list = QListWidget()
        tmpl_layout.addWidget(self._template_list)

        btn_row = QHBoxLayout()
        self._add_template_btn = QPushButton("Add Template…")
        self._remove_template_btn = QPushButton("Remove Selected")
        btn_row.addWidget(self._add_template_btn)
        btn_row.addWidget(self._remove_template_btn)
        btn_row.addStretch()
        tmpl_layout.addLayout(btn_row)
        inner_layout.addWidget(tmpl_box)

        # Racial traits
        traits_box = QGroupBox("Racial Traits")
        traits_layout = QVBoxLayout(traits_box)
        self._traits_list = QListWidget()
        self._traits_list.setToolTip("Special abilities granted by the selected race")
        traits_layout.addWidget(self._traits_list)
        inner_layout.addWidget(traits_box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._remove_template_btn.clicked.connect(self._remove_template)
        self._add_template_btn.clicked.connect(self._add_template)
        self._race_combo.currentTextChanged.connect(self._on_race_changed)
        self._load_data()

    def _load_data(self) -> None:
        """Populate race and template controls from the seeded database."""
        if self._model is None:
            return
        repo = self._model.game_data()
        self._race_combo.clear()
        self._race_combo.addItems(repo.list_races())
        self._race_combo.setCurrentIndex(-1)
        self._available_templates = repo.list_templates()

    def _on_race_changed(self, race_name: str) -> None:
        """Refresh the racial traits list when a new race is chosen."""
        self._traits_list.clear()
        if not race_name or self._model is None:
            return
        repo = self._model.game_data()
        for ability in repo.list_racial_abilities(race_name):
            self._traits_list.addItem(ability.ability_name)

    def _add_template(self) -> None:
        """Add a database-backed template that is not already applied."""
        applied: set[str] = set()
        for i in range(self._template_list.count()):
            item = self._template_list.item(i)
            if item is not None:
                applied.add(item.text())
        for name in self._available_templates:
            if name not in applied:
                self._template_list.addItem(name)
                break

    def _remove_template(self) -> None:
        for item in self._template_list.selectedItems():
            self._template_list.takeItem(self._template_list.row(item))
