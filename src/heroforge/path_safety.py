"""Reusable validation for externally supplied filesystem paths.

Centralises the rejection of characters that have no place in a real directory
or file name and that can either crash path handling or spoof it. Use this at
any boundary where a path comes from outside the application — environment
variables, CLI arguments, configuration files, etc. — so the same policy is
applied consistently rather than re-implemented per call site.

The policy rejects:

* **Unicode category ``C*`` (Other)** — the NUL byte, bidirectional
  "reverse direction" overrides (e.g. ``U+202E``) and zero-width joiners used in
  Trojan-Source-style attacks, plus other control/format codes. The NUL byte in
  particular would otherwise raise an opaque ``ValueError`` from later path
  operations.
* **Emoji and pictographic symbols** (see :data:`EMOJI_RANGES`) — these are not
  category ``C`` (so the control/format check misses them) yet are a common
  spoofing/garbage vector.

Ordinary letters, digits and punctuation from any script remain allowed, so
legitimate non-ASCII names (e.g. ``/home/josé/data``) still pass.

The check deliberately returns only a boolean: the offending character is never
returned or logged, since it may itself be a control/format code (e.g. a
bidirectional override) that would corrupt terminal output or log files if
echoed back.
"""

from __future__ import annotations

import unicodedata

# Unicode code-point ranges covering emoji and pictographic symbols.
EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),  # mahjong/dominoes/cards + emoji & supplemental symbols
    (0x2600, 0x27BF),  # miscellaneous symbols and dingbats
    (0xFE00, 0xFE0F),  # variation selectors (emoji-presentation selectors)
    (0x1F1E6, 0x1F1FF),  # regional indicator symbols (flag sequences)
)


def contains_unsafe_path_char(value: str) -> bool:
    """Return ``True`` if *value* contains any character unsafe for a path.

    A return value of ``False`` means every character is acceptable per the
    policy described in the module docstring. The offending character is
    intentionally not returned, so callers cannot inadvertently echo a
    control/format code into a terminal or log.
    """
    for ch in value:
        if unicodedata.category(ch).startswith("C"):
            return True
        code_point = ord(ch)
        if any(low <= code_point <= high for low, high in EMOJI_RANGES):
            return True
    return False
