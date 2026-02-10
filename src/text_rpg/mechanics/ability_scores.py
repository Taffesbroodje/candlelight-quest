"""Ability score math — pure functions, no I/O."""
from __future__ import annotations

from text_rpg.mechanics.dice import roll

ABILITY_NAMES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

RACIAL_BONUSES: dict[str, dict[str, int]] = {
    "human": {"strength": 1, "dexterity": 1, "constitution": 1, "intelligence": 1, "wisdom": 1, "charisma": 1},
    "elf": {"dexterity": 2},
    "dwarf": {"constitution": 2},
    "halfling": {"dexterity": 2},
    "half_orc": {"strength": 2, "constitution": 1},
}


def modifier(score: int) -> int:
    """Calculate ability modifier from score."""
    return (score - 10) // 2


def generate_ability_scores(method: str = "standard_array") -> list[int]:
    """Generate a set of 6 ability scores."""
    if method == "standard_array":
        return list(STANDARD_ARRAY)
    elif method == "roll_4d6":
        scores = []
        for _ in range(6):
            result = roll("4d6kh3")
            scores.append(result.total)
        return sorted(scores, reverse=True)
    elif method == "point_buy":
        return [13, 13, 13, 12, 12, 12]
    else:
        return list(STANDARD_ARRAY)


def apply_racial_bonuses(scores: dict[str, int], race: str) -> dict[str, int]:
    """Apply racial ability score bonuses."""
    bonuses = RACIAL_BONUSES.get(race.lower(), {})
    result = dict(scores)
    for ability, bonus in bonuses.items():
        if ability in result:
            result[ability] += bonus
    return result
