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
    hit_points: int | None = None
    """Manual maximum-HP override.  ``None`` means HP is auto-calculated from
    class Hit Dice and the Constitution modifier (Stats & Character Details
    tab); set to an integer to override that computed value."""

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
    buffs: list[dict[str, str]] = field(default_factory=list)
    """Active buffs, each ``{"id": str, "name": str}`` where *id* is a UUID."""
    equipment: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    languages: list[str] = field(default_factory=list)
    spells_known: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Spells known, each ``{class_name, spell_level, spell_name}``."""
    spells_prepared: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Spells prepared, each ``{class_name, spell_level, spell_name}``."""
    soulmelds: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Soulmelds shaped, each ``{soulmeld_name, chakra_bound, essentia_invested}``."""
    maneuvers: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Martial maneuvers and stances, each ``{maneuver_name, readied}``."""
    grafts: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Grafts attached, each ``{graft_name, body_slot, notes}``."""
    traits: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Traits and flaws, each ``{trait_name, is_flaw}``."""
    variants: list[str | dict[str, str | None]] = field(default_factory=list)
    """Selected class/racial variants in order.

    A variant may be a legacy plain string (variant name only) or a
    structured mapping ``{variant_name, class_name, notes}``.
    """
    domains: list[str] = field(default_factory=list)
    """Chosen cleric (etc.) domains, in slot order."""
    vestiges: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Binder vestiges bound, each ``{vestige_name, level, bound}``."""
    marshal_auras: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Marshal auras known, each ``{aura_name, aura_type, active}``."""
    skill_tricks: list[str] = field(default_factory=list)
    """Selected skill tricks, in the order chosen."""
    psionic_powers: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Psionic powers known, each ``{class_name, power_level, power_name}``."""
    companions: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Animal companions/familiars, each ``{companion_type, name, creature, notes}``."""
    options: dict[str, str] = field(default_factory=dict)
    """Build / house-rule option toggles (e.g. ``{"Gestalt": "true"}``)."""
    wealth: dict[str, float] = field(default_factory=dict)
    """Coins and valuables by kind (``platinum``/``gold``/``silver``/``copper``/…)."""
    attacks: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Configured weapon attacks, each ``{weapon_name, attack_bonus, damage,
    critical, range_increment, damage_type, ammunition, notes}``."""
    enhancements: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Manual stat enhancements/adjustments, each
    ``{target, bonus_type, value, notes}``."""
    custom_content: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Homebrew definitions, each ``{content_type, name, definition}``;
    ``definition`` is a JSON string."""
    custom_armor: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """User-defined armor/shield entries not present in the game catalogue,
    each ``{name, type, ac_bonus, max_dex_bonus, check_penalty,
    arcane_spell_failure, weight}``."""
    custom_weapons: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """User-defined weapon entries, each ``{name, category, damage, critical,
    range_increment, damage_type, weight}``."""
    custom_items: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """User-defined magic-item entries, each ``{name, slot, description,
    weight}``."""
    lg_records: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Living Greyhawk records, each ``{record_type, event_date, description,
    gp_change, xp_change, notes}``."""
    game_log: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    """Timestamped free-text log entries, each ``{timestamp, content}``."""

    @property
    def total_level(self) -> int:
        """Sum of all class levels. PHB p21."""
        return sum(level for _, level in self.classes)
