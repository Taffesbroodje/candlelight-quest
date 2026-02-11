"""Tests for src/text_rpg/mechanics/size.py and size integration."""
from __future__ import annotations

import random

import pytest

from text_rpg.mechanics.size import (
    SIZE_CATEGORIES,
    carrying_capacity_multiplier,
    grapple_size_advantage,
    intimidation_modifier,
    squeeze_through_narrow,
    stealth_modifier,
)


class TestSizeCategories:
    def test_all_categories_present(self):
        assert "Small" in SIZE_CATEGORIES
        assert "Medium" in SIZE_CATEGORIES
        assert "Large" in SIZE_CATEGORIES

    def test_ordering(self):
        assert SIZE_CATEGORIES["Small"] < SIZE_CATEGORIES["Medium"] < SIZE_CATEGORIES["Large"]


class TestCarryingCapacityMultiplier:
    @pytest.mark.parametrize("size, expected", [
        ("Small", 0.5),
        ("Medium", 1.0),
        ("Large", 2.0),
    ])
    def test_multipliers(self, size, expected):
        assert carrying_capacity_multiplier(size) == expected

    def test_unknown_defaults_medium(self):
        assert carrying_capacity_multiplier("Unknown") == 1.0


class TestGrappleSizeAdvantage:
    def test_same_size(self):
        adv, disadv = grapple_size_advantage("Medium", "Medium")
        assert adv is False
        assert disadv is False

    def test_larger_attacker(self):
        adv, disadv = grapple_size_advantage("Large", "Medium")
        assert adv is True
        assert disadv is False

    def test_smaller_attacker(self):
        adv, disadv = grapple_size_advantage("Small", "Medium")
        assert adv is False
        assert disadv is True

    def test_large_vs_small(self):
        adv, disadv = grapple_size_advantage("Large", "Small")
        assert adv is True
        assert disadv is False

    def test_small_vs_large_auto_fail(self):
        # 2+ size gap: Small (-1) vs Large (1) = diff of -2
        adv, disadv = grapple_size_advantage("Small", "Large")
        assert adv is False
        assert disadv is True

    def test_medium_vs_large_disadvantage(self):
        adv, disadv = grapple_size_advantage("Medium", "Large")
        assert adv is False
        assert disadv is True


class TestStealthModifier:
    @pytest.mark.parametrize("size, expected", [
        ("Small", 2),
        ("Medium", 0),
        ("Large", -2),
    ])
    def test_values(self, size, expected):
        assert stealth_modifier(size) == expected


class TestIntimidationModifier:
    @pytest.mark.parametrize("size, expected", [
        ("Small", -2),
        ("Medium", 0),
        ("Large", 2),
    ])
    def test_values(self, size, expected):
        assert intimidation_modifier(size) == expected


class TestSqueezeThroughNarrow:
    def test_large_squeeze(self):
        result = squeeze_through_narrow("Large")
        assert result["movement_multiplier"] == 2
        assert result["attack_disadvantage"] is True
        assert result["can_squeeze_tiny"] is False

    def test_small_squeeze(self):
        result = squeeze_through_narrow("Small")
        assert result["movement_multiplier"] == 1
        assert result["attack_disadvantage"] is False
        assert result["can_squeeze_tiny"] is True

    def test_medium_normal(self):
        result = squeeze_through_narrow("Medium")
        assert result["movement_multiplier"] == 1
        assert result["attack_disadvantage"] is False
        assert result["can_squeeze_tiny"] is False


