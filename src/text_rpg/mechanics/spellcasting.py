"""Spellcasting mechanics — pure functions, no I/O."""
from __future__ import annotations

import math

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.combat_math import attack_roll, damage_roll
from text_rpg.mechanics.dice import DiceResult, roll

SPELLCASTING_ABILITY: dict[str, str] = {
    "wizard": "intelligence",
    "cleric": "wisdom",
    "bard": "charisma",
    "druid": "wisdom",
    "paladin": "charisma",
    "ranger": "wisdom",
    "sorcerer": "charisma",
    "warlock": "charisma",
}

# Full caster spell slot table (wizard, cleric, bard, druid, sorcerer)
_FULL_CASTER_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2},
}

# Half caster spell slot table (paladin, ranger — no slots at level 1)
_HALF_CASTER_SLOTS: dict[int, dict[int, int]] = {
    1: {},
    2: {1: 2},
    3: {1: 3},
    4: {1: 3},
    5: {1: 4, 2: 2},
    6: {1: 4, 2: 2},
    7: {1: 4, 2: 3},
    8: {1: 4, 2: 3},
    9: {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
    11: {1: 4, 2: 3, 3: 3},
    12: {1: 4, 2: 3, 3: 3},
    13: {1: 4, 2: 3, 3: 3, 4: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 2},
    16: {1: 4, 2: 3, 3: 3, 4: 2},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# Pact magic (warlock): all slots are always at the highest castable level.
# Stored as {slot_level: num_slots} for consistency with other casters.
_PACT_MAGIC_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 1},
    2: {1: 2},
    3: {2: 2},
    4: {2: 2},
    5: {3: 2},
    6: {3: 2},
    7: {4: 2},
    8: {4: 2},
    9: {5: 2},
    10: {5: 2},
    11: {5: 3},
    12: {5: 3},
    13: {5: 3},
    14: {5: 3},
    15: {5: 3},
    16: {5: 3},
    17: {5: 4},
    18: {5: 4},
    19: {5: 4},
    20: {5: 4},
}

FULL_CASTERS = {"wizard", "cleric", "bard", "druid", "sorcerer"}
HALF_CASTERS = {"paladin", "ranger"}
PACT_CASTERS = {"warlock"}

# Legacy compat: SPELL_SLOTS still used by some callers
SPELL_SLOTS: dict[str, dict[int, dict[int, int]]] = {
    cls: {level: dict(slots) for level, slots in _FULL_CASTER_SLOTS.items()}
    for cls in FULL_CASTERS
}

CANTRIP_SCALING_LEVELS = [5, 11, 17]


def get_spell_slots(class_name: str, level: int) -> dict[int, int]:
    """Return max spell slots for a class at a given character level."""
    cls = class_name.lower()
    clamped = min(max(level, 1), 20)
    if cls in FULL_CASTERS:
        return dict(_FULL_CASTER_SLOTS.get(clamped, {}))
    if cls in HALF_CASTERS:
        return dict(_HALF_CASTER_SLOTS.get(clamped, {}))
    if cls in PACT_CASTERS:
        return dict(_PACT_MAGIC_SLOTS.get(clamped, {}))
    return {}


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
