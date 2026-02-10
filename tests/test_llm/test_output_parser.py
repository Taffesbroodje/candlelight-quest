"""Tests for src/text_rpg/llm/output_parser.py."""
from __future__ import annotations

import json

import pytest

from text_rpg.llm.output_parser import OutputParser


class TestParseActionClassification:
    def test_normal_response(self):
        raw = {"action_type": "move", "target": "north", "parameters": {}, "confidence": 0.9}
        result = OutputParser.parse_action_classification(raw)
        assert result["action_type"] == "MOVE"
        assert result["target"] == "north"
        assert result["confidence"] == 0.9

    def test_uppercases_action_type(self):
        result = OutputParser.parse_action_classification({"action_type": "attack"})
        assert result["action_type"] == "ATTACK"

    def test_missing_action_defaults_custom(self):
        result = OutputParser.parse_action_classification({})
        assert result["action_type"] == "CUSTOM"

    def test_confidence_clamped_low(self):
        result = OutputParser.parse_action_classification({"confidence": -0.5})
        assert result["confidence"] == 0.0

    def test_confidence_clamped_high(self):
        result = OutputParser.parse_action_classification({"confidence": 1.5})
        assert result["confidence"] == 1.0

    def test_missing_confidence_defaults_half(self):
        result = OutputParser.parse_action_classification({})
        assert result["confidence"] == 0.5

    def test_parameters_default_empty(self):
        result = OutputParser.parse_action_classification({})
        assert result["parameters"] == {}

    def test_target_can_be_none(self):
        result = OutputParser.parse_action_classification({"action_type": "look"})
        assert result["target"] is None


class TestParseScenePlan:
    def test_normal(self):
        raw = {
            "available_actions": ["move", "attack"],
            "environmental_details": ["dark cave"],
            "npc_intentions": {"goblin": "ambush"},
            "tension_level": "high",
        }
        result = OutputParser.parse_scene_plan(raw)
        assert result["available_actions"] == ["move", "attack"]
        assert result["tension_level"] == "high"

    def test_defaults(self):
        result = OutputParser.parse_scene_plan({})
        assert result["available_actions"] == []
        assert result["tension_level"] == "low"


class TestParseNarrative:
    def test_plain_text(self):
        result = OutputParser.parse_narrative("You walk into the cave.")
        assert result["narrative_text"] == "You walk into the cave."
        assert result["suggested_hooks"] == []

    def test_with_hook(self):
        text = "You find a chest. [HOOK: Strange sounds from below]"
        result = OutputParser.parse_narrative(text)
        assert "Strange sounds from below" in result["suggested_hooks"]
        assert "[HOOK:" not in result["narrative_text"]

    def test_multiple_hooks(self):
        text = "Text. [HOOK: Hook one] More text. [HOOK: Hook two]"
        result = OutputParser.parse_narrative(text)
        assert len(result["suggested_hooks"]) == 2

    def test_empty_string(self):
        result = OutputParser.parse_narrative("")
        assert result["narrative_text"] == ""


class TestParseDialogue:
    def test_plain_dialogue(self):
        result = OutputParser.parse_dialogue("Welcome, traveler!")
        assert result["dialogue"] == "Welcome, traveler!"
        assert result["mood"] == "neutral"

    def test_with_mood_tag(self):
        result = OutputParser.parse_dialogue("[happy] Welcome, traveler!")
        assert result["dialogue"] == "Welcome, traveler!"
        assert result["mood"] == "happy"

    def test_angry_mood(self):
        result = OutputParser.parse_dialogue("[ANGRY] Get out!")
        assert result["mood"] == "angry"
        assert result["dialogue"] == "Get out!"


class TestExtractJsonFromText:
    def test_markdown_code_block(self):
        text = 'Some text\n```json\n{"action_type": "move"}\n```\nMore text'
        result = OutputParser.extract_json_from_text(text)
        assert result == {"action_type": "move"}

    def test_bare_json(self):
        text = 'Here is the result: {"action_type": "attack", "target": "goblin"}'
        result = OutputParser.extract_json_from_text(text)
        assert result["action_type"] == "attack"

    def test_no_json(self):
        result = OutputParser.extract_json_from_text("Just plain text without json")
        assert result is None

    def test_nested_json(self):
        text = '{"outer": {"inner": 42}}'
        result = OutputParser.extract_json_from_text(text)
        assert result["outer"]["inner"] == 42

    def test_malformed_json(self):
        text = '{"broken: json'
        result = OutputParser.extract_json_from_text(text)
        assert result is None

    def test_json_with_surrounding_text(self):
        text = 'I think the answer is {"value": 42} based on analysis'
        result = OutputParser.extract_json_from_text(text)
        assert result == {"value": 42}
