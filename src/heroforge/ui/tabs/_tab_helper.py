"""Shared base/helpers for HeroForge-Anew tab widgets."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PyQt6.QtWidgets import QInputDialog, QWidget

logger = logging.getLogger(__name__)


def pick_from_catalog(
    parent: QWidget | None,
    title: str,
    label: str,
    options: Sequence[str],
) -> str | None:
    """Prompt the user to choose a name, returning it or ``None`` on cancel.

    When *options* is non-empty the user picks from a editable combo populated
    with the seeded catalogue (data-backed selection).  When no catalogue data
    is available the dialog degrades to a free-text entry so the tab remains
    usable on a fresh, unseeded checkout.  The returned string is stripped; an
    empty/blank result yields ``None``.
    """
    if options:
        choice, ok = QInputDialog.getItem(parent, title, label, list(options), 0, True)
    else:
        choice, ok = QInputDialog.getText(parent, title, label)
    if not ok:
        logger.debug("pick_from_catalog cancelled: title=%r", title)
        return None
    choice = choice.strip()
    return choice or None
