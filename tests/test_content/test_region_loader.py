"""Tests for region content loading."""
from __future__ import annotations

import pytest

from text_rpg.content.loader import load_all_regions, load_region


class TestLoadAllRegions:
    """Tests for load_all_regions function."""

    def test_loads_all_regions(self):
        regions = load_all_regions()
        assert len(regions) >= 5
        assert "verdant_reach" in regions
        assert "iron_coast" in regions
        assert "ashen_highlands" in regions
        assert "thornwild" in regions
        assert "sunken_reach" in regions

    def test_region_has_required_fields(self):
        regions = load_all_regions()
        for region_id, region in regions.items():
            assert region["id"] == region_id
            assert "name" in region
            assert "description" in region
            assert "level_range_min" in region
            assert "level_range_max" in region

    def test_level_ranges_valid(self):
        regions = load_all_regions()
        for region_id, region in regions.items():
            assert region["level_range_min"] >= 1
            assert region["level_range_max"] >= region["level_range_min"]
            assert region["level_range_max"] <= 20

    def test_region_has_climate(self):
        regions = load_all_regions()
        for region_id, region in regions.items():
            assert "climate" in region


class TestLoadRegion:
    """Tests for full region loading with locations/npcs."""

    def test_verdant_reach_has_locations(self):
        region = load_region("verdant_reach")
        assert region["id"] == "verdant_reach"
        assert len(region["locations"]) > 0

    def test_verdant_reach_has_npcs(self):
        region = load_region("verdant_reach")
        assert "npcs" in region
        assert len(region["npcs"]) > 0

    def test_all_regions_loadable(self):
        regions = load_all_regions()
        for region_id in regions:
            region = load_region(region_id)
            assert region["id"] == region_id
            assert "locations" in region
