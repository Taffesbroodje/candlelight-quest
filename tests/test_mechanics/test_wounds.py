"""Tests for src/text_rpg/mechanics/wounds.py."""
from __future__ import annotations

import random

import pytest

from text_rpg.mechanics.wounds import (
    WOUND_TYPES,
    check_for_wound,
    get_wound_penalties,
    heal_wound,
)


class TestCheckForWound:
    def test_no_wound_at_50_percent(self, seeded_rng):
        assert check_for_wound(50, 100) is None  # 50 <= 100*0.5

    def test_wound_at_51_percent(self, seeded_rng):
        wound = check_for_wound(51, 100)
        assert wound is not None

    def test_severe_at_75_percent(self, seeded_rng):
        wound = check_for_wound(75, 100)
        assert wound is not None
        # Severe wounds are from WOUND_TYPES[:4]
        assert wound["type"] in [w[0] for w in WOUND_TYPES[:4]]

    def test_zero_hp_max_returns_none(self):
        assert check_for_wound(10, 0) is None

    def test_negative_damage_returns_none(self):
        # damage <= hp_max * 0.5 when damage is negative
        assert check_for_wound(-5, 100) is None

    def test_wound_structure(self, seeded_rng):
        wound = check_for_wound(60, 100)
        assert wound is not None
        assert "type" in wound
        assert "ability" in wound
        assert "penalty" in wound
        assert "description" in wound


class TestHealWound:
    def test_healer_always_succeeds(self):
        wound = {"type": "deep_gash", "ability": "strength", "penalty": -2}
        for _ in range(100):
            assert heal_wound(wound, "healer_npc") is True

    def test_long_rest_approximately_50(self):
        wound = {"type": "deep_gash", "ability": "strength", "penalty": -2}
        healed = sum(heal_wound(wound, "long_rest") for _ in range(1000))
        assert 350 < healed < 650  # ~50% with generous bounds

    def test_unknown_method_defaults_25(self):
        wound = {"type": "deep_gash", "ability": "strength", "penalty": -2}
        healed = sum(heal_wound(wound, "magic_salve") for _ in range(1000))
        assert 150 < healed < 350  # ~25%


class TestGetWoundPenalties:
    def test_empty_no_penalties(self):
        assert get_wound_penalties([]) == {}

    def test_single_wound(self):
        wounds = [{"ability": "strength", "penalty": -2}]
        assert get_wound_penalties(wounds) == {"strength": -2}

    def test_stacking_same_ability(self):
        wounds = [
            {"ability": "strength", "penalty": -2},
            {"ability": "strength", "penalty": -1},
        ]
        assert get_wound_penalties(wounds) == {"strength": -3}

    def test_multiple_abilities(self):
        wounds = [
            {"ability": "strength", "penalty": -2},
            {"ability": "dexterity", "penalty": -1},
        ]
        result = get_wound_penalties(wounds)
        assert result == {"strength": -2, "dexterity": -1}

    def test_missing_fields(self):
        wounds = [{"type": "unknown"}]  # no ability/penalty
        assert get_wound_penalties(wounds) == {}
