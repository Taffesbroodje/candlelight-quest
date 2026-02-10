"""Tests for src/text_rpg/mechanics/reputation.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.reputation import (
    REPUTATION_EFFECTS,
    adjust_reputation,
    clamp_reputation,
    get_effects,
    get_tier,
    reputation_from_action,
)


class TestGetTier:
    @pytest.mark.parametrize("rep, expected", [
        (-100, "hated"), (-61, "hated"), (-60, "hostile"), (-21, "hostile"),
        (-20, "unfriendly"), (-6, "unfriendly"), (-5, "neutral"), (0, "neutral"),
        (5, "neutral"), (6, "friendly"), (20, "friendly"), (21, "trusted"),
        (60, "trusted"), (61, "honored"), (100, "honored"),
    ])
    def test_boundary_values(self, rep, expected):
        assert get_tier(rep) == expected

    def test_out_of_range_clamped(self):
        assert get_tier(-200) == "hated"
        assert get_tier(200) == "honored"


class TestClampReputation:
    def test_in_range_unchanged(self):
        assert clamp_reputation(50) == 50

    def test_below_minimum(self):
        assert clamp_reputation(-150) == -100

    def test_above_maximum(self):
        assert clamp_reputation(200) == 100


class TestAdjustReputation:
    def test_basic_adjust(self):
        assert adjust_reputation(0, 10) == 10

    def test_clamp_at_max(self):
        assert adjust_reputation(95, 20) == 100

    def test_clamp_at_min(self):
        assert adjust_reputation(-90, -20) == -100


class TestGetEffects:
    @pytest.mark.parametrize("rep, expected_mult", [
        (-100, 2.0), (-60, 1.5), (-20, 1.25), (0, 1.0),
        (10, 0.9), (30, 0.75), (80, 0.5),
    ])
    def test_shop_price_mult(self, rep, expected_mult):
        effects = get_effects(rep)
        assert effects["shop_price_mult"] == expected_mult

    def test_hated_attack_on_sight(self):
        assert get_effects(-100)["attack_on_sight"] is True

    def test_neutral_quests_available(self):
        assert get_effects(0)["quest_available"] is True


class TestReputationFromAction:
    @pytest.mark.parametrize("action, expected_delta", [
        ("kill_npc", -15),
        ("complete_quest", 10),
        ("steal", -10),
        ("help", 5),
    ])
    def test_known_actions(self, action, expected_delta):
        result = reputation_from_action(action, {"faction_id": "guard"})
        assert result["guard"] == expected_delta

    def test_unknown_action_empty(self):
        assert reputation_from_action("dance") == {}

    @pytest.mark.parametrize("witnesses, expected_mult", [
        (0, 1.0), (1, 1.25), (2, 1.5), (3, 1.75), (4, 2.0), (5, 2.0),
    ])
    def test_witness_multiplier(self, witnesses, expected_mult):
        result = reputation_from_action(
            "help", {"faction_id": "guard", "witnesses": witnesses}
        )
        assert result["guard"] == int(5 * expected_mult)

    def test_opposing_faction_inverse_half(self):
        result = reputation_from_action(
            "help", {"faction_id": "guard", "opposing_faction_id": "bandits"}
        )
        assert result["guard"] == 5
        assert result["bandits"] == -2  # int(-5 * 0.5)

    def test_no_context_with_known_action(self):
        # No faction_id means no faction deltas
        assert reputation_from_action("help") == {}
