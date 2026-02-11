"""Tests for trait effects — validation, cost calculation, and application."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.trait_effects import (
    FALLBACK_TRAITS,
    TIER_BUDGETS,
    TRAIT_EFFECTS,
    apply_trait_effects,
    format_effect_description,
    get_effect_cost,
    total_effect_cost,
    validate_trait,
)


class TestValidateTrait:
    """Tests for validate_trait function."""

    def test_valid_tier_1_single_effect(self):
        effects = [{"type": "skill_bonus", "params": {"skill": "stealth"}}]
        valid, error = validate_trait(effects, 1)
        assert valid
        assert error == ""

    def test_valid_tier_1_two_cheap_effects(self):
        effects = [
            {"type": "speed_bonus", "params": {}},
            {"type": "darkvision", "params": {}},
        ]
        valid, error = validate_trait(effects, 1)
        assert valid

    def test_exceeds_budget(self):
        # damage_bonus_d6 costs 3, exceeds tier 1 budget of 2
        effects = [{"type": "damage_bonus_d6", "params": {"element": "fire"}}]
        valid, error = validate_trait(effects, 1)
        assert not valid
        assert "exceeds" in error.lower()

    def test_unknown_effect_type(self):
        effects = [{"type": "nonexistent_ability", "params": {}}]
        valid, error = validate_trait(effects, 1)
        assert not valid
        assert "Unknown" in error

    def test_missing_required_param(self):
        effects = [{"type": "damage_bonus_d4", "params": {}}]  # missing "element"
        valid, error = validate_trait(effects, 1)
        assert not valid
        assert "element" in error

    def test_empty_effects(self):
        valid, error = validate_trait([], 1)
        assert not valid
        assert "at least one" in error.lower()

    def test_tier_2_allows_more(self):
        effects = [
            {"type": "damage_bonus_d4", "params": {"element": "fire"}},  # 2 pts
            {"type": "speed_bonus", "params": {}},  # 1 pt
        ]
        valid, error = validate_trait(effects, 2)
        assert valid

    def test_tier_3_allows_most(self):
        effects = [
            {"type": "damage_resistance", "params": {"element": "fire"}},  # 3 pts
            {"type": "damage_bonus_d4", "params": {"element": "fire"}},  # 2 pts
            {"type": "darkvision", "params": {}},  # 1 pt
        ]
        valid, error = validate_trait(effects, 3)
        assert valid

    def test_exactly_at_budget(self):
        effects = [{"type": "damage_bonus_d4", "params": {"element": "cold"}}]  # 2 pts = tier 1 budget
        valid, error = validate_trait(effects, 1)
        assert valid

    def test_empty_required_param_value(self):
        effects = [{"type": "skill_bonus", "params": {"skill": ""}}]
        valid, error = validate_trait(effects, 1)
        assert not valid


class TestEffectCosts:
    """Tests for cost calculation functions."""

    def test_known_effect_cost(self):
        assert get_effect_cost("damage_bonus_d4") == 2
        assert get_effect_cost("speed_bonus") == 1
        assert get_effect_cost("extra_spell_slot_1") == 3

    def test_unknown_effect_cost(self):
        assert get_effect_cost("nonexistent") == 0

    def test_total_cost(self):
        effects = [
            {"type": "speed_bonus"},     # 1
            {"type": "darkvision"},      # 1
            {"type": "skill_bonus"},     # 1
        ]
        assert total_effect_cost(effects) == 3

    def test_total_cost_empty(self):
        assert total_effect_cost([]) == 0


class TestFormatEffectDescription:
    """Tests for format_effect_description function."""

    def test_simple_effect(self):
        effect = {"type": "speed_bonus", "params": {}}
        desc = format_effect_description(effect)
        assert "+5 movement speed" in desc

    def test_parameterized_effect(self):
        effect = {"type": "damage_bonus_d4", "params": {"element": "fire"}}
        desc = format_effect_description(effect)
        assert "fire" in desc
        assert "+1d4" in desc

    def test_unknown_effect(self):
        effect = {"type": "nonexistent", "params": {}}
        desc = format_effect_description(effect)
        assert "Unknown" in desc


class TestApplyTraitEffects:
    """Tests for applying passive trait effects to character."""

    def test_speed_bonus(self):
        char = {"speed": 30}
        traits = [{"effects": [{"type": "speed_bonus", "params": {}}]}]
        result = apply_trait_effects(char, traits)
        assert result["speed"] == 35

    def test_darkvision(self):
        char = {"properties": {}}
        traits = [{"effects": [{"type": "darkvision", "params": {}}]}]
        result = apply_trait_effects(char, traits)
        assert result["properties"]["darkvision"] == 30

    def test_skill_proficiency(self):
        char = {"skill_proficiencies": ["stealth"]}
        traits = [{"effects": [{"type": "skill_proficiency", "params": {"skill": "perception"}}]}]
        result = apply_trait_effects(char, traits)
        assert "perception" in result["skill_proficiencies"]
        assert "stealth" in result["skill_proficiencies"]

    def test_no_duplicate_proficiency(self):
        char = {"skill_proficiencies": ["stealth"]}
        traits = [{"effects": [{"type": "skill_proficiency", "params": {"skill": "stealth"}}]}]
        result = apply_trait_effects(char, traits)
        assert result["skill_proficiencies"].count("stealth") == 1

    def test_extra_spell_slot(self):
        char = {"spell_slots_max": {"1": 2, "2": 1}}
        traits = [{"effects": [{"type": "extra_spell_slot_1", "params": {}}]}]
        result = apply_trait_effects(char, traits)
        assert result["spell_slots_max"]["1"] == 3

    def test_multiple_traits(self):
        char = {"speed": 30, "properties": {}}
        traits = [
            {"effects": [{"type": "speed_bonus", "params": {}}]},
            {"effects": [{"type": "darkvision", "params": {}}]},
        ]
        result = apply_trait_effects(char, traits)
        assert result["speed"] == 35
        assert result["properties"]["darkvision"] == 30

    def test_does_not_mutate_original(self):
        char = {"speed": 30}
        traits = [{"effects": [{"type": "speed_bonus", "params": {}}]}]
        result = apply_trait_effects(char, traits)
        assert char["speed"] == 30  # Original unchanged
        assert result["speed"] == 35


class TestFallbackTraits:
    """Tests for curated fallback trait data."""

    def test_all_categories_have_fallback(self):
        from text_rpg.mechanics.behavior_tracker import BEHAVIOR_CATEGORIES
        for cat in BEHAVIOR_CATEGORIES:
            assert cat in FALLBACK_TRAITS, f"Missing fallback for '{cat}'"

    def test_fallback_effects_are_valid(self):
        for name, trait in FALLBACK_TRAITS.items():
            assert "name" in trait
            assert "effects" in trait
            assert len(trait["effects"]) > 0
            for effect in trait["effects"]:
                assert effect["type"] in TRAIT_EFFECTS

    def test_tier_budgets_defined(self):
        assert TIER_BUDGETS[1] == 2
        assert TIER_BUDGETS[2] == 4
        assert TIER_BUDGETS[3] == 6
