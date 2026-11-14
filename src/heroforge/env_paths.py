"""Resolve directory paths from environment-variable overrides.

Provides a single, reusable helper for the common pattern of "use this directory
unless an environment variable points somewhere else". The override value is
sanitised with :func:`heroforge.path_safety.contains_unsafe_path_char` before
use, so a value carrying control/format codes or emoji is rejected (with a
warning) and the caller's default is used instead — a malformed override
degrades gracefully rather than crashing startup.

The helper never creates the directory; callers decide whether (and when) to
``mkdir`` it, since a writable target should be created but a read-only source
should not.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from heroforge.path_safety import contains_unsafe_path_char

logger = logging.getLogger(__name__)


def dir_from_env(env_var: str, default: Path | None) -> Path | None:
    """Resolve a directory override from *env_var*, falling back to *default*.

    Returns ``Path(value)`` when *env_var* holds a usable path, otherwise
    *default* (which may be ``None`` to signal "no directory / use a downstream
    fallback"). The value is rejected — with a warning naming *env_var* — when it
    contains characters unsafe for a path; an unset or empty variable also yields
    *default*. The returned directory is **not** created.
    """
    raw = os.environ.get(env_var, "").strip()
    if raw and contains_unsafe_path_char(raw):
        logger.warning(
            "Ignoring %s: value contains a disallowed character; falling back "
            "to %s.",
            env_var,
            default,
        )
        raw = ""
    return Path(raw) if raw else default
