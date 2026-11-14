"""Shared logging configuration for HeroForge-Anew entry points.

Both the Qt application (:mod:`heroforge.app`) and the database seeder
(:mod:`heroforge.db.seed`) configure root logging the same way, so the logic
lives here as the single source of truth.
"""

from __future__ import annotations

import logging
import os


def configure_logging(fmt: str | None = None) -> None:
    """Configure root logging, honouring the ``LOG_LEVEL`` environment variable.

    Defaults to ``INFO``.  Set ``LOG_LEVEL=DEBUG`` (e.g. in ``.env`` for the QA
    container) to surface the per-row ``logger.debug`` detail behind warnings
    such as "skipped N source rows due to insert errors (see debug logs)".

    Args:
        fmt: Optional :mod:`logging` format string.  When ``None`` the
            standard-library default format is used.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.INFO
    # Only forward ``format`` when a string is supplied: ``basicConfig`` treats
    # an explicit ``format=None`` as "%(message)s", whereas omitting it falls
    # back to the richer default "%(levelname)s:%(name)s:%(message)s" (keeping
    # the "WARNING:heroforge…:" prefix).
    if fmt is None:
        logging.basicConfig(level=level)
    else:
        logging.basicConfig(level=level, format=fmt)
