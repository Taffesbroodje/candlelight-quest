"""Tests for spell creation input patterns — combine, invent, combinations."""
from __future__ import annotations

import pytest

from text_rpg.cli.input_handler import InputHandler


@pytest.fixture
def handler():
    return InputHandler()


class TestCombineSpellPattern:
    """Test the combine_spell regex pattern."""

    @pytest.mark.parametrize("input_text,element_a,element_b", [
        ("combine fire and wind", "fire", "wind"),
        ("combine fire with wind", "fire", "wind"),
        ("combine fire + wind", "fire", "wind"),
        ("merge water and earth", "water", "earth"),
        ("fuse lightning with water", "lightning", "water"),
        ("blend acid and wind", "acid", "wind"),
        ("Combine Fire And Cold", "Fire", "Cold"),
        ("combine thunder and earth", "thunder", "earth"),
        ("combine necrotic with cold", "necrotic", "cold"),
    ])
    def test_combine_spell_matches(self, handler, input_text, element_a, element_b):
        result = handler.classify(input_text)
        assert result["action_type"] == "combine_spell"
        assert result["parameters"]["element_a"] == element_a
        assert result["parameters"]["element_b"] == element_b

    def test_combine_spell_not_meta(self, handler):
        result = handler.classify("combine fire and wind")
        assert result["is_meta"] is False

    @pytest.mark.parametrize("input_text", [
        "combine",
        "combine fire",
        "combine fire and",
    ])
    def test_combine_spell_incomplete(self, handler, input_text):
        result = handler.classify(input_text)
        assert result["action_type"] != "combine_spell"

    def test_combine_breaks_conversation(self, handler):
        assert handler.should_break_conversation("combine fire and wind")


class TestInventSpellPattern:
    """Test the invent_spell regex pattern."""

    @pytest.mark.parametrize("input_text,concept", [
        ("invent spell that creates a wall of thorns", "creates a wall of thorns"),
        ("invent spell to freeze enemies in place", "freeze enemies in place"),
        ("invent spell of healing rain", "healing rain"),
        ("create spell that shoots lightning bolts", "shoots lightning bolts"),
        ("design spell to turn invisible", "turn invisible"),
        ("research spell that summons fire", "summons fire"),
        ("invent a spell that makes a shield", "makes a shield"),
        ("Invent Spell That Explodes", "Explodes"),
    ])
    def test_invent_spell_matches(self, handler, input_text, concept):
        result = handler.classify(input_text)
        assert result["action_type"] == "invent_spell"
        assert result["parameters"]["spell_concept"] == concept

    def test_invent_spell_not_meta(self, handler):
        result = handler.classify("invent spell that shoots fire")
        assert result["is_meta"] is False

    @pytest.mark.parametrize("input_text", [
        "invent",
        "invent something",
    ])
    def test_invent_spell_no_match_without_spell_keyword(self, handler, input_text):
        result = handler.classify(input_text)
        assert result["action_type"] != "invent_spell"

    def test_invent_breaks_conversation(self, handler):
        assert handler.should_break_conversation("invent spell that creates ice")


class TestCombinationsMetaPattern:
    """Test the combinations meta command pattern."""

    @pytest.mark.parametrize("input_text", [
        "combinations",
        "combos",
        "combo",
        "discovered spells",
        "custom spells",
        "inventions",
    ])
    def test_combinations_matches(self, handler, input_text):
        result = handler.classify(input_text)
        assert result["action_type"] == "combinations"
        assert result["is_meta"] is True

    def test_combinations_does_not_break_conversation(self, handler):
        # Meta commands don't break conversation
        assert not handler.should_break_conversation("combinations")


class TestPatternOrdering:
    """Ensure combine/invent don't conflict with craft or cast patterns."""

    def test_craft_still_works(self, handler):
        result = handler.classify("craft iron sword")
        assert result["action_type"] == "craft"

    def test_cast_still_works(self, handler):
        result = handler.classify("cast fire bolt at goblin")
        assert result["action_type"] == "cast_spell"
        assert result["target"] == "fire bolt"
        assert result["parameters"]["spell_target"] == "goblin"

    def test_combine_takes_priority_over_craft(self, handler):
        # "combine fire and wind" should match combine_spell, not craft
        result = handler.classify("combine fire and wind")
        assert result["action_type"] == "combine_spell"

    def test_create_spell_matches_invent(self, handler):
        # "create spell that..." should match invent_spell
        result = handler.classify("create spell that burns everything")
        assert result["action_type"] == "invent_spell"

    def test_make_still_matches_craft(self, handler):
        # "make iron sword" should match craft, not invent_spell
        result = handler.classify("make iron sword")
        assert result["action_type"] == "craft"
