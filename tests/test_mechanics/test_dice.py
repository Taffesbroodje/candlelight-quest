"""Tests for src/text_rpg/mechanics/dice.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.dice import (
    DiceResult,
    roll,
    roll_d20,
    roll_with_advantage,
    roll_with_disadvantage,
)


class TestRollParsing:
    @pytest.mark.parametrize("expr", [
        "1d20", "2d6", "4d6kh3", "4d6kl1", "1d8+3", "2d10-1",
        "1d4", "3d12+5",
    ])
    def test_valid_expressions(self, expr, seeded_rng):
        result = roll(expr)
        assert isinstance(result, DiceResult)
        assert result.expression == expr

    @pytest.mark.parametrize("expr", [
        "", "abc", "d20", "roll 1d6", "1d",
    ])
    def test_invalid_expressions(self, expr):
        with pytest.raises(ValueError):
            roll(expr)


class TestRollRange:
    @pytest.mark.parametrize("expr, lo, hi", [
        ("1d6", 1, 6),
        ("2d6", 2, 12),
        ("1d20", 1, 20),
        ("1d4+2", 3, 6),
    ])
    def test_total_within_range(self, expr, lo, hi):
        for _ in range(100):
            result = roll(expr)
            assert lo <= result.total <= hi, f"{expr} gave {result.total}"

    def test_keep_highest(self, seeded_rng):
        for _ in range(50):
            result = roll("4d6kh3")
            assert 3 <= result.total <= 18
            assert len(result.individual_rolls) == 4

    def test_keep_lowest(self, seeded_rng):
        for _ in range(50):
            result = roll("4d6kl1")
            assert 1 <= result.total <= 6
            assert len(result.individual_rolls) == 4


class TestRollD20:
    @pytest.mark.parametrize("mod", [-5, 0, 3, 10])
    def test_modifier_applied(self, mod, seeded_rng):
        result = roll_d20(modifier=mod)
        assert result.modifier == mod
        base = result.individual_rolls[0]
        assert result.total == base + mod

    def test_base_range(self):
        for _ in range(100):
            result = roll_d20()
            assert 1 <= result.individual_rolls[0] <= 20


class TestAdvantageDisadvantage:
    def test_advantage_picks_higher(self, seeded_rng):
        for _ in range(50):
            best, r1, r2 = roll_with_advantage()
            assert best.total == max(r1.total, r2.total)

    def test_disadvantage_picks_lower(self, seeded_rng):
        for _ in range(50):
            worst, r1, r2 = roll_with_disadvantage()
            assert worst.total == min(r1.total, r2.total)

    def test_advantage_returns_3_tuple(self, seeded_rng):
        result = roll_with_advantage()
        assert len(result) == 3
        assert all(isinstance(r, DiceResult) for r in result)

    def test_disadvantage_returns_3_tuple(self, seeded_rng):
        result = roll_with_disadvantage()
        assert len(result) == 3
        assert all(isinstance(r, DiceResult) for r in result)
