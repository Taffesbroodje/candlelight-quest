"""Integration tests for trait system — input handler + fallback generator."""
from __future__ import annotations

import pytest

from text_rpg.cli.input_handler import InputHandler
from text_rpg.mechanics.trait_effects import FALLBACK_TRAITS, TIER_BUDGETS, validate_trait
from text_rpg.systems.director.trait_generator import _fallback_trait


class TestTraitInputPatterns:
    """Test that trait-related inputs classify correctly."""

    @pytest.fixture
    def handler(self):
        return InputHandler()

    @pytest.mark.parametrize("text", ["traits", "trait", "perks", "perk", "passives"])
    def test_traits_meta_command(self, handler, text):
        result = handler.classify(text)
        assert result["action_type"] == "traits"
        assert result["is_meta"] is True


class TestFallbackTraits:
    """Test that fallback traits are valid for their target tiers."""

    def test_fallback_tier_1_within_budget(self):
        for pattern, fallback in FALLBACK_TRAITS.items():
            trait = _fallback_trait(pattern, 1)
            assert trait is not None, f"Fallback for {pattern} returned None"
            valid, error = validate_trait(trait["effects"], 1)
            assert valid, f"Fallback for {pattern} invalid at tier 1: {error}"

    def test_fallback_tier_2_within_budget(self):
        for pattern in FALLBACK_TRAITS:
            trait = _fallback_trait(pattern, 2)
            assert trait is not None
            valid, error = validate_trait(trait["effects"], 2)
            assert valid, f"Fallback for {pattern} invalid at tier 2: {error}"

    def test_fallback_tier_3_within_budget(self):
        for pattern in FALLBACK_TRAITS:
            trait = _fallback_trait(pattern, 3)
            assert trait is not None
            valid, error = validate_trait(trait["effects"], 3)
            assert valid, f"Fallback for {pattern} invalid at tier 3: {error}"

    def test_fallback_has_required_fields(self):
        trait = _fallback_trait("explorer", 1)
        assert trait is not None
        assert "id" in trait
        assert "name" in trait
        assert "description" in trait
        assert "effects" in trait
        assert "tier" in trait
        assert "behavior_source" in trait
        assert trait["tier"] == 1
        assert trait["behavior_source"] == "explorer"

    def test_unknown_pattern_uses_first_fallback(self):
        trait = _fallback_trait("nonexistent_pattern", 1)
        assert trait is not None
        assert trait["behavior_source"] == "nonexistent_pattern"
