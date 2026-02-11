"""Tests for assess_threat_level in combat_math."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.combat_math import assess_threat_level


class TestAssessThreatLevel:
    @pytest.mark.parametrize("player,enemy,expected", [
        (10, 3, "trivial"),
        (10, 5, "trivial"),
        (10, 7, "easy"),
        (10, 8, "easy"),
        (10, 9, "normal"),
        (10, 10, "normal"),
        (10, 11, "normal"),
        (10, 12, "hard"),
        (10, 13, "hard"),
        (10, 14, "deadly"),
        (10, 15, "deadly"),
        (10, 16, "overwhelming"),
        (10, 20, "overwhelming"),
        (1, 1, "normal"),
        (1, 2, "normal"),
        (1, 3, "hard"),
        (1, 5, "deadly"),
        (1, 7, "overwhelming"),
        (5, 5, "normal"),
        (5, 1, "easy"),
        (5, 0, "trivial"),
        (20, 15, "trivial"),
    ])
    def test_threat_levels(self, player, enemy, expected):
        assert assess_threat_level(player, enemy) == expected

    def test_same_level_is_normal(self):
        for level in (1, 5, 10, 15, 20):
            assert assess_threat_level(level, level) == "normal"

    def test_returns_string(self):
        result = assess_threat_level(5, 5)
        assert isinstance(result, str)
        assert result in ("trivial", "easy", "normal", "hard", "deadly", "overwhelming")
