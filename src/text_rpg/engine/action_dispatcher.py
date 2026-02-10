"""Action dispatcher — routes actions to appropriate systems."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from text_rpg.engine.system_registry import SystemRegistry
from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.skills import SKILL_ABILITY_MAP, skill_check
from text_rpg.models.action import Action, ActionResult, DiceRoll
from text_rpg.systems.base import GameContext
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)

# Verbs that imply using/manipulating a specific item.
_ITEM_USE_PATTERN = re.compile(
    r"(?:throw|toss|hurl|use|drink|eat|consume|apply|wave|swing|wield|brandish|"
    r"pour|drop|place|put|give|show|offer|light|smash|break)\s+"
    r"(?:the\s+|my\s+|a\s+|some\s+)?(.+?)"
    r"(?:\s+(?:at|on|to|toward|towards|into|onto|against|over|with)\s+|$)",
    re.I,
)


class ActionDispatcher:
    def __init__(self, registry: SystemRegistry, director: Any | None = None, repos: dict[str, Any] | None = None):
        self.registry = registry
        self.director = director
        self.repos = repos or {}

    def dispatch(self, action: Action, context: GameContext) -> ActionResult:
        # Unrecognized input — don't try plausibility, just give a helpful nudge
        if action.action_type == "unrecognized":
            return ActionResult(
                action_id=action.id,
                success=False,
                outcome_description=(
                    f"You pause, uncertain. What exactly do you want to do? "
                    f"(Try commands like **look**, **go north**, **talk to** someone, "
                    f"**attack**, **search**, or type **help** for a full list.)"
                ),
            )

        system = self.registry.find_system_for_action(action, context)
        if not system:
            # No system handles this action — try plausibility-gated creative action
            if self.director:
                return self._try_creative_action(action, context)
            logger.warning(f"No system found for action type: {action.action_type}")
            return ActionResult(
                action_id=action.id,
                success=False,
                outcome_description=f"You're not sure how to '{action.raw_input}'.",
            )
        try:
            return system.resolve(action, context)
        except Exception as e:
            logger.exception(f"Error resolving action in {system.system_id}")
            return ActionResult(
                action_id=action.id,
                success=False,
                outcome_description=f"Something went wrong: {e}",
            )

    def _check_item_references(self, raw_input: str, context: GameContext) -> str | None:
        """Check if the action references items the player doesn't have.

        Returns an error message if a referenced item is missing, or None if OK.
        """
        match = _ITEM_USE_PATTERN.search(raw_input.lower())
        if not match:
            return None

        item_ref = match.group(1).strip()
        if not item_ref:
            return None

        inv = context.inventory
        inv_items: list[str] = []
        if inv:
            items_raw = safe_json(inv.get("items"), [])
            inv_items = [e.get("item_id", "").lower().replace("_", " ") for e in items_raw]

        # Check if the referenced item matches anything in inventory
        found = any(
            item_ref in item_name or item_name in item_ref
            for item_name in inv_items
        )

        if not found:
            if inv_items:
                return f"You don't have '{item_ref}' in your inventory."
            return f"Your pack is empty — you don't have '{item_ref}'."

        return None

    def _try_creative_action(self, action: Action, context: GameContext) -> ActionResult:
        """Use the Director's plausibility engine to evaluate and resolve a creative action."""
        try:
            # Check inventory for referenced items before running plausibility
            item_error = self._check_item_references(action.raw_input, context)
            if item_error:
                return ActionResult(
                    action_id=action.id,
                    success=False,
                    outcome_description=item_error,
                )

            from text_rpg.systems.director.generators import plausibility_to_dc

            plausibility = self.director.evaluate_plausibility(action, context)
            dc = plausibility_to_dc(plausibility["plausibility"])

            # Determine ability score and skill
            ability_name = plausibility.get("ability", "strength").lower()
            skill_name = plausibility.get("skill", "athletics").lower()

            char = context.character
            scores = safe_json(char.get("ability_scores"), {})
            ability_score = scores.get(ability_name, 10)

            skill_profs = safe_json(char.get("skill_proficiencies"), [])
            is_prof = skill_name in skill_profs

            prof_bonus = char.get("proficiency_bonus", 2)

            success, roll_result = skill_check(ability_score, prof_bonus, is_prof, dc)

            dice_rolls = [DiceRoll(
                dice_expression="1d20",
                rolls=roll_result.individual_rolls,
                modifier=roll_result.modifier,
                total=roll_result.total,
                purpose=f"{skill_name}_check (DC {dc})",
            )]

            if success:
                result = self.director.generate_creative_outcome(action, context, plausibility, self.repos)
                result.dice_rolls = dice_rolls
                return result
            else:
                return ActionResult(
                    action_id=action.id,
                    success=False,
                    outcome_description=plausibility.get("failure_description", "You fail in your attempt."),
                    dice_rolls=dice_rolls,
                    events=[{
                        "event_type": "CREATIVE_ACTION_FAIL",
                        "description": f"Failed creative action: {action.raw_input}",
                        "actor_id": context.character.get("id"),
                        "location_id": context.location.get("id"),
                    }],
                )
        except Exception as e:
            logger.warning(f"Creative action evaluation failed: {e}")
            return ActionResult(
                action_id=action.id,
                success=False,
                outcome_description=f"You're not sure how to '{action.raw_input}'.",
            )
