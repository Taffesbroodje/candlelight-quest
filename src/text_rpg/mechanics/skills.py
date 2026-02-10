"""Skill system — pure math, no I/O."""
from __future__ import annotations

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.dice import DiceResult, roll_d20, roll_with_advantage, roll_with_disadvantage

SKILL_ABILITY_MAP: dict[str, str] = {
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}


def skill_check(
    ability_score: int,
    proficiency_bonus: int,
    is_proficient: bool,
    dc: int,
    advantage: bool = False,
    disadvantage: bool = False,
) -> tuple[bool, DiceResult]:
    """Make a skill check. Returns (success, dice_result)."""
    mod = modifier(ability_score)
    if is_proficient:
        mod += proficiency_bonus

    if advantage and not disadvantage:
        best, _, _ = roll_with_advantage()
        result = best
    elif disadvantage and not advantage:
        worst, _, _ = roll_with_disadvantage()
        result = worst
    else:
        result = roll_d20()

    result.modifier = mod
    result.total = result.individual_rolls[0] + mod

    return result.total >= dc, result


def passive_score(ability_score: int, proficiency_bonus: int, is_proficient: bool) -> int:
    """Calculate passive skill score (e.g., passive Perception)."""
    mod = modifier(ability_score)
    if is_proficient:
        mod += proficiency_bonus
    return 10 + mod
