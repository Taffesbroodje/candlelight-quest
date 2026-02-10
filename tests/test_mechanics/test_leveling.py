"""Tests for src/text_rpg/mechanics/leveling.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.leveling import (
    XP_THRESHOLDS,
    can_level_up,
    level_for_xp,
    proficiency_bonus,
    roll_hit_points_on_level_up,
    xp_for_level,
)


class TestXpForLevel:
    @pytest.mark.parametrize("level, expected", [
        (1, 0), (2, 300), (3, 900), (5, 6500), (10, 64000), (20, 355000),
    ])
    def test_known_levels(self, level, expected):
        assert xp_for_level(level) == expected

    @pytest.mark.parametrize("level", [0, -1, 21])
    def test_invalid_levels(self, level):
        assert xp_for_level(level) == 0


class TestLevelForXp:
    @pytest.mark.parametrize("xp, expected", [
        (0, 1),
        (299, 1),
        (300, 2),
        (900, 3),
        (899, 2),
        (355000, 20),
    ])
    def test_exact_thresholds(self, xp, expected):
        assert level_for_xp(xp) == expected

    def test_between_thresholds(self):
        assert level_for_xp(500) == 2

    def test_massive_xp(self):
        assert level_for_xp(999999) == 20


class TestProficiencyBonus:
    @pytest.mark.parametrize("level, expected", [
        (1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4),
        (13, 5), (16, 5), (17, 6), (20, 6),
    ])
    def test_tier_boundaries(self, level, expected):
        assert proficiency_bonus(level) == expected

    def test_clamped_below(self):
        assert proficiency_bonus(0) == 2

    def test_clamped_above(self):
        assert proficiency_bonus(25) == 6


class TestCanLevelUp:
    @pytest.mark.parametrize("level, xp, expected", [
        (1, 300, True),
        (1, 299, False),
        (1, 0, False),
        (2, 900, True),
        (2, 899, False),
        (19, 355000, True),
    ])
    def test_threshold_pairs(self, level, xp, expected):
        assert can_level_up(level, xp) == expected

    def test_level_20_cap(self):
        assert can_level_up(20, 999999) is False


class TestRollHitPointsOnLevelUp:
    def test_positive_con_mod(self, seeded_rng):
        for _ in range(20):
            hp = roll_hit_points_on_level_up("fighter", 3)
            assert 4 <= hp <= 13  # 1d10(1-10) + 3

    def test_negative_con_mod_min_1(self, seeded_rng):
        for _ in range(50):
            hp = roll_hit_points_on_level_up("wizard", -3)
            assert hp >= 1  # minimum 1

    def test_unknown_class_defaults_d8(self, seeded_rng):
        for _ in range(50):
            hp = roll_hit_points_on_level_up("barbarian", 0)
            assert 1 <= hp <= 8
