"""Character dataclass model for HeroForge-Anew.

Represents a complete D&D 3.5 player character, including related data
that is loaded separately from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Character:
    """A D&D 3.5 player character.

    ``id`` is ``None`` for unsaved characters.  Related data (ability
    scores, class levels, feats, skills, equipment …) is stored as
    in-memory Python structures and persisted separately.
    """

    id: int | None = None
    name: str = ""
    player: str = ""
    campaign: str = ""
    alignment: str = ""
    deity: str = ""
    homeland: str = ""
    race: str = ""
    templates: list[str] = field(default_factory=list)
    gender: str = ""
    age: int = 0
    height: str = ""
    weight: str = ""
    eyes: str = ""
    hair: str = ""
    skin: str = ""
    experience: int = 0
    notes: str = ""

    # Related data loaded separately from join tables
    ability_scores: dict[str, int] = field(
        default_factory=lambda: {
            "STR": 10,
            "DEX": 10,
            "CON": 10,
            "INT": 10,
            "WIS": 10,
            "CHA": 10,
        }
    )
    classes: list[tuple[str, int]] = field(default_factory=list)
    """List of ``(class_name, level)`` tuples in the order they were taken."""
    feats: list[str] = field(default_factory=list)
    skills: dict[str, float] = field(default_factory=dict)
    buffs: list[str] = field(default_factory=list)
    equipment: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    languages: list[str] = field(default_factory=list)

    @property
    def total_level(self) -> int:
        """Sum of all class levels. PHB p21."""
        return sum(level for _, level in self.classes)
