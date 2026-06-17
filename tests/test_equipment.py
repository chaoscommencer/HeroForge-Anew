"""Tests for heroforge.logic.equipment (magic-item bonuses and encumbrance)."""

from __future__ import annotations

from heroforge.logic.equipment import (
    aggregate_typed_bonuses,
    armor_check_penalty,
    carried_weight,
    encumbrance_category,
    equipment_bonuses,
    resolve_item_weight,
    total_weight,
)


class TestTypedStacking:
    def test_same_type_keeps_only_largest(self) -> None:
        assert aggregate_typed_bonuses([("enhancement", 2), ("enhancement", 4)]) == 4

    def test_different_types_stack(self) -> None:
        assert aggregate_typed_bonuses([("deflection", 2), ("luck", 1)]) == 3

    def test_untyped_and_dodge_stack(self) -> None:
        assert aggregate_typed_bonuses([("untyped", 1), ("dodge", 1), ("", 1)]) == 3

    def test_penalties_always_stack(self) -> None:
        assert aggregate_typed_bonuses([("enhancement", 4), ("enhancement", -1)]) == 3


class TestEquipmentBonuses:
    def test_ability_enhancement_does_not_stack(self) -> None:
        items = [
            {
                "item_name": "Gloves of Dexterity +4",
                "target": "DEX",
                "bonus_type": "enhancement",
                "value": 4,
                "equipped": 1,
            },
            {
                "item_name": "Lesser Dex Item",
                "target": "DEX",
                "bonus_type": "enhancement",
                "value": 2,
                "equipped": 1,
            },
        ]
        result = equipment_bonuses(items)
        assert result.ability == {"DEX": 4}

    def test_unequipped_item_is_ignored(self) -> None:
        items = [
            {
                "item_name": "Amulet of Health +6",
                "target": "CON",
                "bonus_type": "enhancement",
                "value": 6,
                "equipped": 0,
            }
        ]
        assert equipment_bonuses(items).ability == {}

    def test_ac_bonuses_passed_through_with_type(self) -> None:
        items = [
            {
                "item_name": "Ring of Protection +2",
                "target": "AC",
                "bonus_type": "deflection",
                "value": 2,
                "equipped": 1,
            }
        ]
        assert equipment_bonuses(items).armor_class == (("deflection", 2),)

    def test_save_bonuses_aggregated_by_short_key(self) -> None:
        items = [
            {
                "item_name": "Cloak of Resistance +3",
                "target": "Fortitude",
                "bonus_type": "resistance",
                "value": 3,
                "equipped": 1,
            },
            {
                "item_name": "Cloak of Resistance +3",
                "target": "Reflex",
                "bonus_type": "resistance",
                "value": 3,
                "equipped": 1,
            },
        ]
        result = equipment_bonuses(items)
        assert result.saves == {"fort": 3, "ref": 3}

    def test_multiple_bonuses_per_item(self) -> None:
        items = [
            {
                "item_name": "Belt of Magnificence",
                "equipped": 1,
                "bonuses": [
                    {"target": "STR", "bonus_type": "enhancement", "value": 6},
                    {"target": "CON", "bonus_type": "enhancement", "value": 6},
                ],
            }
        ]
        result = equipment_bonuses(items)
        assert result.ability == {"STR": 6, "CON": 6}

    def test_zero_and_unknown_targets_ignored(self) -> None:
        items = [
            {"item_name": "Junk", "target": "DEX", "value": 0, "equipped": 1},
            {"item_name": "Junk2", "target": "SPEED", "value": 5, "equipped": 1},
        ]
        result = equipment_bonuses(items)
        assert result.ability == {}
        assert result.armor_class == ()
        assert result.saves == {}


class TestEncumbranceIntegration:
    def test_resolve_weight_prefers_entry_then_catalog(self) -> None:
        catalog = {"Gauntlets of ogre power": 2.0}
        entry = {"item_name": "Gauntlets of ogre power", "weight": 0}
        assert resolve_item_weight(entry, catalog) == 2.0
        explicit = {"item_name": "Custom", "weight": 5}
        assert resolve_item_weight(explicit, catalog) == 5.0

    def test_carried_weight_resolves_from_catalog(self) -> None:
        catalog = {"Heavy Helm": 10.0}
        items = [
            {"item_name": "Heavy Helm", "quantity": 1, "weight": 0},
            {"item_name": "Two Helms", "quantity": 2, "weight": 3},
        ]
        assert carried_weight(items, catalog) == 16.0

    def test_magic_equipment_weight_changes_encumbrance_category(self) -> None:
        # A medium-STR character (light load 33 lb) carrying a heavy item.
        catalog = {"Anvil Boots": 40.0}
        items = [{"item_name": "Anvil Boots", "quantity": 1, "weight": 0}]
        load = carried_weight(items, catalog)
        assert load == 40.0
        assert encumbrance_category(load, light_max=33, medium_max=66) == "Medium"
        # Without the catalogue weight the load would read as zero (Light).
        assert (
            encumbrance_category(total_weight(items), light_max=33, medium_max=66)
            == "Light"
        )


def test_armor_check_penalty_still_sums() -> None:
    assert armor_check_penalty(-6, -1) == -7
