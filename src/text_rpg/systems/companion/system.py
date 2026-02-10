"""Companion system — recruit, dismiss, and manage NPC companions."""
from __future__ import annotations

import json
import logging
from typing import Any

from text_rpg.mechanics.affinity import can_recruit, get_tier_name
from text_rpg.mechanics.companion import MAX_ACTIVE_COMPANIONS, can_recruit_companion
from text_rpg.models.action import Action, ActionResult, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)


class CompanionSystem(GameSystem):
    def __init__(self, repos: dict[str, Any] | None = None):
        self._repos = repos or {}

    def inject(self, *, repos: dict | None = None, **kwargs) -> None:
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "companion"

    @property
    def handled_action_types(self) -> set[str]:
        return {"recruit", "dismiss", "give"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        action_type = action.action_type.lower()
        if action_type == "recruit":
            return self._recruit(action, context)
        elif action_type == "dismiss":
            return self._dismiss(action, context)
        elif action_type == "give":
            return self._give_gift(action, context)
        return ActionResult(action_id=action.id, success=False, outcome_description="Unknown companion action.")

    def get_available_actions(self, context: GameContext) -> list[dict]:
        actions = []
        for e in context.entities:
            if e.get("entity_type") == "npc" and e.get("is_alive", True):
                actions.append({"action_type": "give", "target": e["name"], "description": f"Give an item to {e['name']}"})
        return actions

    def _recruit(self, action: Action, context: GameContext) -> ActionResult:
        """Recruit an NPC as a companion."""
        target_name = (action.target_id or "").lower()
        npc = self._find_npc(target_name, context)

        if not npc:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"There's nobody called '{action.target_id}' here to recruit.",
            )

        # Check affinity
        rep_repo = self._repos.get("reputation")
        if not rep_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Cannot check relationship status.")

        affinity_score = rep_repo.get_npc_rep(context.game_id, npc["id"])
        tier = get_tier_name(affinity_score)

        if not can_recruit(affinity_score):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"{npc['name']} considers you a '{tier}' (affinity: {affinity_score}). "
                f"You need at least 'Companion' tier (15) to recruit them.",
            )

        # Check companion limit
        comp_repo = self._repos.get("companion")
        if not comp_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Companion system unavailable.")

        active = comp_repo.get_active_companions(context.game_id)
        if not can_recruit_companion(active):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You already have {MAX_ACTIVE_COMPANIONS} active companions. Dismiss one first.",
            )

        # Check not already recruited
        existing = comp_repo.get_companion_by_entity(context.game_id, npc["id"])
        if existing and existing.get("status") == "active":
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"{npc['name']} is already your companion.",
            )

        # Recruit
        location_id = context.location.get("id", "")
        comp_repo.recruit(context.game_id, npc["id"], context.turn_number, location_id)

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"{npc['name']} agrees to join you on your journey! ({tier})",
            events=[{
                "event_type": "COMPANION_RECRUIT",
                "description": f"{npc['name']} recruited as a companion.",
                "actor_id": context.character["id"],
                "target_id": npc["id"],
            }],
        )

    def _dismiss(self, action: Action, context: GameContext) -> ActionResult:
        """Dismiss a companion."""
        target_name = (action.target_id or "").lower()
        comp_repo = self._repos.get("companion")
        if not comp_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Companion system unavailable.")

        active = comp_repo.get_active_companions(context.game_id)
        companion = None
        for c in active:
            # Find entity to get name
            for e in context.entities:
                if e["id"] == c["entity_id"] and target_name in e["name"].lower():
                    companion = c
                    companion["name"] = e["name"]
                    break
            if companion:
                break

        if not companion:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You don't have a companion called '{action.target_id}'.",
            )

        comp_repo.dismiss(context.game_id, companion["entity_id"])
        home = companion.get("home_location") or context.location.get("id", "")

        mutations = [
            StateMutation(
                target_type="entity", target_id=companion["entity_id"],
                field="location_id", old_value=None, new_value=home,
            ),
        ]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"{companion['name']} bids you farewell and heads home.",
            state_mutations=mutations,
            events=[{
                "event_type": "COMPANION_DISMISS",
                "description": f"{companion['name']} dismissed.",
                "target_id": companion["entity_id"],
            }],
        )

    def _give_gift(self, action: Action, context: GameContext) -> ActionResult:
        """Give an item to an NPC to increase affinity."""
        from text_rpg.mechanics.affinity import affinity_from_gift, clamp_affinity
        from text_rpg.content.loader import load_all_items

        target_name = action.parameters.get("npc_name", action.target_id or "").lower()
        item_name = action.parameters.get("item_name", "").lower()

        if not item_name:
            # Parse "give <item> to <npc>" from raw input
            raw = action.raw_input or ""
            parts = raw.lower().split(" to ")
            if len(parts) == 2:
                item_part = parts[0].replace("give ", "").strip()
                target_name = parts[1].strip()
                item_name = item_part
            else:
                return ActionResult(
                    action_id=action.id, success=False,
                    outcome_description="Give what to whom? Try: give <item> to <npc>",
                )

        npc = self._find_npc(target_name, context)
        if not npc:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"There's nobody called '{target_name}' here.",
            )

        # Find item in inventory
        inv = context.inventory or []
        if isinstance(inv, dict):
            inv = inv.get("items", [])
        all_items = load_all_items()
        found_item = None
        found_inv_entry = None

        for entry in inv:
            iid = entry.get("item_id", "")
            item_data = all_items.get(iid, {})
            if item_name in iid.lower() or item_name in item_data.get("name", "").lower():
                found_item = item_data
                found_item["id"] = iid
                found_inv_entry = entry
                break

        if not found_item:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You don't have '{item_name}' in your inventory.",
            )

        # Get NPC preferences
        props = safe_json(npc.get("properties"), {})
        preferences = {
            "preferred_gifts": props.get("preferred_gifts", []),
            "disliked_gifts": props.get("disliked_gifts", []),
        }

        # Calculate affinity change
        change = affinity_from_gift(found_item["id"], preferences)

        # Update NPC reputation (used as affinity score)
        rep_repo = self._repos.get("reputation")
        if rep_repo:
            current = rep_repo.get_npc_rep(context.game_id, npc["id"])
            new_score = clamp_affinity(current + change)
            rep_repo.set_npc_rep(context.game_id, npc["id"], new_score)
            tier = get_tier_name(new_score)
        else:
            new_score = change
            tier = "Unknown"

        # Remove item from inventory
        mutations = [
            StateMutation(
                target_type="inventory",
                target_id=context.character["id"],
                field="items_remove_one",
                old_value=None,
                new_value=json.dumps({"item_id": found_item["id"]}),
            ),
        ]

        item_display = found_item.get("name", found_item["id"].replace("_", " ").title())
        npc_name = npc["name"]

        if change > 3:
            reaction = f"{npc_name}'s eyes light up! They love it!"
        elif change > 0:
            reaction = f"{npc_name} accepts the gift with a nod."
        else:
            reaction = f"{npc_name} frowns at the gift. Not their taste."

        desc = f"You give {item_display} to {npc_name}. {reaction} (Affinity: {new_score}, {tier})"

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=desc,
            state_mutations=mutations,
            events=[{
                "event_type": "GIFT_GIVEN",
                "description": f"Gave {item_display} to {npc_name}. Affinity {'+' if change >= 0 else ''}{change}.",
                "actor_id": context.character["id"],
                "target_id": npc["id"],
                "mechanical_details": {"item_id": found_item["id"], "affinity_change": change, "new_score": new_score},
            }],
        )

    def _find_npc(self, target_name: str, context: GameContext) -> dict | None:
        """Find an NPC in the current location by name."""
        target_lower = target_name.lower()
        for e in context.entities:
            if e.get("entity_type") == "npc" and e.get("is_alive", True):
                if e["name"].lower() == target_lower or target_lower in e["name"].lower():
                    return e
        return None
