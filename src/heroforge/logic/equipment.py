"""Equipment and encumbrance calculations for HeroForge-Anew.

Reference: PHB p162 (Carrying Capacity), p123–126 (Equipment chapter).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from heroforge.logic.buffs import buff_amount

# Ability keys recognised as magic-item bonus targets (PHB p9).
_ABILITY_KEYS: frozenset[str] = frozenset({"STR", "DEX", "CON", "INT", "WIS", "CHA"})

# Saving-throw target aliases → the short keys used by the derived-stat layer.
_SAVE_ALIASES: Mapping[str, str] = {
    "fort": "fort",
    "fortitude": "fort",
    "ref": "ref",
    "reflex": "ref",
    "will": "will",
}

# Bonus types that stack with themselves (and with everything else); every other
# named type is non-stacking, so only the single largest bonus of that type
# applies (PHB p150–151).  Penalties always stack regardless of type.
_STACKING_BONUS_TYPES: frozenset[str] = frozenset({"untyped", "dodge", "circumstance"})

# Default bonus for catalogue items whose bonus target and type are fixed by the
# item description (DMG chapter 7).  The workbook only computes these in VBA, so
# they are not seedable; the value is the item's lowest version and the user
# edits it in the Magic Equipment tab for stronger versions.  Keys are the
# seeded ``magic_equipment`` names, lower-cased.
_DEFAULT_ITEM_BONUSES: Mapping[str, tuple[str, str, int]] = {
    "gauntlets of ogre power": ("STR", "enhancement", 2),
    "belt of giant strength": ("STR", "enhancement", 4),
    "gloves of dexterity": ("DEX", "enhancement", 2),
    "amulet of health": ("CON", "enhancement", 2),
    "headband of intellect": ("INT", "enhancement", 2),
    "periapt of wisdom": ("WIS", "enhancement", 2),
    "cloak of charisma": ("CHA", "enhancement", 2),
    "cloak of resistance": ("Saves", "resistance", 1),
    "vest of resistance": ("Saves", "resistance", 1),
    # The Ring slot catalogue lists the ring of protection as "Protection".
    "protection": ("AC", "deflection", 1),
}


def default_item_bonuses(name: str) -> list[dict]:  # type: ignore[type-arg]
    """Return the default bonus specs for the catalogue item *name*.

    Returns an empty list for items without a fixed, well-known bonus.
    """
    default = _DEFAULT_ITEM_BONUSES.get(str(name).strip().lower())
    if default is None:
        return []
    target, bonus_type, value = default
    return [{"target": target, "bonus_type": bonus_type, "value": value}]


def aggregate_typed_bonuses(bonuses: Iterable[tuple[str, int]]) -> int:
    """Sum typed bonuses honouring D&D 3.5 stacking rules.

    Same-type bonuses do **not** stack — only the largest of each non-stacking
    type counts — except dodge, circumstance and untyped bonuses, which stack
    with everything.  Penalties (negative values) always stack.

    Reference: PHB p150–151 (bonus types and stacking).

    Args:
        bonuses: Iterable of ``(bonus_type, value)`` pairs.  An empty or unknown
                 type is treated as untyped.

    Returns:
        The aggregated bonus (may be negative).
    """
    typed_best: dict[str, int] = {}
    stacking_total = 0
    for raw_type, raw_value in bonuses:
        btype = str(raw_type).strip().lower() or "untyped"
        value = int(raw_value)
        if value < 0 or btype in _STACKING_BONUS_TYPES:
            stacking_total += value
        else:
            typed_best[btype] = max(typed_best.get(btype, 0), value)
    return stacking_total + sum(typed_best.values())


@dataclass(frozen=True)
class EquipmentBonuses:
    """Aggregated stat bonuses contributed by worn/equipped magic items.

    ``ability`` and ``saves`` are already aggregated per target honouring the
    non-stacking rules.  ``armor_class`` is left as a list of
    ``(bonus_type, value)`` pairs so it can be merged with the other AC sources
    (armor, shield, natural) and stacked across every source at once by
    :func:`heroforge.logic.combat.aggregate_armor_class`.
    """

    ability: Mapping[str, int] = field(default_factory=dict)
    armor_class: tuple[tuple[str, int], ...] = ()
    saves: Mapping[str, int] = field(default_factory=dict)


def _normalise_target(target: str) -> str:
    """Map a raw bonus *target* to a canonical key (ability/``AC``/save)."""
    text = str(target).strip()
    upper = text.upper()
    if upper in _ABILITY_KEYS:
        return upper
    if upper in {"AC", "ARMOR CLASS", "ARMOUR CLASS"}:
        return "AC"
    return _SAVE_ALIASES.get(text.lower(), "")


def item_bonus_specs(item: dict) -> list[dict]:  # type: ignore[type-arg]
    """Return the list of bonus specs declared on an equipment *item*.

    An item may declare a single bonus via top-level ``target``/``bonus_type``/
    ``value`` keys, and/or a ``bonuses`` list of such dicts.  Items are treated
    as equipped by default; only items with ``equipped`` explicitly set to a
    falsey value contribute nothing.
    """
    if not item.get("equipped", True):
        return []
    return declared_bonus_specs(item)


def declared_bonus_specs(item: dict) -> list[dict]:  # type: ignore[type-arg]
    """Return every bonus spec on *item*, equipped or not, in a uniform shape.

    Collects the top-level ``target``/``bonus_type``/``value`` spec and the
    ``bonuses`` list (see :func:`item_bonus_specs`) as
    ``{"target", "bonus_type", "value"}`` dicts with an ``int`` value.  Specs
    with no target are dropped, and an unusable value (e.g. text from a
    hand-edited save) becomes ``0``.  Used to persist an item's bonuses.
    """
    raw: list[dict] = []  # type: ignore[type-arg]
    if item.get("target"):
        raw.append(item)
    extra = item.get("bonuses")
    if isinstance(extra, list):
        raw.extend(spec for spec in extra if isinstance(spec, dict))
    specs: list[dict] = []  # type: ignore[type-arg]
    for spec in raw:
        target = str(spec.get("target") or "").strip()
        if not target:
            continue
        specs.append(
            {
                "target": target,
                "bonus_type": str(spec.get("bonus_type") or "").strip(),
                "value": buff_amount(spec.get("value")),
            }
        )
    return specs


def equipment_bonuses(
    items: Iterable[dict],  # type: ignore[type-arg]
) -> EquipmentBonuses:
    """Aggregate the stat bonuses granted by *items*.

    Each item may declare bonuses with ``target`` (an ability key such as
    ``"DEX"``, ``"AC"``, or a save name), ``bonus_type`` (e.g. ``"enhancement"``,
    ``"deflection"``, ``"resistance"``) and ``value`` (an integer).  Ability and
    save bonuses are aggregated per target with the non-stacking rules; AC
    bonuses are returned untouched so they can be stacked alongside the other AC
    sources.

    Reference: PHB p150–151 (bonus types and stacking).
    """
    ability_pairs: dict[str, list[tuple[str, int]]] = {}
    save_pairs: dict[str, list[tuple[str, int]]] = {}
    ac_bonuses: list[tuple[str, int]] = []
    for item in items:
        for spec in item_bonus_specs(item):
            key = _normalise_target(spec.get("target", ""))
            if not key:
                continue
            try:
                value = int(spec.get("value", 0))
            except (TypeError, ValueError):
                continue
            if value == 0:
                continue
            btype = str(spec.get("bonus_type", "") or "").strip()
            if key in _ABILITY_KEYS:
                ability_pairs.setdefault(key, []).append((btype, value))
            elif key == "AC":
                ac_bonuses.append((btype or "untyped", value))
            else:  # saving throw
                save_pairs.setdefault(key, []).append((btype, value))
    ability = {k: aggregate_typed_bonuses(v) for k, v in ability_pairs.items()}
    saves = {k: aggregate_typed_bonuses(v) for k, v in save_pairs.items()}
    return EquipmentBonuses(
        ability=ability,
        armor_class=tuple(ac_bonuses),
        saves=saves,
    )


def resolve_item_weight(
    item: dict,  # type: ignore[type-arg]
    catalog: Mapping[str, float] | None = None,
) -> float:
    """Return a single item's unit weight, resolving from *catalog* if needed.

    The item's own ``weight`` is used when present and non-zero; otherwise the
    weight is looked up in *catalog* (a mapping of item name → unit weight, e.g.
    the seeded ``magic_equipment`` catalogue) so equipment selected from the
    database still contributes its weight even if the stored entry omitted it.
    """
    try:
        own = float(item.get("weight", 0.0) or 0.0)
    except (TypeError, ValueError):
        own = 0.0
    if own:
        return own
    if catalog:
        name = str(item.get("item_name") or item.get("name") or "")
        return float(catalog.get(name, 0.0))
    return 0.0


def carried_weight(
    items: Iterable[dict],  # type: ignore[type-arg]
    catalog: Mapping[str, float] | None = None,
) -> float:
    """Total carried weight of *items*, resolving weights from *catalog*.

    Each item's weight is multiplied by its ``quantity`` (default 1).  Weights
    missing from an item entry are resolved from *catalog* by item name, so
    magic equipment chosen from the seeded catalogue contributes its weight to
    encumbrance.

    Reference: PHB p162.
    """
    total = 0.0
    for item in items:
        try:
            qty = float(item.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 1.0
        total += resolve_item_weight(item, catalog) * qty
    return total


def total_weight(items: list[dict]) -> float:  # type: ignore[type-arg]
    """Calculate the total carried weight of a list of items.

    Each item dict should have ``'weight'`` (float, per unit) and
    ``'quantity'`` (int, defaults to 1) keys.

    Reference: PHB p162.

    Args:
        items: List of equipment item dicts.

    Returns:
        Total weight in pounds.
    """
    weight = 0.0
    for item in items:
        qty = float(item.get("quantity", 1))
        w = float(item.get("weight", 0.0))
        weight += w * qty
    return weight


def encumbrance_category(
    total_weight: float,
    light_max: int,
    medium_max: int,
    heavy_max: int | None = None,
) -> str:
    """Determine the encumbrance category for a character.

    Categories:
    - ``'Light'``:      total_weight ≤ light_max
    - ``'Medium'``:     light_max < total_weight ≤ medium_max
    - ``'Heavy'``:      medium_max < total_weight ≤ heavy_max
    - ``'Overloaded'``: total_weight > heavy_max

    Reference: PHB p162.

    Args:
        total_weight: Character's carried weight in pounds.
        light_max:    Maximum weight for Light load.
        medium_max:   Maximum weight for Medium load.
        heavy_max:    Maximum weight for Heavy load, e.g. the third value of
                      :func:`heroforge.logic.combat.carrying_capacity`.  When
                      omitted it falls back to ``2 × medium_max``.

    Returns:
        Encumbrance category string.
    """
    if heavy_max is None:
        heavy_max = medium_max * 2
    if total_weight <= light_max:
        return "Light"
    if total_weight <= medium_max:
        return "Medium"
    if total_weight <= heavy_max:
        return "Heavy"
    return "Overloaded"


# Max Dex cap and check penalty imposed by each load (PHB p162, Table 9-2).
# Overloaded uses the heavy-load figures, as the workbook does (Armor!R12/R14).
_LOAD_EFFECTS: Mapping[str, tuple[int | None, int]] = {
    "Light": (None, 0),
    "Medium": (3, -3),
    "Heavy": (1, -6),
    "Overloaded": (1, -6),
}


def load_effects(category: str) -> tuple[int | None, int]:
    """Return ``(max_dex, check_penalty)`` for the load *category*.

    ``max_dex`` is ``None`` when the load does not cap Dexterity.  These do not
    stack with armor: the stricter Max Dex and the worse check penalty apply.

    Reference: PHB p162.
    """
    return _LOAD_EFFECTS.get(category, (None, 0))


#: Base land speed (feet) of a Medium humanoid, used when the race records none.
DEFAULT_LAND_SPEED = 30

#: Races whose speed is not reduced by medium/heavy armor or load (PHB p14),
#: matching the workbook's exemption list in ``Armor!R1``.
SPEED_UNENCUMBERED_RACES: frozenset[str] = frozenset({"dwarf", "wildren"})


def speed_ignores_encumbrance(race: str | None) -> bool:
    """Return ``True`` when *race* keeps its full speed in armor or under load.

    Only the base race (the part before any ``", subrace"``) is compared, so
    ``"Dwarf, Hill"`` is exempt too.  Reference: PHB p14 (Dwarf).
    """
    base = (race or "").split(",", 1)[0].strip().lower()
    return base in SPEED_UNENCUMBERED_RACES


def reduced_speed(base_speed: int) -> int:
    """Return *base_speed* reduced for medium/heavy armor or load.

    Speed drops to two-thirds, rounded up to the next 5 ft. step: 20 ft. → 15,
    30 → 20, 40 → 30 (PHB p162 Table 9-2; workbook ``Armor!R1``).
    """
    base = max(0, int(base_speed))
    return -(-2 * base // 15) * 5


def encumbered_speed(
    base_speed: int,
    armor_type: str | None,
    load: str,
    *,
    ignore_encumbrance: bool = False,
) -> tuple[int, int]:
    """Return ``(speed, run_multiplier)`` after worn armor and carried load.

    Medium or heavy body armor, or a load above light, reduces *base_speed*
    with :func:`reduced_speed` unless *ignore_encumbrance* is set (see
    :func:`speed_ignores_encumbrance`).  The run multiplier is ×4, or ×3 in
    heavy armor or under a heavy load; the dwarf exemption does not change it.

    Reference: PHB p122–123 (armor and speed), p162 Table 9-2 (load); workbook
    ``Armor!R1`` (speed) and ``Armor!R6`` (run multiplier).

    Args:
        base_speed:  Base land speed in feet (usually the race's).
        armor_type:  Type of the worn body armor (``"Light"``, ``"Medium"``,
                     ``"Heavy"``), or ``None`` when none is worn.  Any other
                     value is treated as not slowing the wearer.
        load:        Load category from :func:`encumbrance_category`.
        ignore_encumbrance: Keep the full speed regardless of armor and load.
    """
    armor = (armor_type or "").strip().lower()
    slowed_by_armor = armor in ("medium", "heavy")
    slowed_by_load = load in ("Medium", "Heavy", "Overloaded")
    speed = max(0, int(base_speed))
    if (slowed_by_armor or slowed_by_load) and not ignore_encumbrance:
        speed = reduced_speed(speed)
    run_multiplier = 3 if armor == "heavy" or load in ("Heavy", "Overloaded") else 4
    return speed, run_multiplier


def armor_check_penalty(armor_acp: int, shield_acp: int) -> int:
    """Calculate combined armor check penalty from armor and shield.

    Both values are typically negative in the DB (negative impact on skill
    checks).  The function returns the sum.

    Reference: PHB p123.

    Args:
        armor_acp:  Armor's check penalty (e.g. -6 for Full Plate).
        shield_acp: Shield's check penalty (e.g. -1 for Light Shield).

    Returns:
        Combined armor check penalty (sum of both, typically ≤ 0).
    """
    return armor_acp + shield_acp


def enhancement_bonus(base_item: dict) -> int:  # type: ignore[type-arg]
    """Return the enhancement bonus of an item.

    Reads the ``'enhancement_bonus'`` key from the item dict; defaults to 0.

    Reference: PHB p217 (magic item descriptions).

    Args:
        base_item: Item dict (may or may not contain ``'enhancement_bonus'``).

    Returns:
        Enhancement bonus as an integer.
    """
    return int(base_item.get("enhancement_bonus", 0))
