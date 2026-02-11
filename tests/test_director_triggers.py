"""Tests for Director trigger functions — should_reveal_new_region."""
from __future__ import annotations

import pytest

from text_rpg.systems.base import GameContext
from text_rpg.systems.director.triggers import should_reveal_new_region


class FakeLocationRepo:
    """Minimal stand-in for LocationRepo."""

    def __init__(self, locations: list[dict]):
        self._locations = locations

    def get_by_region(self, game_id: str, region_id: str) -> list[dict]:
        return [l for l in self._locations if l.get("region_id") == region_id]

    def get_all(self, game_id: str) -> list[dict]:
        return list(self._locations)


def _make_context(
    player_level: int = 1,
    region_id: str = "verdant_reach",
) -> GameContext:
    return GameContext(
        game_id="g1",
        character={"id": "c1", "level": player_level},
        location={"id": "loc1", "region_id": region_id},
        entities=[],
        turn_number=50,
        world_time=480,
    )


ALL_REGIONS = ["verdant_reach", "iron_coast", "ashen_highlands", "thornwild", "sunken_reach"]


class TestShouldRevealNewRegion:
    """Tests for the should_reveal_new_region trigger."""

    def test_low_level_player_does_not_trigger(self):
        """Player level 1 in a region with max 5 — too low."""
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": True}
            for i in range(6)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=1)
        assert not should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_high_level_but_low_exploration_does_not_trigger(self):
        """Player level 4 but only 2/10 locations visited."""
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": i < 2}
            for i in range(10)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=4)
        assert not should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_triggers_when_conditions_met(self):
        """Player level 4, 80% explored — should trigger."""
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": i < 8}
            for i in range(10)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=4)
        assert should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_level_5_triggers(self):
        """Player at exactly the region max (5) with 60% explored."""
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": i < 6}
            for i in range(10)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=5)
        assert should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_no_location_repo_returns_false(self):
        """Missing location repo should not crash."""
        ctx = _make_context(player_level=5)
        assert not should_reveal_new_region(ctx, {}, ALL_REGIONS)

    def test_no_locations_returns_false(self):
        """Empty region returns false."""
        repo = FakeLocationRepo([])
        ctx = _make_context(player_level=5)
        assert not should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_no_region_id_returns_false(self):
        """Location with no region_id returns false."""
        ctx = GameContext(
            game_id="g1",
            character={"id": "c1", "level": 5},
            location={"id": "loc1"},
            entities=[],
            turn_number=50,
            world_time=480,
        )
        repo = FakeLocationRepo([])
        assert not should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_all_regions_visited_still_triggers_for_generation(self):
        """When all content regions are visited, trigger for LLM generation."""
        # Make all 5 regions have visited locations
        locations = []
        for rid in ALL_REGIONS:
            for i in range(6):
                locations.append({
                    "id": f"{rid}_loc{i}",
                    "region_id": rid,
                    "visited": True,
                })
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=5)
        assert should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_exactly_60_pct_triggers(self):
        """60% exploration is the threshold — should trigger."""
        # 6 out of 10 = exactly 60%
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": i < 6}
            for i in range(10)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=4)
        assert should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)

    def test_59_pct_does_not_trigger(self):
        """59% exploration is below threshold."""
        # 59 out of 100 = 59%
        locations = [
            {"id": f"loc{i}", "region_id": "verdant_reach", "visited": i < 59}
            for i in range(100)
        ]
        repo = FakeLocationRepo(locations)
        ctx = _make_context(player_level=5)
        assert not should_reveal_new_region(ctx, {"location": repo}, ALL_REGIONS)
