"""Character creation logic — assembles a complete character dict."""
from __future__ import annotations

import uuid
from typing import Any

from text_rpg.mechanics.ability_scores import RACIAL_BONUSES, apply_origin_bonuses, apply_racial_bonuses, modifier
from text_rpg.mechanics.leveling import HIT_DICE, proficiency_bonus
from text_rpg.mechanics.spellcasting import SPELLCASTING_ABILITY, get_spell_slots

CLASS_SAVING_THROWS: dict[str, list[str]] = {
    "fighter": ["strength", "constitution"],
    "wizard": ["intelligence", "wisdom"],
    "rogue": ["dexterity", "intelligence"],
    "cleric": ["wisdom", "charisma"],
    "barbarian": ["strength", "constitution"],
    "bard": ["dexterity", "charisma"],
    "druid": ["intelligence", "wisdom"],
    "monk": ["strength", "dexterity"],
    "paladin": ["wisdom", "charisma"],
    "ranger": ["strength", "dexterity"],
    "sorcerer": ["constitution", "charisma"],
    "warlock": ["wisdom", "charisma"],
}

CLASS_SKILL_CHOICES: dict[str, tuple[int, list[str]]] = {
    "fighter": (2, ["acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "survival"]),
    "wizard": (2, ["arcana", "history", "insight", "investigation", "medicine", "religion"]),
    "rogue": (4, ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight_of_hand", "stealth"]),
    "cleric": (2, ["history", "insight", "medicine", "persuasion", "religion"]),
    "barbarian": (2, ["animal_handling", "athletics", "intimidation", "nature", "perception", "survival"]),
    "bard": (3, ["acrobatics", "animal_handling", "arcana", "athletics", "deception", "history", "insight", "intimidation", "investigation", "medicine", "nature", "perception", "performance", "persuasion", "religion", "sleight_of_hand", "stealth", "survival"]),
    "druid": (2, ["arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"]),
    "monk": (2, ["acrobatics", "athletics", "history", "insight", "religion", "stealth"]),
    "paladin": (2, ["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"]),
    "ranger": (3, ["animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"]),
    "sorcerer": (2, ["arcana", "deception", "insight", "intimidation", "persuasion", "religion"]),
    "warlock": (2, ["arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"]),
}

CLASS_STARTING_HP: dict[str, int] = {
    "fighter": 10,
    "wizard": 6,
    "rogue": 8,
    "cleric": 8,
    "barbarian": 12,
    "bard": 8,
    "druid": 8,
    "monk": 8,
    "paladin": 10,
    "ranger": 10,
    "sorcerer": 6,
    "warlock": 8,
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
    # Barbarian
    ("barbarian", 1): ["Rage", "Unarmored Defense"],
    ("barbarian", 2): ["Reckless Attack", "Danger Sense"],
    ("barbarian", 3): ["Primal Path"],
    ("barbarian", 4): ["Ability Score Improvement"],
    ("barbarian", 5): ["Extra Attack", "Fast Movement"],
    # Bard
    ("bard", 1): ["Spellcasting", "Bardic Inspiration"],
    ("bard", 2): ["Jack of All Trades", "Song of Rest"],
    ("bard", 3): ["Bard College"],
    ("bard", 4): ["Ability Score Improvement"],
    ("bard", 5): ["Font of Inspiration"],
    # Druid
    ("druid", 1): ["Spellcasting", "Druidic"],
    ("druid", 2): ["Wild Shape"],
    ("druid", 4): ["Ability Score Improvement"],
    # Monk
    ("monk", 1): ["Martial Arts", "Unarmored Defense"],
    ("monk", 2): ["Ki"],
    ("monk", 3): ["Monastic Tradition", "Deflect Missiles"],
    ("monk", 4): ["Ability Score Improvement", "Slow Fall"],
    ("monk", 5): ["Extra Attack", "Stunning Strike"],
    # Paladin
    ("paladin", 1): ["Divine Sense", "Lay on Hands"],
    ("paladin", 2): ["Spellcasting", "Fighting Style", "Divine Smite"],
    ("paladin", 3): ["Sacred Oath"],
    ("paladin", 4): ["Ability Score Improvement"],
    ("paladin", 5): ["Extra Attack"],
    # Ranger
    ("ranger", 1): ["Favored Enemy", "Natural Explorer"],
    ("ranger", 2): ["Spellcasting", "Fighting Style"],
    ("ranger", 3): ["Ranger Archetype"],
    ("ranger", 4): ["Ability Score Improvement"],
    ("ranger", 5): ["Extra Attack"],
    # Sorcerer
    ("sorcerer", 1): ["Spellcasting", "Sorcerous Origin"],
    ("sorcerer", 2): ["Font of Magic"],
    ("sorcerer", 3): ["Metamagic"],
    ("sorcerer", 4): ["Ability Score Improvement"],
    # Warlock
    ("warlock", 1): ["Pact Magic", "Otherworldly Patron"],
    ("warlock", 2): ["Eldritch Invocations"],
    ("warlock", 3): ["Pact Boon"],
    ("warlock", 4): ["Ability Score Improvement"],
}

RACIAL_TRAITS: dict[str, list[str]] = {
    "human": ["Versatile", "Extra Language"],
    "elf": ["Darkvision", "Keen Senses", "Fey Ancestry", "Trance"],
    "dwarf": ["Darkvision", "Dwarven Resilience", "Stonecunning", "Dwarven Combat Training"],
    "halfling": ["Lucky", "Brave", "Halfling Nimbleness"],
    "half_orc": ["Darkvision", "Relentless Endurance", "Savage Attacks", "Menacing"],
    "half_elf": ["Darkvision", "Fey Ancestry", "Skill Versatility"],
    "gnome": ["Darkvision", "Gnome Cunning", "Artificer's Lore"],
    "tiefling": ["Darkvision", "Hellish Resistance", "Infernal Legacy"],
    "dragonborn": ["Breath Weapon", "Draconic Resistance", "Draconic Ancestry"],
    "goliath": ["Natural Athlete", "Stone's Endurance", "Mountain Born"],
    "aasimar": ["Darkvision", "Celestial Resistance", "Healing Hands", "Light Bearer"],
    "tabaxi": ["Darkvision", "Feline Agility", "Cat's Claws"],
    "firbolg": ["Firbolg Magic", "Hidden Step", "Speech of Beast and Leaf"],
    "kenku": ["Expert Forgery", "Kenku Training", "Mimicry"],
    "lizardfolk": ["Natural Armor", "Hungry Jaws", "Cunning Artisan", "Hold Breath"],
    "goblin": ["Darkvision", "Fury of the Small", "Nimble Escape"],
    "orc": ["Darkvision", "Aggressive", "Powerful Build", "Primal Intuition"],
    "genasi": ["Elemental Heritage", "Unending Breath", "Elemental Attunement"],
    "changeling": ["Shapechanger", "Changeling Instincts", "Unsettling Visage"],
    "warforged": ["Constructed Resilience", "Sentry's Rest", "Integrated Protection"],
    "centaur": ["Charge", "Equine Build", "Hooves", "Survivor"],
    "minotaur": ["Horns", "Goring Rush", "Hammering Horns", "Labyrinthine Recall"],
    "bugbear": ["Darkvision", "Long-Limbed", "Powerful Build", "Surprise Attack", "Sneaky"],
}

RACIAL_SIZE: dict[str, str] = {
    "human": "Medium",
    "elf": "Medium",
    "dwarf": "Medium",
    "halfling": "Small",
    "half_orc": "Medium",
    "half_elf": "Medium",
    "gnome": "Small",
    "tiefling": "Medium",
    "dragonborn": "Medium",
    "goliath": "Medium",
    "aasimar": "Medium",
    "tabaxi": "Medium",
    "firbolg": "Medium",
    "kenku": "Medium",
    "lizardfolk": "Medium",
    "goblin": "Small",
    "orc": "Medium",
    "genasi": "Medium",
    "changeling": "Medium",
    "warforged": "Medium",
    "centaur": "Large",
    "minotaur": "Large",
    "bugbear": "Large",
}

RACIAL_SPEED: dict[str, int] = {
    "human": 30,
    "elf": 30,
    "dwarf": 25,
    "halfling": 25,
    "half_orc": 30,
    "half_elf": 30,
    "gnome": 25,
    "tiefling": 30,
    "dragonborn": 30,
    "goliath": 30,
    "aasimar": 30,
    "tabaxi": 30,
    "firbolg": 30,
    "kenku": 30,
    "lizardfolk": 30,
    "goblin": 30,
    "orc": 30,
    "genasi": 30,
    "changeling": 30,
    "warforged": 30,
    "centaur": 40,
    "minotaur": 30,
    "bugbear": 30,
}


def create_character(
    name: str,
    race: str,
    char_class: str,
    ability_scores: dict[str, int],
    skill_choices: list[str],
    game_id: str,
    starting_gold: int = 0,
    origin_id: str | None = None,
    origin_primary: str | None = None,
    origin_secondary: str | None = None,
) -> dict[str, Any]:
    """Assemble a complete character dict with all computed values."""
    char_id = str(uuid.uuid4())

    # Apply racial bonuses, then origin bonuses
    final_scores = apply_racial_bonuses(ability_scores, race)
    if origin_primary and origin_secondary:
        final_scores = apply_origin_bonuses(final_scores, origin_primary, origin_secondary)

    # Calculate HP
    base_hp = CLASS_STARTING_HP.get(char_class.lower(), 8)
    con_mod = modifier(final_scores.get("constitution", 10))
    max_hp = base_hp + con_mod

    # AC (unarmored — class-specific formulas)
    dex_mod = modifier(final_scores.get("dexterity", 10))
    cls_lower = char_class.lower()
    if cls_lower == "barbarian":
        con_mod_ac = modifier(final_scores.get("constitution", 10))
        ac = 10 + dex_mod + con_mod_ac
    elif cls_lower == "monk":
        wis_mod_ac = modifier(final_scores.get("wisdom", 10))
        ac = 10 + dex_mod + wis_mod_ac
    elif cls_lower == "sorcerer":
        # Draconic Resilience: 13 + DEX mod
        ac = 13 + dex_mod
    else:
        ac = 10 + dex_mod

    # Proficiency bonus
    prof_bonus = proficiency_bonus(1)

    # Speed and size
    speed = RACIAL_SPEED.get(race.lower(), 30)
    size = RACIAL_SIZE.get(race.lower(), "Medium")

    # Class features at level 1
    features = list(CLASS_FEATURES.get((char_class.lower(), 1), []))

    # Saving throw proficiencies
    save_profs = CLASS_SAVING_THROWS.get(char_class.lower(), [])

    # Spellcasting setup
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
        "size": size,
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
        "origin_id": origin_id,
    }
