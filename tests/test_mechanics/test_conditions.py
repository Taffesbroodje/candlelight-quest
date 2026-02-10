"""Tests for src/text_rpg/mechanics/conditions.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.conditions import (
    CONDITION_EFFECTS,
    can_take_actions,
    get_condition_effects,
    grants_advantage_to_attackers,
    has_attack_advantage,
    has_attack_disadvantage,
    is_incapacitated,
)


class TestGetConditionEffects:
    @pytest.mark.parametrize("condition", list(CONDITION_EFFECTS.keys()))
    def test_known_conditions_non_empty(self, condition):
        effects = get_condition_effects(condition)
        assert effects, f"{condition} should have effects"

    @pytest.mark.parametrize("condition", ["flying", "hasted", "blessed", "enlarged"])
    def test_unknown_conditions_empty(self, condition):
        assert get_condition_effects(condition) == {}

    def test_case_insensitive(self):
        # get_condition_effects uses lowercase key lookup
        assert get_condition_effects("blinded") == CONDITION_EFFECTS["blinded"]


class TestHasAttackAdvantage:
    def test_invisible_grants_advantage(self):
        assert has_attack_advantage(["invisible"]) is True

    def test_empty_no_advantage(self):
        assert has_attack_advantage([]) is False

    def test_mixed_with_invisible(self):
        assert has_attack_advantage(["poisoned", "invisible"]) is True

    def test_no_advantage_conditions(self):
        assert has_attack_advantage(["charmed", "deafened"]) is False


class TestHasAttackDisadvantage:
    @pytest.mark.parametrize("conditions, expected", [
        (["blinded"], True),
        (["poisoned"], True),
        (["prone"], True),
        (["restrained"], True),
        (["charmed"], False),
        ([], False),
    ])
    def test_disadvantage(self, conditions, expected):
        assert has_attack_disadvantage(conditions) == expected


class TestCanTakeActions:
    @pytest.mark.parametrize("conditions", [
        ["incapacitated"],
        ["paralyzed"],
        ["petrified"],
        ["stunned"],
        ["unconscious"],
    ])
    def test_incapacitating_conditions(self, conditions):
        assert can_take_actions(conditions) is False

    @pytest.mark.parametrize("conditions", [
        ["blinded"],
        ["charmed"],
        ["deafened"],
        ["frightened"],
        ["poisoned"],
        ["prone"],
    ])
    def test_non_incapacitating_conditions(self, conditions):
        assert can_take_actions(conditions) is True

    def test_empty_can_act(self):
        assert can_take_actions([]) is True

    def test_mixed_incapacitating(self):
        assert can_take_actions(["blinded", "stunned"]) is False


class TestIsIncapacitated:
    def test_stunned(self):
        assert is_incapacitated(["stunned"]) is True

    def test_empty(self):
        assert is_incapacitated([]) is False

    def test_non_incapacitating(self):
        assert is_incapacitated(["prone", "blinded"]) is False


class TestGrantsAdvantageToAttackers:
    @pytest.mark.parametrize("conditions, expected", [
        (["blinded"], True),
        (["paralyzed"], True),
        (["stunned"], True),
        (["unconscious"], True),
        (["restrained"], True),
        (["prone"], False),  # Only melee, not universal
        (["charmed"], False),
        (["deafened"], False),
        (["poisoned"], False),
        ([], False),
    ])
    def test_grants_advantage(self, conditions, expected):
        assert grants_advantage_to_attackers(conditions) == expected
