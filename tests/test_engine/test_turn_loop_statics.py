"""Tests for static methods in src/text_rpg/engine/turn_loop.py."""
from __future__ import annotations

import pytest

from text_rpg.engine.turn_loop import TurnLoop


class TestAddItem:
    def test_new_item(self):
        items = []
        TurnLoop._add_item(items, "sword", 1)
        assert items == [{"item_id": "sword", "quantity": 1}]

    def test_stacking_existing(self):
        items = [{"item_id": "potion", "quantity": 2}]
        TurnLoop._add_item(items, "potion", 3)
        assert items == [{"item_id": "potion", "quantity": 5}]

    def test_add_zero_quantity(self):
        items = [{"item_id": "potion", "quantity": 2}]
        TurnLoop._add_item(items, "potion", 0)
        assert items[0]["quantity"] == 2

    def test_add_to_multiple_items(self):
        items = [{"item_id": "sword", "quantity": 1}, {"item_id": "potion", "quantity": 2}]
        TurnLoop._add_item(items, "shield", 1)
        assert len(items) == 3
        assert items[2]["item_id"] == "shield"


class TestRemoveItem:
    def test_single_item_removed(self):
        items = [{"item_id": "potion", "quantity": 1}]
        TurnLoop._remove_item(items, "potion")
        assert items == []

    def test_from_stack_decrement(self):
        items = [{"item_id": "potion", "quantity": 3}]
        TurnLoop._remove_item(items, "potion")
        assert items[0]["quantity"] == 2

    def test_not_found_unchanged(self):
        items = [{"item_id": "sword", "quantity": 1}]
        TurnLoop._remove_item(items, "shield")
        assert items == [{"item_id": "sword", "quantity": 1}]

    def test_empty_list(self):
        items = []
        TurnLoop._remove_item(items, "potion")
        assert items == []
