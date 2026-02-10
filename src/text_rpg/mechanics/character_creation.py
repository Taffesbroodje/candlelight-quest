"""Character creation logic — assembles a complete character dict."""
from __future__ import annotations

import uuid
from typing import Any

from text_rpg.mechanics.ability_scores import RACIAL_BONUSES, apply_racial_bonuses, modifier
from text_rpg.mechanics.leveling import HIT_DICE, proficiency_bonus
from text_rpg.mechanics.spellcasting import SPELLCASTING_ABILITY, get_spell_slots

CLASS_SAVING_THROWS: dict[str, list[str]] = {
    "fighter": ["strength", "constitution"],
    "wizard": ["intelligence", "wisdom"],
    "rogue": ["dexterity", "intelligence"],
    "cleric": ["wisdom", "charisma"],
}

CLASS_SKILL_CHOICES: dict[str, tuple[int, list[str]]] = {
    "fighter": (2, ["acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "survival"]),
    "wizard": (2, ["arcana", "history", "insight", "investigation", "medicine", "religion"]),
    "rogue": (4, ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight_of_hand", "stealth"]),
    "cleric": (2, ["history", "insight", "medicine", "persuasion", "religion"]),
}

CLASS_STARTING_HP: dict[str, int] = {
    "fighter": 10,
    "wizard": 6,
    "rogue": 8,
    "cleric": 8,
}

CLASS_FEATURES: dict[tuple[str, int], list[str]] = {
    ("fighter", 1): ["Fighting Style", "Second Wind"],
    ("fighter", 2): ["Action Surge"],
    ("fighter", 3): ["Martial Archetype"],
    ("fighter", 4): ["Ability Score Improvement"],
    ("fighter", 5): ["Extra Attack"],
    ("wizard", 1): ["Spellcasting", "Arcane Recovery"],
    ("wizard", 2): ["Arcane Tradition"],
    ("wizard", 4): ["Ability Score Improvement"],
    ("rogue", 1): ["Expertise", "Sneak Attack", "Thieves' Cant"],
    ("rogue", 2): ["Cunning Action"],
    ("rogue", 3): ["Roguish Archetype"],
    ("rogue", 4): ["Ability Score Improvement"],
    ("rogue", 5): ["Uncanny Dodge"],
    ("cleric", 1): ["Spellcasting", "Divine Domain"],
    ("cleric", 2): ["Channel Divinity"],
    ("cleric", 4): ["Ability Score Improvement"],
    ("cleric", 5): ["Destroy Undead"],
}

RACIAL_TRAITS: dict[str, list[str]] = {
    "human": ["Versatile", "Extra Language"],
    "elf": ["Darkvision", "Keen Senses", "Fey Ancestry", "Trance"],
    "dwarf": ["Darkvision", "Dwarven Resilience", "Stonecunning", "Dwarven Combat Training"],
    "halfling": ["Lucky", "Brave", "Halfling Nimbleness"],
    "half_orc": ["Darkvision", "Relentless Endurance", "Savage Attacks", "Menacing"],
}

RACIAL_SPEED: dict[str, int] = {
    "human": 30,
    "elf": 30,
    "dwarf": 25,
    "halfling": 25,
    "half_orc": 30,
}


def create_character(
    name: str,
    race: str,
    char_class: str,
    ability_scores: dict[str, int],
    skill_choices: list[str],
    game_id: str,
    starting_gold: int = 0,
) -> dict[str, Any]:
    """Assemble a complete character dict with all computed values."""
    char_id = str(uuid.uuid4())

    # Apply racial bonuses
    final_scores = apply_racial_bonuses(ability_scores, race)

    # Calculate HP
    base_hp = CLASS_STARTING_HP.get(char_class.lower(), 8)
    con_mod = modifier(final_scores.get("constitution", 10))
    max_hp = base_hp + con_mod

    # AC (unarmored: 10 + DEX)
    dex_mod = modifier(final_scores.get("dexterity", 10))
    ac = 10 + dex_mod

    # Proficiency bonus
    prof_bonus = proficiency_bonus(1)

    # Speed
    speed = RACIAL_SPEED.get(race.lower(), 30)

    # Class features at level 1
    features = list(CLASS_FEATURES.get((char_class.lower(), 1), []))

    # Saving throw proficiencies
    save_profs = CLASS_SAVING_THROWS.get(char_class.lower(), [])

    # Spellcasting setup
    cls_lower = char_class.lower()
    casting_ability = SPELLCASTING_ABILITY.get(cls_lower)
    spell_slots_max = get_spell_slots(cls_lower, 1) if casting_ability else {}
    spell_slots_remaining = dict(spell_slots_max)

    return {
        "id": char_id,
        "name": name,
        "race": race.lower(),
        "char_class": char_class.lower(),
        "level": 1,
        "xp": 0,
        "ability_scores": final_scores,
        "hp_current": max_hp,
        "hp_max": max_hp,
        "hp_temp": 0,
        "ac": ac,
        "proficiency_bonus": prof_bonus,
        "skill_proficiencies": skill_choices,
        "saving_throw_proficiencies": save_profs,
        "class_features": features,
        "equipped_weapon_id": None,
        "equipped_armor_id": None,
        "conditions": [],
        "hit_dice_remaining": 1,
        "speed": speed,
        "gold": starting_gold,
        "hunger": 100,
        "thirst": 100,
        "warmth": 80,
        "morale": 75,
        "game_id": game_id,
        "spellcasting_ability": casting_ability,
        "spell_slots_remaining": spell_slots_remaining,
        "spell_slots_max": spell_slots_max,
        "concentration_spell": None,
    }
