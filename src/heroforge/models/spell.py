"""Spell dataclass model for HeroForge-Anew."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Spell:
    """A D&D 3.5 spell. References: PHB Chapters 10-11."""

    id: int | None = None
    name: str = ""
    school: str = ""
    """One of the eight schools: Abjuration, Conjuration, Divination,
    Enchantment, Evocation, Illusion, Necromancy, Transmutation."""
    subschool: str = ""
    descriptor: str = ""
    components: str = ""
    """E.g. ``'V, S, M'``."""
    casting_time: str = ""
    range: str = ""
    target: str = ""
    duration: str = ""
    saving_throw: str = ""
    spell_resistance: str = ""
    description: str = ""
    source: str = ""
