"""Feat dataclass model for HeroForge-Anew."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Feat:
    """A D&D 3.5 feat. References: PHB Chapter 5."""

    id: int | None = None
    name: str = ""
    type: str = ""
    """E.g. ``'General'``, ``'Fighter'``, ``'Metamagic'``, ``'Item Creation'``."""
    description: str = ""
    benefit: str = ""
    special: str = ""
    source: str = ""
    prerequisites: list[str] = field(default_factory=list)
    """Raw prerequisite strings as stored in ``feat_prerequisites``."""
