"""Tests for src/text_rpg/mechanics/multiclassing.py."""
from __future__ import annotations

import json

import pytest

from text_rpg.mechanics.multiclassing import (
    can_multiclass,
    format_class_display,
    get_total_level,
)


class TestCanMulticlass:
    def test_meets_prerequisites(self):
        scores = {"strength": 15, "dexterity": 14, "constitution": 13,
                  "intelligence": 12, "wisdom": 10, "charisma": 8}
        ok, reason = can_multiclass(scores, "fighter", {"wizard": 3})
        # Fighter needs STR 13+, wizard needs INT 13+ — but INT is 12
        assert ok is False

    def test_meets_both_prereqs(self):
        scores = {"strength": 14, "dexterity": 14, "constitution": 13,
                  "intelligence": 14, "wisdom": 10, "charisma": 8}
        ok, _ = can_multiclass(scores, "fighter", {"wizard": 3})
        assert ok is True

    def test_below_target_prereq(self):
        scores = {"strength": 10, "dexterity": 14, "constitution": 13,
                  "intelligence": 14, "wisdom": 10, "charisma": 8}
        ok, reason = can_multiclass(scores, "fighter", {"wizard": 3})
        assert ok is False
        assert "strength" in reason.lower()

    def test_already_has_class(self):
        scores = {"strength": 15}
        ok, reason = can_multiclass(scores, "fighter", {"fighter": 3})
        assert ok is True
        assert "already" in reason.lower()

    def test_max_classes(self):
        scores = {"strength": 15, "dexterity": 15, "intelligence": 15}
        ok, reason = can_multiclass(scores, "cleric", {"fighter": 3, "wizard": 2})
        assert ok is False
        assert "maximum" in reason.lower()

    def test_bard_charisma_prereq(self):
        scores = {"charisma": 14, "strength": 14}
        ok, _ = can_multiclass(scores, "bard", {"fighter": 3})
        assert ok is True

    def test_bard_charisma_too_low(self):
        scores = {"charisma": 10, "strength": 14}
        ok, reason = can_multiclass(scores, "bard", {"fighter": 3})
        assert ok is False
        assert "charisma" in reason.lower()

    def test_paladin_dual_prerequisite(self):
        # Paladin needs STR 13+ AND CHA 13+
        scores = {"strength": 14, "charisma": 14, "dexterity": 14}
        ok, _ = can_multiclass(scores, "paladin", {"rogue": 3})
        assert ok is True

    def test_paladin_missing_one_prereq(self):
        # Has STR but not CHA
        scores = {"strength": 14, "charisma": 10, "dexterity": 14}
        ok, reason = can_multiclass(scores, "paladin", {"rogue": 3})
        assert ok is False
        assert "charisma" in reason.lower()

    def test_ranger_dual_prerequisite(self):
        # Ranger needs DEX 13+ AND WIS 13+
        scores = {"dexterity": 14, "wisdom": 14, "strength": 14}
        ok, _ = can_multiclass(scores, "ranger", {"fighter": 3})
        assert ok is True

    def test_ranger_missing_wisdom(self):
        scores = {"dexterity": 14, "wisdom": 10, "strength": 14}
        ok, reason = can_multiclass(scores, "ranger", {"fighter": 3})
        assert ok is False
        assert "wisdom" in reason.lower()

    def test_unknown_class(self):
        scores = {"strength": 15}
        ok, reason = can_multiclass(scores, "necromancer", {"fighter": 3})
        assert ok is False
        assert "unknown" in reason.lower()

    def test_json_string_scores(self):
        scores_json = json.dumps({"strength": 15, "dexterity": 14,
                                   "intelligence": 14})
        ok, _ = can_multiclass(scores_json, "fighter", {"wizard": 3})
        assert ok is True


class TestGetTotalLevel:
    def test_dict(self):
        assert get_total_level({"fighter": 3, "wizard": 2}) == 5

    def test_json_string(self):
        assert get_total_level(json.dumps({"fighter": 3})) == 3

    def test_empty(self):
        assert get_total_level({}) == 0

    def test_none(self):
        assert get_total_level(None) == 0


class TestFormatClassDisplay:
    def test_single_class(self):
        assert format_class_display({"fighter": 5}) == "Fighter 5"

    def test_multiclass_sorted(self):
        result = format_class_display({"wizard": 2, "fighter": 3})
        assert result == "Fighter 3 / Wizard 2"

    def test_empty_with_primary(self):
        assert format_class_display({}, "fighter") == "Fighter"

    def test_empty_no_primary(self):
        assert format_class_display({}, "") == "Unknown"

    def test_json_string(self):
        result = format_class_display(json.dumps({"rogue": 4}))
        assert result == "Rogue 4"
