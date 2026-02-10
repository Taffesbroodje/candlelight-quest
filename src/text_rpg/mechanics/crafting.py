"""Crafting and trade skill mechanics — pure calculations, no I/O.

Trade skills: alchemy, smithing, herbalism, enchanting, cooking
Each skill has levels 1-10, with XP thresholds.
Recipes have skill/level requirements and material costs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from text_rpg.mechanics.dice import roll

# XP required to reach each trade skill level
TRADE_SKILL_XP: dict[int, int] = {
    1: 0, 2: 50, 3: 150, 4: 300, 5: 500,
    6: 750, 7: 1050, 8: 1400, 9: 1800, 10: 2500,
}

# Base training cost in gold to learn a trade skill from an NPC
TRAINING_COST: dict[str, int] = {
    "alchemy": 25,
    "smithing": 30,
    "herbalism": 15,
    "enchanting": 50,
    "cooking": 10,
}

# Which ability score affects each trade skill
TRADE_SKILL_ABILITY: dict[str, str] = {
    "alchemy": "intelligence",
    "smithing": "strength",
    "herbalism": "wisdom",
    "enchanting": "intelligence",
    "cooking": "wisdom",
}

TRADE_SKILL_DESCRIPTIONS: dict[str, str] = {
    "alchemy": "Brew potions, acids, and alchemical substances",
    "smithing": "Forge and repair weapons, armor, and metal goods",
    "herbalism": "Gather and prepare medicinal herbs and poultices",
    "enchanting": "Imbue items with magical properties",
    "cooking": "Prepare meals that restore needs and grant temporary bonuses",
}


@dataclass
class Recipe:
    id: str
    name: str
    skill: str
    min_level: int
    materials: dict[str, int]  # item_id -> quantity
    result_item: str
    result_quantity: int = 1
    xp_reward: int = 10
    dc: int = 10
    description: str = ""


# All known recipes
RECIPES: dict[str, Recipe] = {
    # Alchemy
    "brew_healing_potion": Recipe(
        id="brew_healing_potion", name="Brew Healing Potion",
        skill="alchemy", min_level=1,
        materials={"healing_herb": 2},
        result_item="healing_potion", xp_reward=15, dc=12,
        description="Combine healing herbs into a potion of healing.",
    ),
    "brew_antidote": Recipe(
        id="brew_antidote", name="Brew Antidote",
        skill="alchemy", min_level=2,
        materials={"healing_herb": 1, "moonpetal": 1},
        result_item="antidote", xp_reward=20, dc=14,
        description="Create an antidote to cure poisons.",
    ),
    "brew_fire_flask": Recipe(
        id="brew_fire_flask", name="Brew Alchemist's Fire",
        skill="alchemy", min_level=3,
        materials={"sulfur": 2, "flask": 1},
        result_item="alchemists_fire", xp_reward=25, dc=15,
        description="Create a flask of volatile alchemist's fire.",
    ),
    # Smithing
    "repair_weapon": Recipe(
        id="repair_weapon", name="Repair Weapon",
        skill="smithing", min_level=1,
        materials={"iron_ingot": 1},
        result_item="_repair_weapon", xp_reward=10, dc=10,
        description="Repair a damaged weapon to restore its effectiveness.",
    ),
    "forge_dagger": Recipe(
        id="forge_dagger", name="Forge Dagger",
        skill="smithing", min_level=1,
        materials={"iron_ingot": 1},
        result_item="dagger", xp_reward=15, dc=12,
        description="Forge a simple but effective dagger.",
    ),
    "forge_shortsword": Recipe(
        id="forge_shortsword", name="Forge Shortsword",
        skill="smithing", min_level=3,
        materials={"iron_ingot": 2, "leather_strip": 1},
        result_item="shortsword", xp_reward=25, dc=15,
        description="Forge a shortsword with a leather-wrapped hilt.",
    ),
    # Herbalism
    "gather_herbs": Recipe(
        id="gather_herbs", name="Gather Healing Herbs",
        skill="herbalism", min_level=1,
        materials={},  # No materials needed, just skill check
        result_item="healing_herb", result_quantity=2, xp_reward=10, dc=10,
        description="Forage for healing herbs in the wilderness.",
    ),
    "make_poultice": Recipe(
        id="make_poultice", name="Make Poultice",
        skill="herbalism", min_level=2,
        materials={"healing_herb": 3},
        result_item="poultice", xp_reward=15, dc=12,
        description="Create a healing poultice from gathered herbs.",
    ),
    # Cooking
    "cook_meal": Recipe(
        id="cook_meal", name="Cook a Meal",
        skill="cooking", min_level=1,
        materials={"rations": 1},
        result_item="cooked_meal", xp_reward=10, dc=8,
        description="Prepare a hearty meal from rations.",
    ),
    "cook_stew": Recipe(
        id="cook_stew", name="Cook Hearty Stew",
        skill="cooking", min_level=2,
        materials={"rations": 2, "waterskin": 1},
        result_item="hearty_stew", xp_reward=15, dc=12,
        description="A warming stew that restores hunger and boosts morale.",
    ),
    # -- Enchanting (8 new) --
    "enchant_fire_weapon": Recipe(
        id="enchant_fire_weapon", name="Enchant Fire Weapon",
        skill="enchanting", min_level=3,
        materials={"arcane_dust": 2, "firepowder": 1},
        result_item="fire_longsword", xp_reward=50, dc=16,
        description="Imbue a weapon with fire magic, wreathing it in flame.",
    ),
    "enchant_frost_weapon": Recipe(
        id="enchant_frost_weapon", name="Enchant Frost Weapon",
        skill="enchanting", min_level=3,
        materials={"arcane_dust": 2, "moonpetal": 2},
        result_item="frost_shortsword", xp_reward=50, dc=16,
        description="Imbue a weapon with frost magic, coating it in rime.",
    ),
    "enchant_lightning_weapon": Recipe(
        id="enchant_lightning_weapon", name="Enchant Lightning Weapon",
        skill="enchanting", min_level=4,
        materials={"soul_gem": 1, "arcane_dust": 3},
        result_item="lightning_rapier", xp_reward=60, dc=18,
        description="Channel lightning into a weapon, making it crackle with electricity.",
    ),
    "enchant_sharpness": Recipe(
        id="enchant_sharpness", name="Enchant Sharpness",
        skill="enchanting", min_level=5,
        materials={"dragon_scale_fragment": 1, "arcane_dust": 2},
        result_item="sharp_greataxe", xp_reward=75, dc=20,
        description="Hone a weapon to supernatural sharpness with dragon-scale magic.",
    ),
    "enchant_protection_armor": Recipe(
        id="enchant_protection_armor", name="Enchant Protection Armor",
        skill="enchanting", min_level=3,
        materials={"arcane_dust": 2, "enchanted_thread": 1},
        result_item="armor_of_protection", xp_reward=50, dc=16,
        description="Weave protective enchantments into armor, granting +1 AC.",
    ),
    "enchant_resistance_armor": Recipe(
        id="enchant_resistance_armor", name="Enchant Resistance Armor",
        skill="enchanting", min_level=4,
        materials={"soul_gem": 1, "enchanted_thread": 2},
        result_item="ring_of_resistance", xp_reward=60, dc=18,
        description="Forge a ring of resistance from a soul gem.",
    ),
    "enchant_ring": Recipe(
        id="enchant_ring", name="Enchant Ring",
        skill="enchanting", min_level=5,
        materials={"soul_gem": 1, "enchanted_thread": 1, "arcane_dust": 3},
        result_item="ring_of_resistance", xp_reward=75, dc=20,
        description="Create a powerful enchanted ring.",
    ),
    "scribe_scroll": Recipe(
        id="scribe_scroll", name="Scribe Scroll",
        skill="enchanting", min_level=2,
        materials={"arcane_dust": 1, "flask": 1},
        result_item="_scroll", xp_reward=30, dc=14,
        description="Inscribe a known spell onto a scroll for single use.",
    ),
    # -- Alchemy (3 new) --
    "brew_mana_potion": Recipe(
        id="brew_mana_potion", name="Brew Mana Potion",
        skill="alchemy", min_level=3,
        materials={"moonpetal": 2, "arcane_dust": 1},
        result_item="mana_potion", xp_reward=25, dc=15,
        description="Brew a potion that restores magical energy.",
    ),
    "brew_poison": Recipe(
        id="brew_poison", name="Brew Poison Vial",
        skill="alchemy", min_level=2,
        materials={"nightshade": 2, "flask": 1},
        result_item="poison_vial", xp_reward=20, dc=14,
        description="Distill nightshade into a concentrated poison.",
    ),
    "brew_smoke_bomb": Recipe(
        id="brew_smoke_bomb", name="Brew Smoke Bomb",
        skill="alchemy", min_level=2,
        materials={"sulfur": 1, "firepowder": 1, "flask": 1},
        result_item="smoke_bomb", xp_reward=20, dc=13,
        description="Create a small ball that releases obscuring smoke.",
    ),
    # -- Smithing (3 new) --
    "forge_silver_coating": Recipe(
        id="forge_silver_coating", name="Forge Silver Weapon Coating",
        skill="smithing", min_level=2,
        materials={"silver_ore": 2},
        result_item="silver_weapon_coating", xp_reward=20, dc=14,
        description="Melt silver ore into a weapon coating solution.",
    ),
    "forge_reinforced_chain": Recipe(
        id="forge_reinforced_chain", name="Forge Reinforced Chain Shirt",
        skill="smithing", min_level=4,
        materials={"iron_ingot": 3, "leather_strip": 2},
        result_item="reinforced_chain_shirt", xp_reward=40, dc=17,
        description="Forge a reinforced chain shirt with extra protection.",
    ),
    "forge_longsword": Recipe(
        id="forge_longsword", name="Forge Longsword",
        skill="smithing", min_level=3,
        materials={"iron_ingot": 3, "leather_strip": 1},
        result_item="longsword", xp_reward=30, dc=15,
        description="Forge a well-balanced longsword.",
    ),
    # -- Cooking (3 new) --
    "cook_feast": Recipe(
        id="cook_feast", name="Prepare a Grand Feast",
        skill="cooking", min_level=4,
        materials={"rations": 5, "waterskin": 2},
        result_item="feast", xp_reward=30, dc=16,
        description="Prepare a lavish meal that fully restores hunger and boosts morale.",
    ),
    "cook_travelers_rations": Recipe(
        id="cook_travelers_rations", name="Prepare Traveler's Rations",
        skill="cooking", min_level=2,
        materials={"rations": 3},
        result_item="travelers_rations", result_quantity=3, xp_reward=15, dc=12,
        description="Prepare compact, long-lasting rations for extended journeys.",
    ),
    "cook_energy_bar": Recipe(
        id="cook_energy_bar", name="Make Energy Bars",
        skill="cooking", min_level=1,
        materials={"rations": 1},
        result_item="energy_bar", result_quantity=2, xp_reward=10, dc=10,
        description="Press nuts and honey into portable energy bars.",
    ),
}


def can_craft(recipe: Recipe, skill_level: int, materials: dict[str, int]) -> tuple[bool, str]:
    """Check if crafting is possible. Returns (can_craft, reason)."""
    if skill_level < recipe.min_level:
        return False, f"Requires {recipe.skill} level {recipe.min_level} (you have {skill_level})."

    for mat_id, required in recipe.materials.items():
        available = materials.get(mat_id, 0)
        if available < required:
            return False, f"Need {required}x {mat_id.replace('_', ' ')} (have {available})."

    return True, ""


def attempt_craft(
    recipe: Recipe,
    skill_level: int,
    ability_modifier: int,
) -> tuple[bool, int]:
    """Attempt to craft. Returns (success, roll_total).

    DC is recipe.dc, modified by skill level bonus.
    Roll: 1d20 + ability_modifier + (skill_level // 2)
    """
    skill_bonus = skill_level // 2
    result = roll("1d20")
    total = result.individual_rolls[0] + ability_modifier + skill_bonus

    success = total >= recipe.dc
    return success, total


def trade_skill_level_for_xp(xp: int) -> int:
    """Determine trade skill level from total XP."""
    level = 1
    for lvl in sorted(TRADE_SKILL_XP.keys()):
        if xp >= TRADE_SKILL_XP[lvl]:
            level = lvl
        else:
            break
    return level


def can_level_up_trade_skill(current_level: int, current_xp: int) -> bool:
    """Check if a trade skill can level up."""
    if current_level >= 10:
        return False
    next_level = current_level + 1
    return current_xp >= TRADE_SKILL_XP.get(next_level, 999999)


def get_available_recipes(skill_name: str, skill_level: int) -> list[Recipe]:
    """Get recipes available at a given skill level."""
    return [r for r in RECIPES.values() if r.skill == skill_name and r.min_level <= skill_level]
