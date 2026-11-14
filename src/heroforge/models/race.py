"""Race dataclass model for HeroForge-Anew."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Race:
    """A D&D 3.5 playable race. References: PHB Chapter 2, MM appendix."""

    id: int | None = None
    name: str = ""
    size: str = "Medium"
    type: str = "Humanoid"
    subtype: str = ""
    base_land_speed: int = 30
    base_fly_speed: int = 0
    base_swim_speed: int = 0
    base_climb_speed: int = 0
    base_burrow_speed: int = 0
    darkvision: int = 0
    low_light_vision: int = 0
    natural_armor: int = 0
    str_adj: int = 0
    dex_adj: int = 0
    con_adj: int = 0
    int_adj: int = 0
    wis_adj: int = 0
    cha_adj: int = 0
    level_adjustment: int = 0
    favored_class: str = ""
    source: str = ""
    abilities: list[str] = field(default_factory=list)
    """Names of special racial abilities (loaded from racial_abilities table)."""
