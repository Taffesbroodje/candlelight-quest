"""Tests for src/text_rpg/mechanics/death.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.death import (
    calculate_death_penalty,
    find_safe_location,
    get_weakened_condition,
)


class TestCalculateDeathPenalty:
    @pytest.mark.parametrize("gold, expected_loss", [
        (0, 0), (1, 0), (3, 0), (4, 1), (7, 1),
        (100, 25), (1000, 250),
    ])
    def test_gold_loss(self, gold, expected_loss):
        result = calculate_death_penalty(gold)
        assert result["gold_lost"] == expected_loss


class TestGetWeakenedCondition:
    def test_structure(self):
        cond = get_weakened_condition()
        assert cond["name"] == "weakened"
        assert cond["penalty"] == -2
        assert cond["duration_turns"] == 5
        assert cond["turns_remaining"] == 5
        assert "description" in cond


class TestFindSafeLocation:
    def test_prefers_settlements(self):
        locs = [
            {"id": "forest", "visited": True, "location_type": "wilderness"},
            {"id": "town", "visited": True, "location_type": "town"},
        ]
        assert find_safe_location(locs) == "town"

    def test_falls_back_to_visited(self):
        locs = [
            {"id": "forest", "visited": True, "location_type": "wilderness"},
            {"id": "cave", "visited": True, "location_type": "dungeon"},
        ]
        assert find_safe_location(locs) == "forest"

    def test_no_visited_returns_none(self):
        locs = [
            {"id": "forest", "visited": False, "location_type": "wilderness"},
        ]
        assert find_safe_location(locs) is None

    def test_empty_returns_none(self):
        assert find_safe_location([]) is None

    def test_name_based_detection(self):
        locs = [
            {"id": "small_village", "visited": True, "name": "Small Village", "location_type": "area"},
        ]
        assert find_safe_location(locs) == "small_village"

    def test_unvisited_settlement_skipped(self):
        locs = [
            {"id": "town", "visited": False, "location_type": "town"},
            {"id": "road", "visited": True, "location_type": "road"},
        ]
        assert find_safe_location(locs) == "road"

    def test_settlement_type_variant(self):
        locs = [
            {"id": "city1", "visited": True, "location_type": "city"},
        ]
        assert find_safe_location(locs) == "city1"

    def test_village_type(self):
        locs = [
            {"id": "v1", "visited": True, "location_type": "village"},
        ]
        assert find_safe_location(locs) == "v1"
