"""Options dialog for HeroForge-Anew.

Presents the workbook's *Options* sheet (``docs/conversion-plan.md`` §11.2) as a
form built declaratively from :data:`heroforge.models.options.OPTION_SPECS`, so
adding a new option only requires extending that registry. Stored values are
read in via the constructor and read back out with :meth:`get_options`.
"""

from __future__ import annotations

from collections.abc import Mapping

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)

from heroforge.models.options import OPTION_SPECS, POINT_BUY_BUDGET


class OptionsDialog(QDialog):
    """Application options and preferences.

    The dialog is pre-populated from the supplied *options* mapping (typically
    ``model.character.options``) and exposes the user's choices via
    :meth:`get_options`, so callers can persist them back onto the active
    character.
    """

    def __init__(
        self,
        options: Mapping[str, object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.setMinimumWidth(350)
        self._spinboxes: dict[str, QSpinBox] = {}
        self._build_ui()
        self.set_options(options or {})

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        for spec in OPTION_SPECS:
            spin = QSpinBox()
            spin.setRange(spec.minimum, spec.maximum)
            spin.setValue(spec.default)
            layout.addRow(spec.label, spin)
            self._spinboxes[spec.key] = spin

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def set_options(self, options: Mapping[str, object]) -> None:
        """Populate the widgets from a stored ``character.options`` mapping.

        Unknown keys are ignored and missing/invalid values fall back to each
        option's default, so a partial or hand-edited save still loads cleanly.
        """
        for spec in OPTION_SPECS:
            if spec.key in self._spinboxes:
                self._spinboxes[spec.key].setValue(spec.coerce(options.get(spec.key)))

    def get_options(self) -> dict[str, str]:
        """Return the currently selected option values keyed by option key.

        Values are stringified to match the ``dict[str, str]`` shape of
        ``character.options`` and the ``character_options`` table.
        """
        return {key: str(spin.value()) for key, spin in self._spinboxes.items()}

    @property
    def point_buy_budget(self) -> int:
        """The point-buy budget currently selected in the dialog (DMG p169)."""
        return self._spinboxes[POINT_BUY_BUDGET].value()
