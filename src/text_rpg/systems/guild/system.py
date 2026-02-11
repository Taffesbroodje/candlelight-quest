"""Guild system — handles guild membership, work orders, and profession progression."""
from __future__ import annotations

import json
import random
import uuid
from typing import Any

from text_rpg.mechanics.guilds import (
    MAX_ACTIVE_ORDERS,
    GUILD_RANKS,
    can_join_guild,
    check_work_order_complete,
    get_guild_rank,
    get_rank_perks,
    rank_index,
)
from text_rpg.models.action import Action, ActionResult, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json


class GuildSystem(GameSystem):
    """Handles guild join, info, job board, accept/submit/abandon jobs."""

    def __init__(self) -> None:
        self._repos: dict[str, Any] | None = None

    def inject(self, *, repos: dict | None = None, **kwargs: Any) -> None:
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "guild"

    @property
    def handled_action_types(self) -> set[str]:
        return {"join_guild", "accept_job", "submit_job", "abandon_job"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        at = action.action_type.lower()
        if at == "join_guild":
            return self._resolve_join(action, context)
        if at == "accept_job":
            return self._resolve_accept_job(action, context)
        if at == "submit_job":
            return self._resolve_submit_job(action, context)
        if at == "abandon_job":
            return self._resolve_abandon_job(action, context)
        return ActionResult(action_id=action.id, success=False, outcome_description="Unknown guild action.")

    def get_available_actions(self, context: GameContext) -> list[dict]:
        return [
            {"action_type": "join_guild", "description": "Join a professional guild"},
            {"action_type": "accept_job", "description": "Accept a work order from the job board"},
            {"action_type": "submit_job", "description": "Submit a completed work order"},
        ]

    def _get_guilds(self) -> dict[str, dict]:
        from text_rpg.content.loader import load_all_guilds
        return load_all_guilds()

    def _get_order_templates(self) -> list[dict]:
        from text_rpg.content.loader import load_work_order_templates
        return load_work_order_templates()

    def _resolve_join(self, action: Action, context: GameContext) -> ActionResult:
        repos = self._repos or {}
        guild_repo = repos.get("guild")
        if not guild_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Guild system unavailable.")

        guilds = self._get_guilds()
        target = (action.target_id or "").lower().strip()

        # Match guild by name or id
        guild_id = None
        guild_data = None
        for gid, gdata in guilds.items():
            gname = gdata.get("name", "").lower()
            if target in gname or target in gid or gname in target or gid in target:
                guild_id = gid
                guild_data = gdata
                break

        if not guild_id or not guild_data:
            guild_names = ", ".join(g["name"] for g in guilds.values())
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"No guild matching '{target}'. Available guilds: {guild_names}",
            )

        char_id = context.character["id"]
        game_id = context.game_id

        # Check if a guild NPC or guild location is nearby
        guild_npc_present = False
        guild_faction = guild_data.get("faction_id", "")
        for entity in context.entities:
            if not entity.get("is_alive", True):
                continue
            props = safe_json(entity.get("properties"), {})
            npc_faction = entity.get("faction_id") or props.get("faction_id", "")
            teaches = props.get("teaches", [])
            profession = guild_data.get("profession", "")
            if npc_faction == guild_faction or profession in teaches:
                guild_npc_present = True
                break

        loc_type = context.location.get("location_type", "")
        loc_props = safe_json(context.location.get("properties"), {})
        is_guild_location = loc_props.get("guild_id") == guild_id or loc_type in ("guild_hall", "academy")

        if not guild_npc_present and not is_guild_location:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You need to find a {guild_data['name']} representative or guild hall to join.",
            )

        # Check membership limits
        memberships = guild_repo.get_memberships(game_id, char_id)
        can_do, reason = can_join_guild(memberships, guild_id)
        if not can_do:
            return ActionResult(action_id=action.id, success=False, outcome_description=reason)

        # Join
        is_primary = len(memberships) == 0
        guild_repo.join_guild(game_id, char_id, guild_id, context.turn_number, is_primary=is_primary)

        # Grant initial reputation with the guild's faction
        rep_repo = repos.get("reputation")
        if rep_repo and guild_faction:
            rep_repo.adjust_faction_rep(game_id, guild_faction, 5)

        events = [{
            "event_type": "GUILD_JOINED",
            "description": f"Joined the {guild_data['name']}",
            "actor_id": char_id,
            "mechanical_details": {
                "guild_id": guild_id,
                "guild_name": guild_data["name"],
                "profession": guild_data.get("profession", ""),
            },
        }]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=(
                f"Welcome to the {guild_data['name']}! You are now an Initiate. "
                f"Check 'jobs' for available work orders, or 'guild' for your status."
            ),
            events=events,
        )

    def _resolve_accept_job(self, action: Action, context: GameContext) -> ActionResult:
        repos = self._repos or {}
        guild_repo = repos.get("guild")
        if not guild_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Guild system unavailable.")

        char_id = context.character["id"]
        game_id = context.game_id

        # Check memberships
        memberships = guild_repo.get_memberships(game_id, char_id)
        if not memberships:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You're not a member of any guild. Find a guild to join first.",
            )

        # Check active order limit
        active_orders = guild_repo.get_active_orders(game_id, char_id)
        if len(active_orders) >= MAX_ACTIVE_ORDERS:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You already have {MAX_ACTIVE_ORDERS} active work orders. Complete or abandon one first.",
            )

        # Find matching order template
        target = (action.target_id or "").lower().strip()
        templates = self._get_order_templates()
        guilds = self._get_guilds()

        # Get reputation data for rank checks
        rep_repo = repos.get("reputation")
        trade_repo = repos.get("trade_skill")

        # Build available orders based on membership and rank
        available = []
        for tmpl in templates:
            tmpl_guild_id = tmpl.get("guild_id", "")
            membership = next((m for m in memberships if m["guild_id"] == tmpl_guild_id), None)
            if not membership:
                continue

            guild_data = guilds.get(tmpl_guild_id, {})

            # Calculate current rank
            faction_id = guild_data.get("faction_id", "")
            rep = 0
            if rep_repo and faction_id:
                rep = rep_repo.get_faction_rep(game_id, faction_id)

            profession = guild_data.get("profession", "")
            trade_level = 1
            if trade_repo and profession:
                skill = trade_repo.get_skill(game_id, char_id, profession)
                if skill:
                    trade_level = skill.get("level", 1)

            rank = get_guild_rank(rep, trade_level, guild_data.get("ranks", []))

            # Check min_rank
            min_rank = tmpl.get("min_rank", "initiate")
            if rank_index(rank) < rank_index(min_rank):
                continue

            available.append((tmpl, guild_data, rank))

        if not available:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="No work orders available for your current guild ranks. Advance your profession to unlock more.",
            )

        # Match by target or pick by number
        chosen = None
        chosen_guild = None
        chosen_rank = None

        if target:
            # Try to match by template id, name, or number
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(available):
                    chosen, chosen_guild, chosen_rank = available[idx]
            else:
                for tmpl, gdata, rank in available:
                    tmpl_name = tmpl.get("name", "").lower()
                    tmpl_id = tmpl.get("id", "").lower()
                    if target in tmpl_name or target in tmpl_id or tmpl_name in target:
                        chosen = tmpl
                        chosen_guild = gdata
                        chosen_rank = rank
                        break

        if not chosen:
            # Show available orders
            lines = ["Available work orders:"]
            for i, (tmpl, gdata, rank) in enumerate(available, 1):
                lines.append(f"  {i}. [{gdata['name']}] {tmpl['name']} ({tmpl['order_type']}) — {tmpl.get('description', '')}")
            lines.append("\nUse 'accept job <number>' or 'accept job <name>' to take one.")
            return ActionResult(action_id=action.id, success=False, outcome_description="\n".join(lines))

        # Create the work order
        from text_rpg.mechanics.guilds import calculate_work_order_reward

        region_tier = 1
        try:
            region_id = context.location.get("region_id", "")
            if region_id:
                from text_rpg.content.loader import load_all_regions
                regions = load_all_regions()
                rdata = regions.get(region_id, {})
                region_tier = max(1, rdata.get("level_range_min", 1) // 3 + 1)
        except Exception:
            pass

        reward = calculate_work_order_reward(
            chosen.get("reward_gold_min", 10), chosen.get("reward_gold_max", 30),
            chosen_rank, region_tier,
        )

        order_data = {
            "id": str(uuid.uuid4()),
            "game_id": game_id,
            "character_id": char_id,
            "guild_id": chosen["guild_id"],
            "template_id": chosen["id"],
            "order_type": chosen["order_type"],
            "description": chosen.get("description", ""),
            "requirements": chosen.get("requirements", {}),
            "progress": {},
            "reward_gold": reward["gold"],
            "reward_xp": chosen.get("reward_xp", 0),
            "reward_rep": chosen.get("reward_rep", 0),
            "accepted_turn": context.turn_number,
            "expires_turn": context.turn_number + 100,  # Generous deadline
        }

        guild_repo.accept_work_order(order_data)

        # Format requirements
        req_str = ", ".join(f"{qty}x {item.replace('_', ' ')}" for item, qty in chosen.get("requirements", {}).items())

        events = [{
            "event_type": "WORK_ORDER_ACCEPTED",
            "description": f"Accepted work order: {chosen['name']}",
            "actor_id": char_id,
            "mechanical_details": {
                "order_id": order_data["id"],
                "guild_id": chosen["guild_id"],
                "template_id": chosen["id"],
            },
        }]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=(
                f"Work order accepted: {chosen['name']}\n"
                f"Requirements: {req_str}\n"
                f"Reward: {reward['gold']} gold, {chosen.get('reward_xp', 0)} trade XP, "
                f"+{chosen.get('reward_rep', 0)} reputation"
            ),
            events=events,
        )

    def _resolve_submit_job(self, action: Action, context: GameContext) -> ActionResult:
        repos = self._repos or {}
        guild_repo = repos.get("guild")
        if not guild_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Guild system unavailable.")

        char_id = context.character["id"]
        game_id = context.game_id

        active_orders = guild_repo.get_active_orders(game_id, char_id)
        if not active_orders:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You have no active work orders.",
            )

        # Find the order to submit
        target = (action.target_id or "").lower().strip()
        chosen = None

        if target and target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(active_orders):
                chosen = active_orders[idx]
        elif target:
            for order in active_orders:
                desc = (order.get("description") or "").lower()
                tmpl_id = order.get("template_id", "").lower()
                if target in desc or target in tmpl_id:
                    chosen = order
                    break

        if not chosen and len(active_orders) == 1:
            chosen = active_orders[0]

        if not chosen:
            lines = ["Active work orders:"]
            for i, order in enumerate(active_orders, 1):
                reqs = order.get("requirements", {})
                prog = order.get("progress", {})
                req_str = ", ".join(
                    f"{prog.get(k, 0)}/{v} {k.replace('_', ' ')}" for k, v in reqs.items()
                )
                lines.append(f"  {i}. {order.get('description', order['template_id'])} — {req_str}")
            lines.append("\nUse 'submit job <number>' to turn one in.")
            return ActionResult(action_id=action.id, success=False, outcome_description="\n".join(lines))

        # Check completion
        requirements = chosen.get("requirements", {})
        progress = chosen.get("progress", {})

        if not check_work_order_complete(requirements, progress):
            req_str = ", ".join(
                f"{progress.get(k, 0)}/{v} {k.replace('_', ' ')}" for k, v in requirements.items()
            )
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"Work order not complete yet. Progress: {req_str}",
            )

        # Complete the order
        completed = guild_repo.complete_order(chosen["id"], game_id, char_id, context.turn_number)
        if not completed:
            return ActionResult(action_id=action.id, success=False, outcome_description="Failed to complete work order.")

        reward_gold = completed.get("reward_gold", 0)
        reward_xp = completed.get("reward_xp", 0)
        reward_rep = completed.get("reward_rep", 0)

        mutations: list[StateMutation] = []
        if reward_gold > 0:
            mutations.append(StateMutation(
                target_type="character", target_id=char_id,
                field="gold", old_value=context.character.get("gold", 0),
                new_value=context.character.get("gold", 0) + reward_gold,
            ))

        # Award reputation
        guild_id = completed.get("guild_id", "")
        guilds = self._get_guilds()
        guild_data = guilds.get(guild_id, {})
        faction_id = guild_data.get("faction_id", "")

        rep_repo = repos.get("reputation")
        if rep_repo and faction_id and reward_rep > 0:
            rep_repo.adjust_faction_rep(game_id, faction_id, reward_rep)

        # Award trade XP
        trade_repo = repos.get("trade_skill")
        profession = guild_data.get("profession", "")
        xp_result = {}
        if trade_repo and profession and reward_xp > 0:
            xp_result = trade_repo.add_xp(game_id, char_id, profession, reward_xp)

        # Check for rank up
        rank_up_text = ""
        membership = guild_repo.get_membership(game_id, char_id, guild_id)
        if membership and rep_repo and faction_id:
            rep = rep_repo.get_faction_rep(game_id, faction_id)
            trade_level = 1
            if trade_repo and profession:
                skill = trade_repo.get_skill(game_id, char_id, profession)
                if skill:
                    trade_level = skill.get("level", 1)

            new_rank = get_guild_rank(rep, trade_level, guild_data.get("ranks", []))
            old_rank = membership.get("rank", "initiate")

            if rank_index(new_rank) > rank_index(old_rank):
                guild_repo.update_rank(game_id, char_id, guild_id, new_rank)
                rank_title = new_rank.capitalize()
                rank_up_text = f"\nRank up! You are now a {rank_title} of the {guild_data.get('name', guild_id)}!"

        events = [{
            "event_type": "WORK_ORDER_COMPLETE",
            "description": f"Completed work order for {guild_data.get('name', guild_id)}",
            "actor_id": char_id,
            "mechanical_details": {
                "guild_id": guild_id,
                "template_id": completed.get("template_id", ""),
                "reward_gold": reward_gold,
                "reward_xp": reward_xp,
                "reward_rep": reward_rep,
            },
        }]

        if rank_up_text:
            events.append({
                "event_type": "GUILD_RANK_UP",
                "description": rank_up_text.strip(),
                "actor_id": char_id,
                "mechanical_details": {"guild_id": guild_id, "new_rank": new_rank},
            })

        desc = f"Work order complete! Earned {reward_gold} gold, {reward_xp} trade XP, +{reward_rep} reputation."
        if xp_result.get("leveled_up"):
            desc += f" {profession.capitalize()} leveled up to {xp_result['level']}!"
        desc += rank_up_text

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=desc,
            state_mutations=mutations,
            events=events,
        )

    def _resolve_abandon_job(self, action: Action, context: GameContext) -> ActionResult:
        repos = self._repos or {}
        guild_repo = repos.get("guild")
        if not guild_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Guild system unavailable.")

        char_id = context.character["id"]
        game_id = context.game_id

        active_orders = guild_repo.get_active_orders(game_id, char_id)
        if not active_orders:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You have no active work orders to abandon.",
            )

        target = (action.target_id or "").lower().strip()
        chosen = None

        if target and target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(active_orders):
                chosen = active_orders[idx]
        elif target:
            for order in active_orders:
                desc = (order.get("description") or "").lower()
                if target in desc or target in order.get("template_id", "").lower():
                    chosen = order
                    break

        if not chosen and len(active_orders) == 1:
            chosen = active_orders[0]

        if not chosen:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="Specify which order to abandon (number or name).",
            )

        guild_repo.abandon_order(chosen["id"])

        # Small reputation penalty
        guild_id = chosen.get("guild_id", "")
        guilds = self._get_guilds()
        guild_data = guilds.get(guild_id, {})
        faction_id = guild_data.get("faction_id", "")

        rep_repo = repos.get("reputation")
        if rep_repo and faction_id:
            rep_repo.adjust_faction_rep(game_id, faction_id, -2)

        events = [{
            "event_type": "WORK_ORDER_FAILED",
            "description": f"Abandoned work order for {guild_data.get('name', guild_id)}",
            "actor_id": char_id,
            "mechanical_details": {"guild_id": guild_id, "template_id": chosen.get("template_id", "")},
        }]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"Work order abandoned. You lost 2 reputation with {guild_data.get('name', 'the guild')}.",
            events=events,
        )
