"""Template dataclass model for HeroForge-Anew."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Template:
    """A D&D 3.5 creature template. Reference: MM appendix (templates).

    Templates are layered on top of a base race/creature.  Their ability
    adjustments and level adjustment stack additively with the base race and
    with any other applied templates (see ``Template Info`` workbook sheet).
    """

    id: int | None = None
    name: str = ""
    cr_adjustment: float = 0.0
    level_adjustment: int = 0
    type_change: str = ""
    subtype_added: str = ""
    str_adj: int = 0
    dex_adj: int = 0
    con_adj: int = 0
    int_adj: int = 0
    wis_adj: int = 0
    cha_adj: int = 0
    source: str = ""
