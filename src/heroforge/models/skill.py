"""Skill dataclass model for HeroForge-Anew."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    """A D&D 3.5 skill. References: PHB Chapter 4."""

    id: int | None = None
    name: str = ""
    key_ability: str = ""
    """One of STR, DEX, CON, INT, WIS, CHA."""
    trained_only: bool = False
    armor_check_penalty: bool = False
    description: str = ""
    synergies: list[tuple[str, str]] = field(default_factory=list)
    """List of ``(to_skill, condition)`` tuples provided by this skill."""
