"""Wound mechanics — pure calculations, no I/O.

Wounds occur when a single attack deals > 50% of max HP.
Each wound imposes a -2 penalty to a specific ability.
Wounds heal via long rest (50% chance each), healer NPC (100%), or potion (25%).
"""
from __future__ import annotations

import random

# Wound types: (wound_name, affected_ability, penalty, description)
WOUND_TYPES: list[tuple[str, str, int, str]] = [
    ("deep_gash", "strength", -2, "A deep gash weakens your muscles."),
    ("cracked_rib", "constitution", -2, "A cracked rib makes it hard to breathe."),
    ("concussion", "intelligence", -2, "A blow to the head leaves you dazed."),
    ("torn_muscle", "dexterity", -2, "A torn muscle slows your movements."),
    ("sprained_wrist", "strength", -1, "A sprained wrist weakens your grip."),
    ("bruised_ribs", "constitution", -1, "Bruised ribs make every breath painful."),
]


def check_for_wound(damage: int, hp_max: int) -> dict | None:
    """Check if a single hit causes a wound.

    Returns a wound dict or None. A wound occurs when damage > 50% of max HP.
    """
    if hp_max <= 0:
        return None
    if damage <= hp_max * 0.5:
        return None

    # Pick a wound type — more severe for bigger hits
    if damage >= hp_max * 0.75:
        # Severe wound: pick from the first 4 (major wounds)
        wound_type = random.choice(WOUND_TYPES[:4])
    else:
        # Minor wound: pick any
        wound_type = random.choice(WOUND_TYPES)

    name, ability, penalty, description = wound_type
    return {
        "type": name,
        "ability": ability,
        "penalty": penalty,
        "description": description,
    }


def heal_wound(wound: dict, method: str) -> bool:
    """Attempt to heal a wound. Returns True if healed.

    Methods:
    - "long_rest": 50% chance
    - "healer_npc": 100% chance
    - "potion": 25% chance
    """
    chances = {
        "long_rest": 0.50,
        "healer_npc": 1.00,
        "potion": 0.25,
    }
    chance = chances.get(method, 0.25)
    return random.random() < chance


def get_wound_penalties(wounds: list[dict]) -> dict[str, int]:
    """Sum up all ability penalties from active wounds.

    Returns {ability_name: total_penalty}.
    """
    penalties: dict[str, int] = {}
    for wound in wounds:
        ability = wound.get("ability", "")
        penalty = wound.get("penalty", 0)
        if ability:
            penalties[ability] = penalties.get(ability, 0) + penalty
    return penalties
