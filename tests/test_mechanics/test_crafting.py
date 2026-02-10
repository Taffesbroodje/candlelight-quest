"""Tests for src/text_rpg/mechanics/crafting.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.crafting import (
    RECIPES,
    TRADE_SKILL_XP,
    Recipe,
    attempt_craft,
    can_craft,
    can_level_up_trade_skill,
    get_available_recipes,
    trade_skill_level_for_xp,
)


@pytest.fixture
def healing_recipe():
    return RECIPES["brew_healing_potion"]


class TestCanCraft:
    def test_sufficient(self, healing_recipe):
        ok, reason = can_craft(healing_recipe, 1, {"healing_herb": 5})
        assert ok is True
        assert reason == ""

    def test_insufficient_level(self, healing_recipe):
        recipe = RECIPES["brew_antidote"]  # min_level 2
        ok, reason = can_craft(recipe, 1, {"healing_herb": 5, "moonpetal": 5})
        assert ok is False
        assert "level" in reason.lower()

    def test_missing_materials(self, healing_recipe):
        ok, reason = can_craft(healing_recipe, 1, {})
        assert ok is False
        assert "need" in reason.lower()

    def test_partial_materials(self, healing_recipe):
        ok, reason = can_craft(healing_recipe, 1, {"healing_herb": 1})
        assert ok is False

    def test_excess_ok(self, healing_recipe):
        ok, _ = can_craft(healing_recipe, 5, {"healing_herb": 99})
        assert ok is True

    def test_no_materials_needed(self):
        recipe = RECIPES["gather_herbs"]
        ok, _ = can_craft(recipe, 1, {})
        assert ok is True


class TestAttemptCraft:
    def test_high_roll_succeeds(self, seeded_rng, healing_recipe):
        # DC 12 for healing potion, skill_level=5 gives +2 bonus, ability_mod=3
        # Need to try multiple seeds to get a success
        import random
        random.seed(1)  # seed that gives a high roll
        successes = 0
        for _ in range(50):
            success, total = attempt_craft(healing_recipe, 5, 3)
            if success:
                successes += 1
        assert successes > 0, "Expected at least one success in 50 attempts"

    def test_low_roll_can_fail(self, healing_recipe):
        import random
        random.seed(42)
        failures = 0
        for _ in range(50):
            success, total = attempt_craft(healing_recipe, 1, -2)
            if not success:
                failures += 1
        assert failures > 0, "Expected at least one failure in 50 attempts"

    def test_skill_bonus_included(self, healing_recipe, seeded_rng):
        _, total = attempt_craft(healing_recipe, 6, 0)
        # skill_bonus = 6 // 2 = 3, total = d20_roll + 0 + 3
        assert total >= 4  # minimum d20(1) + 0 + 3

    def test_ability_mod_included(self, healing_recipe, seeded_rng):
        _, total = attempt_craft(healing_recipe, 1, 5)
        # skill_bonus = 0, total = d20_roll + 5 + 0
        assert total >= 6  # minimum d20(1) + 5 + 0


class TestTradeSkillLevelForXp:
    @pytest.mark.parametrize("xp, expected", [
        (0, 1), (49, 1), (50, 2), (149, 2), (150, 3),
        (2500, 10), (9999, 10),
    ])
    def test_thresholds(self, xp, expected):
        assert trade_skill_level_for_xp(xp) == expected


class TestCanLevelUpTradeSkill:
    @pytest.mark.parametrize("level, xp, expected", [
        (1, 50, True), (1, 49, False), (2, 150, True), (2, 149, False),
    ])
    def test_boundaries(self, level, xp, expected):
        assert can_level_up_trade_skill(level, xp) == expected

    def test_max_level_10(self):
        assert can_level_up_trade_skill(10, 99999) is False


class TestGetAvailableRecipes:
    def test_alchemy_level_1(self):
        recipes = get_available_recipes("alchemy", 1)
        ids = {r.id for r in recipes}
        assert "brew_healing_potion" in ids

    def test_unknown_skill_empty(self):
        assert get_available_recipes("dancing", 10) == []

    def test_higher_level_includes_lower(self):
        r1 = get_available_recipes("alchemy", 1)
        r3 = get_available_recipes("alchemy", 3)
        assert len(r3) > len(r1)
