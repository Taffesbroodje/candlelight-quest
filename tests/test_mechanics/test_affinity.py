"""Tests for src/text_rpg/mechanics/affinity.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.affinity import (
    RECRUIT_THRESHOLD,
    affinity_from_action,
    affinity_from_gift,
    can_recruit,
    clamp_affinity,
    get_shop_discount,
    get_tier,
    get_tier_name,
)


class TestGetTier:
    @pytest.mark.parametrize("score, expected_name", [
        (0, "Stranger"), (4, "Stranger"), (5, "Acquaintance"), (14, "Acquaintance"),
        (15, "Companion"), (29, "Companion"), (30, "Friend"), (49, "Friend"),
        (50, "Close Friend"), (74, "Close Friend"), (75, "Trusted Ally"),
        (99, "Trusted Ally"), (100, "Sworn Bond"),
    ])
    def test_tier_boundaries(self, score, expected_name):
        assert get_tier(score)["name"] == expected_name

    @pytest.mark.parametrize("score, expected_discount", [
        (0, 0.0), (15, 0.05), (30, 0.10), (50, 0.15), (75, 0.20), (100, 0.25),
    ])
    def test_shop_discount_scaling(self, score, expected_discount):
        assert get_shop_discount(score) == expected_discount


class TestCanRecruit:
    @pytest.mark.parametrize("score, expected", [
        (0, False), (14, False), (15, True), (50, True), (100, True),
    ])
    def test_threshold(self, score, expected):
        assert can_recruit(score) == expected


class TestAffinityFromGift:
    def test_preferred_gift(self):
        prefs = {"preferred_gifts": ["ruby", "ale"], "disliked_gifts": ["bones"]}
        assert affinity_from_gift("ruby", prefs) == 5

    def test_disliked_gift(self):
        prefs = {"preferred_gifts": ["ruby"], "disliked_gifts": ["bones"]}
        assert affinity_from_gift("bones", prefs) == -2

    def test_neutral_gift(self):
        prefs = {"preferred_gifts": ["ruby"], "disliked_gifts": ["bones"]}
        assert affinity_from_gift("bread", prefs) == 2

    def test_empty_prefs_is_neutral(self):
        assert affinity_from_gift("anything", {}) == 2


class TestAffinityFromAction:
    @pytest.mark.parametrize("action, expected", [
        ("complete_quest", 5),
        ("help_npc", 3),
        ("attack_npc", -10),
        ("conversation", 1),
    ])
    def test_known_actions(self, action, expected):
        assert affinity_from_action(action) == expected

    def test_unknown_action_zero(self):
        assert affinity_from_action("juggle") == 0


class TestClampAffinity:
    def test_in_range(self):
        assert clamp_affinity(50) == 50

    def test_below_zero(self):
        assert clamp_affinity(-10) == 0

    def test_above_100(self):
        assert clamp_affinity(150) == 100
