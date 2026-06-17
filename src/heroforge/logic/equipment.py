"""Equipment and encumbrance calculations for HeroForge-Anew.

Reference: PHB p162 (Carrying Capacity), p123–126 (Equipment chapter).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

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


def _item_bonus_specs(item: dict) -> list[dict]:  # type: ignore[type-arg]
    """Return the list of bonus specs declared on an equipment *item*.

    An item may declare a single bonus via top-level ``target``/``bonus_type``/
    ``value`` keys, and/or a ``bonuses`` list of such dicts.  Items are treated
    as equipped by default; only items with ``equipped`` explicitly set to a
    falsey value contribute nothing.
    """
    if not item.get("equipped", True):
        return []
    specs: list[dict] = []  # type: ignore[type-arg]
    if item.get("target"):
        specs.append(item)
    extra = item.get("bonuses")
    if isinstance(extra, list):
        specs.extend(spec for spec in extra if isinstance(spec, dict))
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
        for spec in _item_bonus_specs(item):
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
) -> str:
    """Determine the encumbrance category for a character.

    Categories:
    - ``'Light'``:      total_weight ≤ light_max
    - ``'Medium'``:     light_max < total_weight ≤ medium_max
    - ``'Heavy'``:      medium_max < total_weight ≤ heavy_max (= 2 × medium_max)
    - ``'Overloaded'``: total_weight > heavy_max

    Reference: PHB p162.

    Args:
        total_weight: Character's carried weight in pounds.
        light_max:    Maximum weight for Light load.
        medium_max:   Maximum weight for Medium load.

    Returns:
        Encumbrance category string.
    """
    heavy_max = medium_max * 2
    if total_weight <= light_max:
        return "Light"
    if total_weight <= medium_max:
        return "Medium"
    if total_weight <= heavy_max:
        return "Heavy"
    return "Overloaded"


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
