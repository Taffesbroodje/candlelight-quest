"""XP and level-up mechanics — pure math, no I/O."""
from __future__ import annotations

from text_rpg.mechanics.dice import roll

XP_THRESHOLDS: dict[int, int] = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}

HIT_DICE: dict[str, str] = {
    "fighter": "1d10",
    "wizard": "1d6",
    "rogue": "1d8",
    "cleric": "1d8",
}

_PROF_BONUS = {
    1: 2, 2: 2, 3: 2, 4: 2,
    5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4,
    13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6,
}


def xp_for_level(level: int) -> int:
    """XP required to reach the given level."""
    return XP_THRESHOLDS.get(level, 0)


def level_for_xp(xp: int) -> int:
    """Determine level from total XP."""
    level = 1
    for lvl in sorted(XP_THRESHOLDS.keys()):
        if xp >= XP_THRESHOLDS[lvl]:
            level = lvl
        else:
            break
    return level


def proficiency_bonus(level: int) -> int:
    """Proficiency bonus for a given level."""
    return _PROF_BONUS.get(min(max(level, 1), 20), 2)


def can_level_up(current_level: int, current_xp: int) -> bool:
    """Check if the character can level up."""
    if current_level >= 20:
        return False
    next_level = current_level + 1
    return current_xp >= xp_for_level(next_level)


def roll_hit_points_on_level_up(class_name: str, con_modifier: int) -> int:
    """Roll HP gained on level up: hit die + CON modifier (minimum 1)."""
    hit_die = HIT_DICE.get(class_name.lower(), "1d8")
    result = roll(hit_die)
    hp_gained = result.total + con_modifier
    return max(hp_gained, 1)
