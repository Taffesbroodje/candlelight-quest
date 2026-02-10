"""Status condition effects — pure data, no I/O."""
from __future__ import annotations

from enum import Enum
from typing import Any


class Condition(str, Enum):
    BLINDED = "blinded"
    CHARMED = "charmed"
    DEAFENED = "deafened"
    FRIGHTENED = "frightened"
    GRAPPLED = "grappled"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    POISONED = "poisoned"
    PRONE = "prone"
    RESTRAINED = "restrained"
    STUNNED = "stunned"
    UNCONSCIOUS = "unconscious"


CONDITION_EFFECTS: dict[str, dict[str, Any]] = {
    "blinded": {
        "attack_disadvantage": True,
        "grants_advantage_to_attackers": True,
        "auto_fail_sight_checks": True,
    },
    "charmed": {
        "cannot_attack_charmer": True,
        "charmer_has_advantage_on_social": True,
    },
    "deafened": {
        "auto_fail_hearing_checks": True,
    },
    "frightened": {
        "attack_disadvantage_while_source_visible": True,
        "cannot_move_closer_to_source": True,
    },
    "grappled": {
        "speed_zero": True,
    },
    "incapacitated": {
        "cannot_take_actions": True,
        "cannot_take_reactions": True,
    },
    "invisible": {
        "attack_advantage": True,
        "grants_disadvantage_to_attackers": True,
    },
    "paralyzed": {
        "cannot_take_actions": True,
        "cannot_move": True,
        "auto_fail_str_dex_saves": True,
        "grants_advantage_to_attackers": True,
        "melee_hits_are_crits": True,
    },
    "petrified": {
        "cannot_take_actions": True,
        "cannot_move": True,
        "auto_fail_str_dex_saves": True,
        "grants_advantage_to_attackers": True,
        "resistance_all_damage": True,
        "immune_poison_disease": True,
    },
    "poisoned": {
        "attack_disadvantage": True,
        "ability_check_disadvantage": True,
    },
    "prone": {
        "attack_disadvantage": True,
        "melee_attackers_have_advantage": True,
        "ranged_attackers_have_disadvantage": True,
    },
    "restrained": {
        "speed_zero": True,
        "attack_disadvantage": True,
        "grants_advantage_to_attackers": True,
        "dex_save_disadvantage": True,
    },
    "stunned": {
        "cannot_take_actions": True,
        "cannot_move": True,
        "auto_fail_str_dex_saves": True,
        "grants_advantage_to_attackers": True,
    },
    "unconscious": {
        "cannot_take_actions": True,
        "cannot_move": True,
        "auto_fail_str_dex_saves": True,
        "grants_advantage_to_attackers": True,
        "melee_hits_are_crits": True,
        "prone": True,
    },
}


def get_condition_effects(condition: str) -> dict[str, Any]:
    """Get the mechanical effects of a condition."""
    return CONDITION_EFFECTS.get(condition.lower(), {})


def has_attack_advantage(conditions: list[str]) -> bool:
    """Check if any active conditions grant attack advantage."""
    for c in conditions:
        effects = get_condition_effects(c)
        if effects.get("attack_advantage"):
            return True
    return False


def has_attack_disadvantage(conditions: list[str]) -> bool:
    """Check if any active conditions impose attack disadvantage."""
    for c in conditions:
        effects = get_condition_effects(c)
        if effects.get("attack_disadvantage"):
            return True
    return False


def can_take_actions(conditions: list[str]) -> bool:
    """Check if the creature can take actions given its conditions."""
    for c in conditions:
        effects = get_condition_effects(c)
        if effects.get("cannot_take_actions"):
            return False
    return True


def is_incapacitated(conditions: list[str]) -> bool:
    """Check if the creature is incapacitated."""
    return not can_take_actions(conditions)


def grants_advantage_to_attackers(conditions: list[str]) -> bool:
    """Check if any condition grants advantage to attackers."""
    for c in conditions:
        effects = get_condition_effects(c)
        if effects.get("grants_advantage_to_attackers"):
            return True
    return False
