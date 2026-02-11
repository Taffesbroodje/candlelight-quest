"""Exploration system — movement, looking, searching."""
from __future__ import annotations

import json
import logging
from typing import Any

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.size import stealth_modifier
from text_rpg.mechanics.skills import SKILL_ABILITY_MAP, skill_check
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)


class ExplorationSystem(GameSystem):
    def __init__(self, director: Any | None = None, repos: dict[str, Any] | None = None):
        self._director = director
        self._repos = repos or {}

    def inject(self, *, director: Any = None, repos: dict | None = None, **kwargs: Any) -> None:
        if director is not None:
            self._director = director
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "exploration"

    @property
    def handled_action_types(self) -> set[str]:
        return {"move", "look", "search", "interact"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        action_type = action.action_type.lower()
        if action_type == "move":
            return self._resolve_move(action, context)
        elif action_type == "look":
            return self._resolve_look(action, context)
        elif action_type == "search":
            return self._resolve_search(action, context)
        elif action_type == "interact":
            return self._resolve_interact(action, context)
        return ActionResult(action_id=action.id, success=False, outcome_description="Unknown exploration action.")

    def get_available_actions(self, context: GameContext) -> list[dict]:
        actions: list[dict] = [{"action_type": "look", "description": "Look around"}]
        connections = safe_json(context.location.get("connections"), [])
        for conn in connections:
            if isinstance(conn, dict):
                actions.append({
                    "action_type": "move",
                    "target": conn.get("direction", ""),
                    "description": f"Go {conn.get('direction', '?')} to {conn.get('description', conn.get('target_location_id', '?'))}",
                })
        actions.append({"action_type": "search", "description": "Search the area"})
        return actions

    def _resolve_move(self, action: Action, context: GameContext) -> ActionResult:
        direction = (action.target_id or "").lower()
        connections = safe_json(context.location.get("connections"), [])

        target_conn = None
        for conn in connections:
            if isinstance(conn, dict):
                if conn.get("direction", "").lower() == direction:
                    target_conn = conn
                    break
                # Also match by location id
                if conn.get("target_location_id", "").lower() == direction:
                    target_conn = conn
                    break

        if not target_conn:
            # No existing connection — try dynamic location generation via Director
            if self._director and self._repos:
                return self._try_dynamic_move(action, direction, context)
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You can't go '{direction}' from here.",
            )

        if target_conn.get("is_locked"):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="That way is locked.",
            )

        target_loc_id = target_conn["target_location_id"]

        outcome = f"You head {direction}."
        events = [{"event_type": "MOVE", "description": f"Traveled {direction} to a new location.", "location_id": target_loc_id}]

        mutations = [
            StateMutation(target_type="game", target_id=context.game_id, field="current_location_id", old_value=context.location["id"], new_value=target_loc_id),
            StateMutation(target_type="location", target_id=target_loc_id, field="visited", old_value=False, new_value=True),
        ]

        # Move companions to new location
        for comp in (context.companions or []):
            if comp.get("status") == "active":
                mutations.append(StateMutation(
                    target_type="entity", target_id=comp["entity_id"],
                    field="location_id", old_value=None, new_value=target_loc_id,
                ))

        # Check for bounty-related encounters when entering a town
        bounty_event = self._check_bounty_on_enter(target_loc_id, context)
        if bounty_event:
            outcome += f"\n{bounty_event['description']}"
            events.append(bounty_event)

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=outcome,
            state_mutations=mutations,
            events=events,
        )

    def _try_dynamic_move(self, action: Action, direction: str, context: GameContext) -> ActionResult:
        """Attempt to discover a new path via the Director's plausibility engine."""
        from text_rpg.systems.director.generators import plausibility_to_dc

        try:
            # Evaluate plausibility of finding/creating a path this direction
            plausibility = self._director.evaluate_plausibility(action, context)
            if not isinstance(plausibility, dict):
                plausibility = {"plausibility": 0.5}
            dc = plausibility_to_dc(plausibility.get("plausibility", 0.5))

            # Skill check — typically Survival or Perception for path-finding
            ability_name = plausibility.get("ability", "wisdom").lower()
            skill_name = plausibility.get("skill", "survival").lower()

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

            # Record the skill check event for behavior tracking
            skill_check_event = {
                "event_type": "SKILL_CHECK",
                "description": f"{skill_name} check (DC {dc}) — {'success' if success else 'failure'}",
                "actor_id": char.get("id", ""),
                "mechanical_details": {
                    "skill": skill_name,
                    "dc": dc,
                    "success": success,
                    "roll": roll_result.total,
                },
            }

            if success:
                # Generate and save new location
                new_location = self._director.generate_location_for_direction(
                    direction, context, self._repos,
                )
                if not new_location:
                    return ActionResult(
                        action_id=action.id, success=False,
                        outcome_description=f"You search {direction} but find no viable path.",
                        dice_rolls=dice_rolls,
                    )

                target_loc_id = new_location["id"]
                return ActionResult(
                    action_id=action.id, success=True,
                    outcome_description=f"You discover a path leading {direction} to {new_location.get('name', 'a new area')}.",
                    dice_rolls=dice_rolls,
                    state_mutations=[
                        StateMutation(target_type="game", target_id=context.game_id, field="current_location_id", old_value=context.location["id"], new_value=target_loc_id),
                        StateMutation(target_type="location", target_id=target_loc_id, field="visited", old_value=False, new_value=True),
                    ],
                    events=[
                        skill_check_event,
                        {
                            "event_type": "DISCOVERY",
                            "description": f"Discovered a new path {direction} leading to {new_location.get('name', 'a new area')}.",
                            "location_id": target_loc_id,
                        },
                    ],
                )
            else:
                failure_desc = plausibility.get(
                    "failure_description",
                    f"You search {direction} but can't find a way through.",
                )
                return ActionResult(
                    action_id=action.id, success=False,
                    outcome_description=failure_desc,
                    dice_rolls=dice_rolls,
                    events=[
                        skill_check_event,
                        {
                            "event_type": "EXPLORATION_FAIL",
                            "description": f"Failed to find a path {direction}.",
                        },
                    ],
                )
        except Exception as e:
            logger.warning(f"Dynamic location generation failed: {e}")
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You can't go '{direction}' from here.",
            )

    def _check_bounty_on_enter(self, target_loc_id: str, context: GameContext) -> dict | None:
        """Check if entering a town triggers a guard confrontation due to bounty."""
        if not self._repos or not self._repos.get("reputation") or not self._repos.get("location"):
            return None

        try:
            target_loc = self._repos["location"].get(target_loc_id, context.game_id)
            if not target_loc:
                return None

            loc_type = target_loc.get("location_type", "wilderness")
            if loc_type not in ("town", "village", "settlement"):
                return None

            region_id = target_loc.get("region_id", "")
            if not region_id:
                return None

            bounty = self._repos["reputation"].get_bounty(context.game_id, region_id)
            if bounty.get("amount", 0) <= 0:
                return None

            amount = bounty["amount"]
            return {
                "event_type": "GUARD_CONFRONTATION",
                "description": (
                    f"As you enter, a guard steps forward. \"Halt! You're wanted for crimes in this region. "
                    f"Your bounty stands at {amount} gold. Pay up or face justice!\""
                ),
                "mechanical_details": {
                    "bounty_amount": amount,
                    "region": region_id,
                },
            }
        except Exception:
            return None

    def _resolve_look(self, action: Action, context: GameContext) -> ActionResult:
        loc = context.location
        entities = context.entities
        entity_names = [e["name"] for e in entities if e.get("is_alive", True)]
        items = safe_json(loc.get("items"), [])

        description = loc.get("description", "You see nothing notable.")
        parts = [description]
        if entity_names:
            parts.append(f"Present: {', '.join(entity_names)}")
        if items:
            parts.append(f"Items on the ground: {', '.join(items)}")

        connections = safe_json(loc.get("connections"), [])
        if connections:
            exits = []
            for c in connections:
                if isinstance(c, dict):
                    exits.append(f"{c.get('direction', '?')} ({c.get('description', c.get('target_location_id', '?'))})")
            parts.append(f"Exits: {', '.join(exits)}")

        return ActionResult(action_id=action.id, success=True, outcome_description="\n".join(parts))

    def _resolve_search(self, action: Action, context: GameContext) -> ActionResult:
        char = context.character
        scores = safe_json(char.get("ability_scores"), {})
        skill_profs = safe_json(char.get("skill_proficiencies"), [])

        wis_score = scores.get("wisdom", 10)
        prof_bonus = char.get("proficiency_bonus", 2)
        is_prof = "investigation" in skill_profs or "perception" in skill_profs

        # Searching uses stealth-like awareness — size helps small creatures
        size_mod = stealth_modifier(char.get("size", "Medium"))
        success, result = skill_check(wis_score, prof_bonus, is_prof, dc=12, size_modifier=size_mod)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=result.individual_rolls,
            modifier=result.modifier, total=result.total, purpose="investigation_check",
        )]

        search_skill = "investigation" if "investigation" in skill_profs else "perception"
        skill_event = {
            "event_type": "SKILL_CHECK",
            "description": f"{search_skill} check (DC 12) — {'success' if success else 'failure'}",
            "actor_id": char.get("id", ""),
            "mechanical_details": {"skill": search_skill, "dc": 12, "success": success, "roll": result.total},
        }

        if success:
            outcome = "Your thorough search reveals something interesting."
        else:
            outcome = "After searching carefully, you find nothing of note."

        events = [skill_event]
        if success:
            events.append({"event_type": "DISCOVERY", "description": outcome})

        return ActionResult(
            action_id=action.id, success=success, outcome_description=outcome, dice_rolls=dice_rolls,
            events=events,
        )

    def _resolve_interact(self, action: Action, context: GameContext) -> ActionResult:
        target = action.target_id or ""
        # Check if target is an item on the ground
        items = safe_json(context.location.get("items"), [])
        if target.lower() in [i.lower() for i in items]:
            return ActionResult(
                action_id=action.id, success=True,
                outcome_description=f"You pick up {target}.",
                state_mutations=[
                    StateMutation(target_type="location", target_id=context.location["id"], field="items_remove", old_value=None, new_value=target),
                    StateMutation(target_type="inventory", target_id=context.character["id"], field="items_add", old_value=None, new_value=target),
                ],
                events=[{"event_type": "ITEM_PICKUP", "description": f"Picked up {target}.", "actor_id": context.character["id"]}],
            )
        return ActionResult(action_id=action.id, success=False, outcome_description=f"Nothing to interact with called '{target}'.")
