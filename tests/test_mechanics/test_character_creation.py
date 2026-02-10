"""Tests for src/text_rpg/mechanics/character_creation.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.ability_scores import RACIAL_BONUSES, modifier
from text_rpg.mechanics.character_creation import (
    CLASS_FEATURES,
    CLASS_SAVING_THROWS,
    CLASS_STARTING_HP,
    RACIAL_SPEED,
    create_character,
)

SCORES = {
    "strength": 15, "dexterity": 14, "constitution": 13,
    "intelligence": 12, "wisdom": 10, "charisma": 8,
}


class TestCreateCharacter:
    @pytest.mark.parametrize("cls, expected_hp_base, race, expected_speed", [
        ("fighter", 10, "dwarf", 25),
        ("wizard", 6, "elf", 30),
        ("rogue", 8, "halfling", 25),
        ("cleric", 8, "human", 30),
    ])
    def test_class_race_combos(self, cls, expected_hp_base, race, expected_speed):
        char = create_character("Hero", race, cls, dict(SCORES), ["athletics"], "g1")
        assert char["char_class"] == cls
        assert char["race"] == race
        assert char["speed"] == expected_speed
        # HP = base + con_mod (after racial bonuses)
        bonuses = RACIAL_BONUSES.get(race, {})
        final_con = SCORES["constitution"] + bonuses.get("constitution", 0)
        assert char["hp_max"] == expected_hp_base + modifier(final_con)

    @pytest.mark.parametrize("race", ["human", "elf", "dwarf", "halfling", "half_orc"])
    def test_racial_bonuses_applied(self, race):
        char = create_character("Hero", race, "fighter", dict(SCORES), ["athletics"], "g1")
        bonuses = RACIAL_BONUSES.get(race, {})
        for ability, bonus in bonuses.items():
            assert char["ability_scores"][ability] == SCORES[ability] + bonus

    def test_class_features_level_1(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), ["athletics"], "g1")
        assert "Fighting Style" in char["class_features"]
        assert "Second Wind" in char["class_features"]

    def test_saving_throw_proficiencies(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), ["athletics"], "g1")
        assert char["saving_throw_proficiencies"] == ["strength", "constitution"]

    def test_spellcaster_spell_slots(self):
        char = create_character("Wiz", "elf", "wizard", dict(SCORES), ["arcana"], "g1")
        assert char["spellcasting_ability"] == "intelligence"
        assert char["spell_slots_max"] == {1: 2}
        assert char["spell_slots_remaining"] == {1: 2}

    def test_non_caster_no_slots(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), ["athletics"], "g1")
        assert char["spellcasting_ability"] is None
        assert char["spell_slots_max"] == {}

    def test_unique_id(self):
        c1 = create_character("A", "human", "fighter", dict(SCORES), [], "g1")
        c2 = create_character("B", "human", "fighter", dict(SCORES), [], "g1")
        assert c1["id"] != c2["id"]

    def test_initial_values(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1")
        assert char["level"] == 1
        assert char["xp"] == 0
        assert char["hp_current"] == char["hp_max"]
        assert char["hp_temp"] == 0
        assert char["conditions"] == []
        assert char["hit_dice_remaining"] == 1
        assert char["equipped_weapon_id"] is None
        assert char["concentration_spell"] is None

    def test_survival_needs(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1")
        assert char["hunger"] == 100
        assert char["thirst"] == 100
        assert char["warmth"] == 80
        assert char["morale"] == 75

    def test_starting_gold(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1", starting_gold=100)
        assert char["gold"] == 100

    def test_default_gold_zero(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1")
        assert char["gold"] == 0

    def test_ac_unarmored(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1")
        # Human: DEX stays 14+1=15, mod=2. AC = 10+2 = 12
        dex_mod = modifier(char["ability_scores"]["dexterity"])
        assert char["ac"] == 10 + dex_mod

    def test_cleric_spell_slots(self):
        char = create_character("Cleric", "human", "cleric", dict(SCORES), ["insight"], "g1")
        assert char["spellcasting_ability"] == "wisdom"
        assert char["spell_slots_max"] == {1: 2}
