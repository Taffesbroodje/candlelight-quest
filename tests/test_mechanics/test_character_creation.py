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
        ("barbarian", 12, "human", 30),
        ("bard", 8, "elf", 30),
        ("druid", 8, "human", 30),
        ("monk", 8, "human", 30),
        ("paladin", 10, "dwarf", 25),
        ("ranger", 10, "human", 30),
        ("sorcerer", 6, "halfling", 25),
        ("warlock", 8, "half_orc", 30),
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

    def test_origin_id_stored(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1", origin_id="noble")
        assert char["origin_id"] == "noble"

    def test_origin_id_none_by_default(self):
        char = create_character("Hero", "human", "fighter", dict(SCORES), [], "g1")
        assert char["origin_id"] is None

    def test_origin_bonuses_applied(self):
        char = create_character(
            "Hero", "human", "fighter", dict(SCORES), [], "g1",
            origin_primary="strength", origin_secondary="charisma",
        )
        # Human: STR 15+1(racial)+2(origin) = 18, CHA 8+1(racial)+1(origin) = 10
        assert char["ability_scores"]["strength"] == 18
        assert char["ability_scores"]["charisma"] == 10

    def test_origin_bonuses_stacks_with_racial(self):
        # Dwarf gets CON+2 racial. Origin gives CON+2, STR+1.
        char = create_character(
            "Hero", "dwarf", "fighter", dict(SCORES), [], "g1",
            origin_primary="constitution", origin_secondary="strength",
        )
        # CON: 13 + 2(racial) + 2(origin) = 17
        assert char["ability_scores"]["constitution"] == 17
        # STR: 15 + 0(racial) + 1(origin) = 16
        assert char["ability_scores"]["strength"] == 16

    def test_origin_bonuses_cap_at_20(self):
        high_scores = {
            "strength": 15, "dexterity": 15, "constitution": 15,
            "intelligence": 15, "wisdom": 15, "charisma": 15,
        }
        # Half-orc: STR+2, CON+1. Origin: STR+2, CON+1.
        # STR: 15 + 2 + 2 = 19 (under cap)
        # CON: 15 + 1 + 1 = 17
        char = create_character(
            "Hero", "half_orc", "fighter", dict(high_scores), [], "g1",
            origin_primary="strength", origin_secondary="constitution",
        )
        assert char["ability_scores"]["strength"] == 19
        assert char["ability_scores"]["constitution"] == 17

    def test_no_origin_bonuses_when_not_provided(self):
        char = create_character("Hero", "elf", "wizard", dict(SCORES), [], "g1")
        # Elf: DEX+2 only
        assert char["ability_scores"]["dexterity"] == SCORES["dexterity"] + 2
        assert char["ability_scores"]["strength"] == SCORES["strength"]

    def test_barbarian_unarmored_defense(self):
        # Barbarian: AC = 10 + DEX mod + CON mod
        char = create_character("Barb", "human", "barbarian", dict(SCORES), ["athletics"], "g1")
        # Human: DEX 14+1=15 mod=2, CON 13+1=14 mod=2. AC = 10 + 2 + 2 = 14
        dex_mod = modifier(char["ability_scores"]["dexterity"])
        con_mod = modifier(char["ability_scores"]["constitution"])
        assert char["ac"] == 10 + dex_mod + con_mod

    def test_monk_unarmored_defense(self):
        # Monk: AC = 10 + DEX mod + WIS mod
        char = create_character("Monk", "human", "monk", dict(SCORES), ["acrobatics"], "g1")
        dex_mod = modifier(char["ability_scores"]["dexterity"])
        wis_mod = modifier(char["ability_scores"]["wisdom"])
        assert char["ac"] == 10 + dex_mod + wis_mod

    def test_sorcerer_draconic_ac(self):
        # Sorcerer (Draconic): AC = 13 + DEX mod
        char = create_character("Sorc", "human", "sorcerer", dict(SCORES), ["arcana"], "g1")
        dex_mod = modifier(char["ability_scores"]["dexterity"])
        assert char["ac"] == 13 + dex_mod

    def test_bard_spell_slots(self):
        char = create_character("Bard", "human", "bard", dict(SCORES), ["performance"], "g1")
        assert char["spellcasting_ability"] == "charisma"
        assert char["spell_slots_max"] == {1: 2}

    def test_paladin_no_slots_at_level_1(self):
        char = create_character("Pal", "human", "paladin", dict(SCORES), ["religion"], "g1")
        assert char["spellcasting_ability"] == "charisma"
        assert char["spell_slots_max"] == {}

    def test_warlock_pact_slots(self):
        char = create_character("Lock", "human", "warlock", dict(SCORES), ["arcana"], "g1")
        assert char["spellcasting_ability"] == "charisma"
        assert char["spell_slots_max"] == {1: 1}

    def test_barbarian_features_level_1(self):
        char = create_character("Barb", "human", "barbarian", dict(SCORES), ["athletics"], "g1")
        assert "Rage" in char["class_features"]
        assert "Unarmored Defense" in char["class_features"]

    def test_monk_features_level_1(self):
        char = create_character("Monk", "human", "monk", dict(SCORES), ["acrobatics"], "g1")
        assert "Martial Arts" in char["class_features"]
        assert "Unarmored Defense" in char["class_features"]

    def test_warlock_features_level_1(self):
        char = create_character("Lock", "human", "warlock", dict(SCORES), ["arcana"], "g1")
        assert "Pact Magic" in char["class_features"]
        assert "Otherworldly Patron" in char["class_features"]
