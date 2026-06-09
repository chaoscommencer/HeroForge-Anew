"""Language rules for HeroForge-Anew.

Reference: PHB p82 (Speak Language) and the racial language tables in PHB
Chapter 2.  A character automatically knows Common plus their racial
language(s); a positive Intelligence modifier grants that many *bonus*
languages, chosen from any language on the list.
"""

from __future__ import annotations

import re

from heroforge.logic.ability_scores import ability_modifier

# Automatic languages granted by race (PHB Chapter 2).  Every entry implicitly
# includes Common.  Keys are matched case-insensitively against the whole words
# of the character's race so subtype prefixes (e.g. "Mountain Dwarf") still
# resolve to their base race entry via a longest match in
# :func:`automatic_languages` without matching incidental substrings.
_RACIAL_LANGUAGES: dict[str, tuple[str, ...]] = {
    "human": (),
    "dwarf": ("Dwarven",),
    "elf": ("Elven",),
    "gnome": ("Gnome",),
    "half-elf": ("Elven",),
    "half-orc": ("Orc",),
    "halfling": ("Halfling",),
}


def automatic_languages(race: str) -> list[str]:
    """Return the languages a character of *race* knows automatically.

    Always includes Common.  Unknown or empty races yield just ``["Common"]``
    so the function degrades gracefully for homebrew races.
    """
    result = ["Common"]
    key = (race or "").strip().lower()
    racial: tuple[str, ...] = ()
    if key in _RACIAL_LANGUAGES:
        racial = _RACIAL_LANGUAGES[key]
    else:
        # Whole-word, longest match so "Mountain Dwarf"/"Wood Elf" resolve while
        # incidental substrings (e.g. "elf" inside "selfish") do not.
        words = set(re.findall(r"[a-z]+", key))
        best = ""
        for name in _RACIAL_LANGUAGES:
            name_words = set(re.findall(r"[a-z]+", name))
            if name_words <= words and len(name) > len(best):
                best = name
        if best:
            racial = _RACIAL_LANGUAGES[best]
    for lang in racial:
        if lang not in result:
            result.append(lang)
    return result


def bonus_language_slots(int_score: int) -> int:
    """Return the number of bonus languages granted by an Intelligence score.

    Equals the Intelligence modifier when positive, otherwise ``0``.
    Reference: PHB p82.
    """
    return max(0, ability_modifier(int_score))
