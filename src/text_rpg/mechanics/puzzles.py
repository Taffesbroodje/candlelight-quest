"""Puzzle mechanics — skill checks, item requirements, and LLM-evaluated riddles."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.dice import roll_d20
from text_rpg.mechanics.skills import SKILL_ABILITY_MAP, skill_check
from text_rpg.utils import safe_json


# Puzzle type definitions — what skill/item each type requires
PUZZLE_TYPES: dict[str, dict[str, Any]] = {
    "lock": {
        "skill": "sleight_of_hand",
        "required_item": "thieves_tools",
        "default_dc": 15,
        "description": "A locked mechanism that requires careful manipulation.",
    },
    "trap": {
        "detect_skill": "perception",
        "save_ability": "dexterity",
        "default_dc": 13,
        "description": "A hidden trap that must be spotted and avoided.",
    },
    "riddle": {
        "skill": "intelligence",  # Raw INT check, or LLM evaluation
        "default_dc": 12,
        "description": "A riddle or puzzle requiring wit to solve.",
    },
    "elemental": {
        "required_spell_type": "elemental",
        "default_dc": 14,
        "description": "A barrier that responds to a specific elemental force.",
    },
    "strength": {
        "skill": "athletics",
        "default_dc": 16,
        "description": "A physical obstacle requiring raw strength.",
    },
}


def evaluate_puzzle_attempt(
    puzzle: dict,
    action_description: str,
    character: dict,
    inventory: list[dict] | None = None,
) -> dict[str, Any]:
    """Evaluate a player's attempt to solve a puzzle encounter.

    Args:
        puzzle: The puzzle definition from encounters.toml
        action_description: What the player is trying to do
        character: Player character dict
        inventory: Player's inventory items

    Returns:
        Dict with keys: success, dc, skill_used, roll_result, description
    """
    puzzle_type = puzzle.get("puzzle_type", "lock")
    dc = puzzle.get("dc", PUZZLE_TYPES.get(puzzle_type, {}).get("default_dc", 15))
    required_item = puzzle.get("required_item")
    required_spell = puzzle.get("required_spell")
    puzzle_def = PUZZLE_TYPES.get(puzzle_type, {})

    scores = safe_json(character.get("ability_scores"), {})
    prof_bonus = character.get("proficiency_bonus", 2)
    skill_profs = safe_json(character.get("skill_proficiencies"), [])

    inventory = inventory or []

    # Check required items
    if required_item:
        has_item = any(
            item.get("item_id") == required_item or item.get("id") == required_item
            for item in inventory
        )
        if not has_item:
            return {
                "success": False,
                "dc": dc,
                "skill_used": None,
                "roll_result": None,
                "description": f"You need {required_item.replace('_', ' ')} to attempt this.",
                "missing_item": required_item,
            }

    if puzzle_type == "lock":
        skill = "sleight_of_hand"
        ability = SKILL_ABILITY_MAP[skill]
        score = scores.get(ability, 10)
        is_prof = skill in skill_profs
        success, result = skill_check(score, prof_bonus, is_prof, dc)
        return {
            "success": success,
            "dc": dc,
            "skill_used": skill,
            "roll_result": result,
            "description": _lock_description(success, result.total, dc),
        }

    elif puzzle_type == "trap":
        # Two-phase: perception to detect, then DEX save to avoid
        detect_skill = "perception"
        detect_ability = SKILL_ABILITY_MAP[detect_skill]
        detect_score = scores.get(detect_ability, 10)
        detect_prof = detect_skill in skill_profs
        detect_dc = max(dc - 2, 8)
        detected, detect_result = skill_check(detect_score, prof_bonus, detect_prof, detect_dc)

        if not detected:
            # Trap triggers — DEX save
            dex_score = scores.get("dexterity", 10)
            save_prof = "dexterity" in (character.get("saving_throw_proficiencies") or [])
            success, save_result = skill_check(dex_score, prof_bonus, save_prof, dc)
            return {
                "success": success,
                "dc": dc,
                "skill_used": "dexterity_save",
                "roll_result": save_result,
                "detected": False,
                "trap_damage": puzzle.get("trap_damage", "2d6"),
                "description": _trap_description(False, success, save_result.total, dc),
            }
        else:
            # Detected — can disarm (sleight_of_hand) or avoid
            skill = "sleight_of_hand"
            ability = SKILL_ABILITY_MAP[skill]
            score = scores.get(ability, 10)
            is_prof = skill in skill_profs
            success, result = skill_check(score, prof_bonus, is_prof, dc)
            return {
                "success": success,
                "dc": dc,
                "skill_used": skill,
                "roll_result": result,
                "detected": True,
                "description": _trap_description(True, success, result.total, dc),
            }

    elif puzzle_type == "riddle":
        # Riddle: uses INT check. LLM evaluation handled separately.
        int_score = scores.get("intelligence", 10)
        is_prof = "investigation" in skill_profs or "arcana" in skill_profs
        success, result = skill_check(int_score, prof_bonus, is_prof, dc)
        return {
            "success": success,
            "dc": dc,
            "skill_used": "intelligence",
            "roll_result": result,
            "description": _riddle_description(success),
            "needs_llm_eval": True,
        }

    elif puzzle_type == "elemental":
        # Check if player used the right spell
        if required_spell:
            action_lower = action_description.lower()
            if required_spell.lower() in action_lower:
                return {
                    "success": True,
                    "dc": dc,
                    "skill_used": "spellcasting",
                    "roll_result": None,
                    "description": f"The elemental barrier responds to your magic and dissolves!",
                }
        # Arcana check as fallback for creative solutions
        arcana_score = scores.get("intelligence", 10)
        is_prof = "arcana" in skill_profs
        success, result = skill_check(arcana_score, prof_bonus, is_prof, dc + 3)
        return {
            "success": success,
            "dc": dc + 3,
            "skill_used": "arcana",
            "roll_result": result,
            "description": _elemental_description(success),
        }

    elif puzzle_type == "strength":
        skill = "athletics"
        ability = SKILL_ABILITY_MAP[skill]
        score = scores.get(ability, 10)
        is_prof = skill in skill_profs
        success, result = skill_check(score, prof_bonus, is_prof, dc)
        return {
            "success": success,
            "dc": dc,
            "skill_used": skill,
            "roll_result": result,
            "description": _strength_description(success),
        }

    # Fallback — generic skill check
    return {
        "success": False,
        "dc": dc,
        "skill_used": None,
        "roll_result": None,
        "description": "You're unsure how to approach this obstacle.",
    }


def get_puzzle_reward(puzzle: dict) -> dict[str, Any]:
    """Get the reward for solving a puzzle."""
    return {
        "xp": puzzle.get("xp_value", 50),
        "loot": puzzle.get("loot", {}),
        "unlocks": puzzle.get("unlocks"),
    }


# -- Description helpers --

def _lock_description(success: bool, roll: int, dc: int) -> str:
    if success:
        return "With deft fingers, you manipulate the mechanism until it clicks open."
    return "The lock resists your attempts. The tumblers refuse to cooperate."


def _trap_description(detected: bool, avoided: bool, roll: int, dc: int) -> str:
    if detected and avoided:
        return "You spot the trap mechanism and carefully disarm it."
    elif detected and not avoided:
        return "You spot the trap but fumble the disarm — it triggers!"
    elif not detected and avoided:
        return "A trap springs! You react instinctively and dodge clear."
    return "A trap springs with no warning! You take the full brunt of it."


def _riddle_description(success: bool) -> str:
    if success:
        return "The answer comes to you in a flash of insight."
    return "The riddle's meaning eludes you. Perhaps there's another way..."


def _elemental_description(success: bool) -> str:
    if success:
        return "You channel your arcane knowledge to bypass the elemental ward."
    return "The elemental barrier holds firm against your approach."


def _strength_description(success: bool) -> str:
    if success:
        return "With a mighty effort, you force the obstacle aside."
    return "Despite your best effort, the obstacle won't budge."
