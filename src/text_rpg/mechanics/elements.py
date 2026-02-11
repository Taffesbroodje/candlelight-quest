"""Elemental damage types, resistances, vulnerabilities, and compatibility.

Pure mechanics — no I/O. Provides the foundation for elemental spell interactions.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class DamageType(str, Enum):
    """All 16 damage types in the game."""
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    ACID = "acid"
    POISON = "poison"
    RADIANT = "radiant"
    NECROTIC = "necrotic"
    FORCE = "force"
    PSYCHIC = "psychic"
    WATER = "water"
    EARTH = "earth"
    WIND = "wind"
    BLUDGEONING = "bludgeoning"
    PIERCING = "piercing"
    SLASHING = "slashing"


# Elemental oppositions: each element has a natural opposite.
ELEMENTAL_OPPOSITIONS: dict[str, str] = {
    "fire": "cold",
    "cold": "fire",
    "lightning": "earth",
    "earth": "lightning",
    "water": "fire",
    "wind": "earth",
    "acid": "radiant",
    "radiant": "necrotic",
    "necrotic": "radiant",
    "poison": "radiant",
    "thunder": "psychic",
    "psychic": "thunder",
    "force": "force",
}

# Elemental affinities: elements that combine well together.
ELEMENTAL_AFFINITIES: dict[str, list[str]] = {
    "fire": ["wind", "lightning"],
    "cold": ["water", "wind"],
    "lightning": ["water", "wind"],
    "water": ["cold", "earth", "acid"],
    "earth": ["fire", "thunder"],
    "wind": ["fire", "lightning", "cold"],
    "acid": ["water", "poison"],
    "thunder": ["earth", "lightning"],
    "poison": ["acid", "wind"],
    "radiant": ["fire"],
    "necrotic": ["cold"],
    "psychic": ["force"],
    "force": ["wind", "psychic"],
}


def get_effective_damage(
    base_damage: int,
    damage_type: str,
    resistances: list[str],
    vulnerabilities: list[str],
    immunities: list[str],
) -> tuple[int, str]:
    """Calculate effective damage after applying resistance/vulnerability/immunity.

    Rules (D&D 5e style):
    - Immunity: 0 damage
    - Resistance + Vulnerability cancel each other out
    - Resistance alone: half damage (floor division)
    - Vulnerability alone: double damage

    Returns (effective_damage, label) where label describes the modifier applied.
    """
    dt = damage_type.lower()

    if dt in [i.lower() for i in immunities]:
        return 0, "immune"

    is_resistant = dt in [r.lower() for r in resistances]
    is_vulnerable = dt in [v.lower() for v in vulnerabilities]

    if is_resistant and is_vulnerable:
        return base_damage, "normal"
    if is_resistant:
        return base_damage // 2, "resistant"
    if is_vulnerable:
        return base_damage * 2, "vulnerable"

    return base_damage, "normal"


def are_elements_compatible(element_a: str, element_b: str) -> bool:
    """Check if two elements have natural affinity for combination.

    Two elements are compatible if either lists the other as an affinity.
    """
    a = element_a.lower()
    b = element_b.lower()
    if a == b:
        return True
    affinities_a = ELEMENTAL_AFFINITIES.get(a, [])
    affinities_b = ELEMENTAL_AFFINITIES.get(b, [])
    return b in affinities_a or a in affinities_b


def get_combination_affinity(element_a: str, element_b: str) -> float:
    """Get a 0.0-1.0 score indicating how well two elements combine.

    1.0 = mutually affine (both list each other)
    0.7 = one-way affinity
    0.3 = neutral (no affinity, no opposition)
    0.0 = opposed elements
    """
    a = element_a.lower()
    b = element_b.lower()

    if a == b:
        return 1.0

    # Check opposition
    if ELEMENTAL_OPPOSITIONS.get(a) == b:
        return 0.0

    affinities_a = ELEMENTAL_AFFINITIES.get(a, [])
    affinities_b = ELEMENTAL_AFFINITIES.get(b, [])
    mutual = b in affinities_a and a in affinities_b
    one_way = b in affinities_a or a in affinities_b

    if mutual:
        return 1.0
    if one_way:
        return 0.7
    return 0.3
