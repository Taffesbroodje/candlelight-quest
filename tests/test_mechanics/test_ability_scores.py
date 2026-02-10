"""Tests for src/text_rpg/mechanics/ability_scores.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.ability_scores import (
    RACIAL_BONUSES,
    STANDARD_ARRAY,
    apply_racial_bonuses,
    generate_ability_scores,
    modifier,
)


class TestModifier:
    @pytest.mark.parametrize("score, expected", [
        (1, -5), (2, -4), (3, -4), (8, -1), (9, -1),
        (10, 0), (11, 0), (12, 1), (13, 1), (14, 2),
        (15, 2), (16, 3), (17, 3), (18, 4), (19, 4),
        (20, 5), (30, 10),
    ])
    def test_score_to_modifier(self, score, expected):
        assert modifier(score) == expected

    def test_symmetry_around_10(self):
        """Scores equidistant from 10 have symmetric modifiers."""
        assert modifier(8) == -modifier(12)
        assert modifier(6) == -modifier(14)


class TestGenerateAbilityScores:
    def test_standard_array_values(self):
        scores = generate_ability_scores("standard_array")
        assert sorted(scores, reverse=True) == sorted(STANDARD_ARRAY, reverse=True)

    def test_standard_array_returns_copy(self):
        s1 = generate_ability_scores("standard_array")
        s2 = generate_ability_scores("standard_array")
        assert s1 is not s2

    def test_roll_4d6_range(self, seeded_rng):
        scores = generate_ability_scores("roll_4d6")
        assert len(scores) == 6
        for s in scores:
            assert 3 <= s <= 18

    def test_point_buy_values(self):
        scores = generate_ability_scores("point_buy")
        assert scores == [13, 13, 13, 12, 12, 12]

    def test_unknown_method_defaults_to_standard(self):
        assert generate_ability_scores("unknown") == list(STANDARD_ARRAY)


class TestApplyRacialBonuses:
    @pytest.mark.parametrize("race, expected_deltas", [
        ("human", {"strength": 1, "dexterity": 1, "constitution": 1, "intelligence": 1, "wisdom": 1, "charisma": 1}),
        ("elf", {"dexterity": 2}),
        ("dwarf", {"constitution": 2}),
        ("halfling", {"dexterity": 2}),
        ("half_orc", {"strength": 2, "constitution": 1}),
    ])
    def test_racial_bonuses(self, sample_ability_scores, race, expected_deltas):
        result = apply_racial_bonuses(sample_ability_scores, race)
        for ability, delta in expected_deltas.items():
            assert result[ability] == sample_ability_scores[ability] + delta

    def test_unknown_race_no_bonuses(self, sample_ability_scores):
        result = apply_racial_bonuses(sample_ability_scores, "alien")
        assert result == sample_ability_scores

    def test_input_not_mutated(self, sample_ability_scores):
        original = dict(sample_ability_scores)
        apply_racial_bonuses(sample_ability_scores, "elf")
        assert sample_ability_scores == original
