"""Spellcasting mechanics — pure functions, no I/O."""
from __future__ import annotations

import math

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.combat_math import attack_roll, damage_roll
from text_rpg.mechanics.dice import DiceResult, roll

SPELLCASTING_ABILITY: dict[str, str] = {
    "wizard": "intelligence",
    "cleric": "wisdom",
}

# Spell slots by class and character level (levels 1-5, spell levels 1-3)
SPELL_SLOTS: dict[str, dict[int, dict[int, int]]] = {
    "wizard": {
        1: {1: 2},
        2: {1: 3},
        3: {1: 4, 2: 2},
        4: {1: 4, 2: 3},
        5: {1: 4, 2: 3, 3: 2},
    },
    "cleric": {
        1: {1: 2},
        2: {1: 3},
        3: {1: 4, 2: 2},
        4: {1: 4, 2: 3},
        5: {1: 4, 2: 3, 3: 2},
    },
}

CANTRIP_SCALING_LEVELS = [5, 11, 17]


def get_spell_slots(class_name: str, level: int) -> dict[int, int]:
    """Return max spell slots for a class at a given character level."""
    class_slots = SPELL_SLOTS.get(class_name.lower(), {})
    clamped = min(max(level, 1), 5)
    return dict(class_slots.get(clamped, {}))


def calculate_spell_dc(ability_score: int, prof_bonus: int) -> int:
    """Calculate spell save DC: 8 + ability modifier + proficiency bonus."""
    return 8 + modifier(ability_score) + prof_bonus


def calculate_spell_attack_bonus(ability_score: int, prof_bonus: int) -> int:
    """Calculate spell attack bonus: ability modifier + proficiency bonus."""
    return modifier(ability_score) + prof_bonus


def can_cast_spell(
    spell: dict, char_level: int, slots_remaining: dict[int, int], class_name: str,
) -> tuple[bool, str]:
    """Check if a character can cast a spell. Returns (can_cast, reason)."""
    spell_level = spell.get("level", 0)

    # Cantrips are always castable
    if spell_level == 0:
        return True, ""

    # Check if class has slots for this spell level at this character level
    max_slots = get_spell_slots(class_name.lower(), char_level)
    if spell_level not in max_slots:
        return False, f"You cannot cast level {spell_level} spells yet."

    # Check remaining slots — can use a higher slot
    usable = find_usable_slot(spell_level, slots_remaining)
    if usable is None:
        return False, "You have no spell slots remaining."

    return True, ""


def find_usable_slot(spell_level: int, slots_remaining: dict[int, int]) -> int | None:
    """Find the lowest available slot >= spell_level. Returns slot level or None."""
    for sl in range(spell_level, 10):
        if slots_remaining.get(sl, 0) > 0:
            return sl
    return None


def resolve_spell_attack(
    attack_bonus: int, target_ac: int,
) -> tuple[bool, bool, DiceResult]:
    """Make a spell attack roll. Returns (hit, critical, dice_result)."""
    return attack_roll(attack_bonus, target_ac)


def resolve_spell_save(target_ability_score: int, dc: int) -> tuple[bool, DiceResult]:
    """Target makes a saving throw vs spell DC. Returns (saved, dice_result)."""
    save_mod = modifier(target_ability_score)
    result = roll("1d20")
    result.modifier = save_mod
    result.total = result.individual_rolls[0] + save_mod
    saved = result.total >= dc
    return saved, result


def calculate_spell_damage(damage_dice: str, is_critical: bool = False) -> DiceResult:
    """Roll spell damage. Critical doubles dice count."""
    return damage_roll(damage_dice, 0, is_critical)


def scale_cantrip_dice(base_dice: str, character_level: int) -> str:
    """Scale cantrip damage dice based on character level.

    Cantrips gain extra dice at levels 5, 11, and 17.
    """
    extra = sum(1 for threshold in CANTRIP_SCALING_LEVELS if character_level >= threshold)
    if extra == 0:
        return base_dice

    parts = base_dice.lower().split("d")
    if len(parts) != 2:
        return base_dice
    num = int(parts[0]) + extra
    return f"{num}d{parts[1]}"


def calculate_healing(healing_dice: str, spellcasting_mod: int) -> DiceResult:
    """Roll healing: dice + spellcasting ability modifier."""
    result = roll(healing_dice)
    result.modifier = spellcasting_mod
    result.total = sum(result.individual_rolls) + spellcasting_mod
    if result.total < 1:
        result.total = 1
    return result


def concentration_save_dc(damage_taken: int) -> int:
    """Calculate Constitution save DC to maintain concentration."""
    return max(10, damage_taken // 2)


def get_arcane_recovery_slots(wizard_level: int) -> int:
    """Arcane Recovery: recover spell slot levels equal to ceil(level / 2)."""
    return math.ceil(wizard_level / 2)