class TestCharacterCreationSize:
    def test_small_races(self):
        from text_rpg.mechanics.character_creation import RACIAL_SIZE
        for race in ("halfling", "gnome", "goblin"):
            assert RACIAL_SIZE[race] == "Small", f"{race} should be Small"

    def test_large_races(self):
        from text_rpg.mechanics.character_creation import RACIAL_SIZE
        for race in ("centaur", "minotaur", "bugbear"):
            assert RACIAL_SIZE[race] == "Large", f"{race} should be Large"

    def test_medium_races(self):
        from text_rpg.mechanics.character_creation import RACIAL_SIZE
        medium_races = [
            "human", "elf", "dwarf", "half_orc", "half_elf", "tiefling",
            "dragonborn", "goliath", "aasimar", "tabaxi", "firbolg",
            "kenku", "lizardfolk", "orc", "genasi", "changeling", "warforged",
        ]
        for race in medium_races:
            assert RACIAL_SIZE[race] == "Medium", f"{race} should be Medium"

    def test_create_character_includes_size(self):
        from text_rpg.mechanics.character_creation import create_character
        char = create_character(
            "Test", "bugbear", "fighter",
            {"strength": 15, "dexterity": 14, "constitution": 13,
             "intelligence": 12, "wisdom": 10, "charisma": 8},
            ["athletics"], "test-game",
        )
        assert char["size"] == "Large"

    def test_create_character_small(self):
        from text_rpg.mechanics.character_creation import create_character
        char = create_character(
            "Test", "halfling", "rogue",
            {"strength": 8, "dexterity": 15, "constitution": 14,
             "intelligence": 13, "wisdom": 12, "charisma": 10},
            ["stealth", "acrobatics", "perception", "investigation"], "test-game",
        )
        assert char["size"] == "Small"

    def test_create_character_medium_default(self):
        from text_rpg.mechanics.character_creation import create_character
        char = create_character(
            "Test", "human", "fighter",
            {"strength": 15, "dexterity": 14, "constitution": 13,
             "intelligence": 12, "wisdom": 10, "charisma": 8},
            ["athletics", "perception"], "test-game",
        )
        assert char["size"] == "Medium"

    def test_all_23_races_in_racial_size(self):
        from text_rpg.mechanics.character_creation import RACIAL_SIZE, RACIAL_SPEED
        assert set(RACIAL_SIZE.keys()) == set(RACIAL_SPEED.keys())


class TestGrappleCheck:
    def test_grapple_check_returns_dict(self, seeded_rng):
        from text_rpg.mechanics.combat_math import grapple_check
        result = grapple_check(
            attacker_athletics=14, attacker_prof=2, attacker_proficient=True,
            defender_score=10, defender_prof=2, defender_proficient=False,
        )
        assert "success" in result
        assert "auto_fail" in result
        assert result["auto_fail"] is False

    def test_grapple_auto_fail_too_large(self):
        from text_rpg.mechanics.combat_math import grapple_check
        result = grapple_check(
            attacker_athletics=14, attacker_prof=2, attacker_proficient=True,
            defender_score=10, defender_prof=2, defender_proficient=False,
            attacker_size="Small", defender_size="Large",
        )
        assert result["auto_fail"] is True
        assert result["success"] is False

    def test_grapple_size_advantage_applied(self, seeded_rng):
        from text_rpg.mechanics.combat_math import grapple_check
        result = grapple_check(
            attacker_athletics=14, attacker_prof=2, attacker_proficient=True,
            defender_score=10, defender_prof=2, defender_proficient=False,
            attacker_size="Large", defender_size="Small",
        )
        assert result["advantage"] is True
        assert result["disadvantage"] is False

    def test_grapple_size_disadvantage_applied(self, seeded_rng):
        from text_rpg.mechanics.combat_math import grapple_check
        result = grapple_check(
            attacker_athletics=14, attacker_prof=2, attacker_proficient=True,
            defender_score=10, defender_prof=2, defender_proficient=False,
            attacker_size="Medium", defender_size="Large",
        )
        assert result["advantage"] is False
        assert result["disadvantage"] is True


class TestSkillCheckSizeModifier:
    def test_size_modifier_applied(self, seeded_rng):
        from text_rpg.mechanics.skills import skill_check
        # Run many checks with +2 bonus vs without, +2 should succeed more
        random.seed(42)
        bonus_successes = sum(
            skill_check(10, 2, False, 12, size_modifier=2)[0]
            for _ in range(200)
        )
        random.seed(42)
        no_bonus_successes = sum(
            skill_check(10, 2, False, 12, size_modifier=0)[0]
            for _ in range(200)
        )
        assert bonus_successes >= no_bonus_successes

    def test_negative_size_modifier(self, seeded_rng):
        from text_rpg.mechanics.skills import skill_check
        random.seed(42)
        penalty_successes = sum(
            skill_check(10, 2, False, 12, size_modifier=-2)[0]
            for _ in range(200)
        )
        random.seed(42)
        no_bonus_successes = sum(
            skill_check(10, 2, False, 12, size_modifier=0)[0]
            for _ in range(200)
        )
        assert penalty_successes <= no_bonus_successes
