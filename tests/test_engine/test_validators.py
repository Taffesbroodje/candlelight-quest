"""Tests for src/text_rpg/engine/validators.py."""
from __future__ import annotations

import pytest

from text_rpg.engine.validators import validate_action, validate_mutations
from text_rpg.models.action import Action, StateMutation
from text_rpg.systems.base import GameContext


def _make_context(hp_max=100, conditions=None, combat_state=None, char_id="player1"):
    char = {
        "id": char_id,
        "hp_max": hp_max,
        "hp_current": hp_max,
        "conditions": conditions or [],
    }
    location = {"id": "test_loc", "name": "Test", "description": ""}
    return GameContext(
        game_id="test", character=char, location=location,
        entities=[], combat_state=combat_state,
    )


class TestValidateMutations:
    def test_hp_clamped_at_max(self):
        ctx = _make_context(hp_max=50)
        muts = [StateMutation(field="hp_current", new_value=999)]
        result = validate_mutations(muts, ctx)
        assert result[0].new_value == 50

    def test_hp_clamped_at_zero(self):
        ctx = _make_context(hp_max=50)
        muts = [StateMutation(field="hp_current", new_value=-10)]
        result = validate_mutations(muts, ctx)
        assert result[0].new_value == 0

    def test_hp_exact_max(self):
        ctx = _make_context(hp_max=50)
        muts = [StateMutation(field="hp_current", new_value=50)]
        result = validate_mutations(muts, ctx)
        assert result[0].new_value == 50

    def test_non_hp_passthrough(self):
        ctx = _make_context()
        muts = [StateMutation(field="gold", new_value=999)]
        result = validate_mutations(muts, ctx)
        assert result[0].new_value == 999

    def test_empty_list(self):
        ctx = _make_context()
        assert validate_mutations([], ctx) == []


class TestValidateAction:
    def test_valid_action(self):
        ctx = _make_context()
        action = Action(action_type="move", actor_id="player1")
        ok, reason = validate_action(action, ctx)
        assert ok is True
        assert reason == ""

    def test_incapacitated(self):
        ctx = _make_context(conditions=["stunned"])
        action = Action(action_type="attack", actor_id="player1")
        ok, reason = validate_action(action, ctx)
        assert ok is False
        assert "incapacitated" in reason.lower()

    def test_not_your_turn(self):
        combat = {
            "is_active": True,
            "turn_order": ["npc1", "player1"],
            "current_turn_index": 0,
        }
        ctx = _make_context(combat_state=combat)
        action = Action(action_type="attack", actor_id="player1")
        ok, reason = validate_action(action, ctx)
        assert ok is False
        assert "not your turn" in reason.lower()

    def test_your_turn(self):
        combat = {
            "is_active": True,
            "turn_order": ["player1", "npc1"],
            "current_turn_index": 0,
        }
        ctx = _make_context(combat_state=combat)
        action = Action(action_type="attack", actor_id="player1")
        ok, reason = validate_action(action, ctx)
        assert ok is True

    def test_no_combat_state(self):
        ctx = _make_context()
        action = Action(action_type="move", actor_id="player1")
        ok, _ = validate_action(action, ctx)
        assert ok is True
