"""Build / house-rule option definitions for HeroForge-Anew.

Mirrors the workbook's *Options* sheet (``docs/conversion-plan.md`` §11.2).
Each option is described once, declaratively, by an :class:`OptionSpec` so that
the :class:`~heroforge.ui.dialogs.options.OptionsDialog` can build its widgets,
the :class:`~heroforge.ui.main_window.CharacterModel` can read typed values, and
new options can be added in a single place without touching the dialog or the
persistence layer.

Option values are stored on :class:`~heroforge.models.character.Character` in the
``options`` mapping (``dict[str, str]``), which is already persisted to ``.hfc``
save files via :mod:`heroforge.db.character_repo`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Canonical option keys (stored verbatim in ``character.options``).
POINT_BUY_BUDGET = "point_buy_budget"


@dataclass(frozen=True)
class OptionSpec:
    """Declarative description of a single integer build option.

    Attributes:
        key: Stable identifier stored in ``character.options``.
        label: Human-readable label shown in the Options dialog.
        default: Value used when the option is unset or malformed.
        minimum: Inclusive lower bound (also clamps stored values).
        maximum: Inclusive upper bound (also clamps stored values).
    """

    key: str
    label: str
    default: int
    minimum: int
    maximum: int

    def coerce(self, value: object) -> int:
        """Return *value* coerced to an ``int`` and clamped to this spec's range.

        Falls back to :attr:`default` when *value* is missing or cannot be
        interpreted as an integer, so a corrupt or hand-edited save never
        produces an out-of-range or non-numeric option.
        """
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return self.default
        return max(self.minimum, min(self.maximum, number))


# Registry of every supported option. Add new options here only.
OPTION_SPECS: tuple[OptionSpec, ...] = (
    OptionSpec(
        key=POINT_BUY_BUDGET,
        label="Point-Buy Budget:",
        default=25,
        minimum=15,
        maximum=40,
    ),
)

OPTION_SPECS_BY_KEY: dict[str, OptionSpec] = {spec.key: spec for spec in OPTION_SPECS}


def default_options() -> dict[str, str]:
    """Return every option at its default value, keyed by option key."""
    return {spec.key: str(spec.default) for spec in OPTION_SPECS}


def get_int_option(options: Mapping[str, object], key: str) -> int:
    """Read a single integer option, coerced and clamped to its spec.

    Args:
        options: A ``character.options``-style mapping of stored values.
        key: One of the keys in :data:`OPTION_SPECS_BY_KEY`.

    Returns:
        The stored value coerced to ``int`` and clamped to the option's range,
        or the option's default when unset/invalid.

    Raises:
        KeyError: If *key* is not a registered option.
    """
    spec = OPTION_SPECS_BY_KEY[key]
    return spec.coerce(options.get(key))


def point_buy_budget(options: Mapping[str, object]) -> int:
    """Return the configured point-buy budget (DMG p169).

    Convenience wrapper over :func:`get_int_option` for the most frequently
    consulted option. Defaults to 25 points (the standard campaign budget) when
    unset.
    """
    return get_int_option(options, POINT_BUY_BUDGET)
