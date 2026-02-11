"""Spell combination mechanics — recipes and DC calculation for merging elements.

Pure mechanics — no I/O. Defines known combination recipes and calculates
the difficulty of discovering them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from text_rpg.mechanics.elements import are_elements_compatible, get_combination_affinity


@dataclass(frozen=True)
class SpellCombination:
    """A discoverable spell combination recipe."""
    id: str
    name: str
    element_a: str
    element_b: str
    result_element: str
    result_spell_id: str
    discovery_dc: int


SPELL_COMBINATIONS: dict[str, SpellCombination] = {
    "firestorm": SpellCombination("firestorm", "Firestorm", "fire", "wind", "fire", "firestorm", 14),
    "ice_lance": SpellCombination("ice_lance", "Ice Lance", "water", "cold", "cold", "ice_lance", 12),
    "mud_pit": SpellCombination("mud_pit", "Mud Pit", "water", "earth", "earth", "mud_pit", 10),
    "chain_storm": SpellCombination("chain_storm", "Chain Storm", "lightning", "water", "lightning", "chain_storm", 16),
    "sandstorm": SpellCombination("sandstorm", "Sandstorm", "earth", "wind", "earth", "sandstorm", 14),
    "acid_rain": SpellCombination("acid_rain", "Acid Rain", "acid", "water", "acid", "acid_rain", 15),
    "frozen_flame": SpellCombination("frozen_flame", "Frozen Flame", "fire", "cold", "force", "frozen_flame", 18),
    "thunder_quake": SpellCombination("thunder_quake", "Thunder Quake", "thunder", "earth", "thunder", "thunder_quake", 16),
    "blinding_storm": SpellCombination("blinding_storm", "Blinding Storm", "lightning", "wind", "lightning", "blinding_storm", 15),
    "poison_mist": SpellCombination("poison_mist", "Poison Mist", "poison", "wind", "poison", "poison_mist", 13),
    "radiant_blaze": SpellCombination("radiant_blaze", "Radiant Blaze", "radiant", "fire", "radiant", "radiant_blaze", 17),
    "shadow_frost": SpellCombination("shadow_frost", "Shadow Frost", "necrotic", "cold", "necrotic", "shadow_frost", 17),
    "psychic_quake": SpellCombination("psychic_quake", "Psychic Quake", "psychic", "earth", "psychic", "psychic_quake", 19),
    "force_gale": SpellCombination("force_gale", "Force Gale", "force", "wind", "force", "force_gale", 16),
    "steam_blast": SpellCombination("steam_blast", "Steam Blast", "fire", "water", "fire", "steam_blast", 13),
}


def find_combination(element_a: str, element_b: str) -> SpellCombination | None:
    """Find a combination recipe for two elements (order-independent).

    Returns the SpellCombination if one exists, None otherwise.
    """
    a = element_a.lower()
    b = element_b.lower()
    for combo in SPELL_COMBINATIONS.values():
        if (combo.element_a == a and combo.element_b == b) or \
           (combo.element_a == b and combo.element_b == a):
            return combo
    return None


def can_attempt_combination(
    known_spells: list[str],
    all_spells: dict[str, dict],
    element_a: str,
    element_b: str,
) -> tuple[bool, str]:
    """Check if the player can attempt to combine two elements.

    Requires knowing at least one spell of each element type.
    Returns (can_attempt, reason).
    """
    a = element_a.lower()
    b = element_b.lower()

    has_a = False
    has_b = False
    for spell_id in known_spells:
        spell = all_spells.get(spell_id, {})
        mechanics = spell.get("mechanics", {})
        damage_type = mechanics.get("damage_type", "").lower()
        if damage_type == a:
            has_a = True
        if damage_type == b:
            has_b = True
        if has_a and has_b:
            break

    if not has_a:
        return False, f"You don't know any {a} spells to use as a base."
    if not has_b:
        return False, f"You don't know any {b} spells to use as a base."

    return True, ""


def calculate_combination_dc(
    base_dc: int,
    arcana_modifier: int,
    affinity_score: float,
    location_bonus: int,
) -> int:
    """Calculate the effective DC for discovering a spell combination.

    Args:
        base_dc: The combination recipe's base discovery DC.
        arcana_modifier: Player's arcana skill modifier (subtracted).
        affinity_score: 0.0-1.0 element compatibility (reduces DC by up to 4).
        location_bonus: Negative bonus from arcane locations (e.g. -8 for arcane tower).

    Returns the final DC, clamped to [5, 40].
    """
    affinity_reduction = int(affinity_score * 4)
    dc = base_dc - affinity_reduction + location_bonus
    return max(5, min(40, dc))
