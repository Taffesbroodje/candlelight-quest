"""Trigger evaluation — decides when the Director should generate content."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.systems.base import GameContext
from text_rpg.utils import safe_json, safe_props


def should_spawn_npc(context: GameContext, repos: dict[str, Any]) -> bool:
    """True if the current location could use a new NPC.

    Conditions:
    - Location has fewer than 2 alive NPCs
    - Player has visited this location on 3+ turns without social interaction
    """
    alive_npcs = [
        e for e in context.entities
        if e.get("entity_type") == "npc" and e.get("is_alive", True)
    ]
    if len(alive_npcs) >= 2:
        return False

    # Check if location is populated enough for the area type
    loc_type = context.location.get("location_type", "wilderness")
    if loc_type in ("town", "village", "settlement", "tavern", "shop") and len(alive_npcs) < 1:
        return True

    # Check if player has been here a while without social interaction
    recent = context.recent_events or []
    location_id = context.location.get("id")
    turns_at_location = sum(
        1 for e in recent
        if e.get("location_id") == location_id
    )
    dialogue_at_location = any(
        e.get("event_type") == "DIALOGUE" and e.get("location_id") == location_id
        for e in recent
    )
    if turns_at_location >= 3 and not dialogue_at_location and len(alive_npcs) == 0:
        return True

    return False


def should_generate_location(direction: str, context: GameContext) -> bool:
    """True if the player tried to move in a direction with no connection.

    This is checked in the exploration system itself — always returns True
    as a confirmation that the Director should attempt generation.
    """
    connections = safe_json(context.location.get("connections"), [])

    for conn in connections:
        if isinstance(conn, dict) and conn.get("direction", "").lower() == direction.lower():
            return False  # Connection exists, no need to generate
    return True


def should_offer_quest(npc: dict, context: GameContext) -> bool:
    """True if NPC has a quest hook but no active quest from them."""
    props = safe_props(npc)

    quest_hook = props.get("quest_hook")
    if not quest_hook:
        return False

    # Check if there's already an active quest from this NPC
    npc_id = npc.get("id", "")
    for quest in (context.active_quests or []):
        if quest.get("quest_giver_id") == npc_id and quest.get("status") in ("active", "available"):
            return False

    return True


def should_generate_follow_up(completed_quest: dict, context: GameContext) -> bool:
    """True if a just-completed quest is suitable for a follow-up."""
    flexibility = completed_quest.get("completion_flexibility", "low")
    if flexibility == "none":
        return False

    # Don't chain too deep — check if this quest was itself a follow-up
    props = safe_props(completed_quest)
    chain_depth = props.get("chain_depth", 0)
    if chain_depth >= 3:
        return False

    return True


def should_enrich_location(context: GameContext) -> bool:
    """True if the location has been visited but feels empty."""
    loc = context.location
    items = safe_json(loc.get("items"), [])

    entities = context.entities
    alive = [e for e in entities if e.get("is_alive", True)]

    # Location is empty if no items and no alive entities
    if not items and not alive:
        # Only enrich if the location has been visited before
        if loc.get("visited", False):
            return True
    return False


def pacing_check(context: GameContext) -> bool:
    """True every 10 turns — opportunity for the Director to seed hooks."""
    return context.turn_number > 0 and context.turn_number % 10 == 0


def should_spawn_bounty_hunter(context: GameContext, bounty_amount: int) -> bool:
    """True if the player has a high enough bounty for a bounty hunter encounter.

    Chance increases with bounty amount. Only triggers on roads/wilderness.
    """
    import random

    if bounty_amount < 50:
        return False

    loc_type = context.location.get("location_type", "wilderness")
    if loc_type in ("town", "village", "settlement", "tavern", "shop"):
        return False  # Guards handle towns, bounty hunters roam the wilds

    # Higher bounty → higher chance
    chance = min(0.5, bounty_amount / 200)
    return random.random() < chance
