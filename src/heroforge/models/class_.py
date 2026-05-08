"""Class dataclass model for HeroForge-Anew.

Note: the file is named ``class_.py`` to avoid shadowing the Python
built-in ``class`` keyword.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Class:
    """A D&D 3.5 character class (base or prestige). References: PHB Chapter 3."""

    id: int | None = None
    name: str = ""
    is_prestige: bool = False
    hit_die: int = 8
    bab_progression: str = "medium"
    """One of ``'fast'``, ``'medium'``, or ``'slow'``."""
    fort_progression: str = "poor"
    """One of ``'good'`` or ``'poor'``."""
    ref_progression: str = "poor"
    will_progression: str = "poor"
    skill_points_per_level: int = 2
    source: str = ""
    class_skills: list[str] = field(default_factory=list)
    """Skill names that are class skills for this class."""
    abilities: list[tuple[int, str]] = field(default_factory=list)
    """``(level, ability_name)`` pairs granted by this class."""
    weapon_armor_proficiencies: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    """Only populated for prestige classes."""
