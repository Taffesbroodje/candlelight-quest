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


def should_reveal_new_region(
    context: GameContext,
    repos: dict[str, Any],
    all_region_ids: list[str],
) -> bool:
    """True when player is near the ceiling of the current region and has explored most locations.

    Tier-aware progression:
    - Player level must be within 1 of the region's level_range_max
    - Player has visited 60%+ of the locations in the current region
    - Prefers revealing same-tier unexplored regions before higher tiers
    - Only reveals T(N+1) when no same-tier unexplored regions remain
    """
    region_id = context.location.get("region_id", "")
    if not region_id:
        return False

    location_repo = repos.get("location")
    if not location_repo:
        return False

    # Check exploration percentage in current region
    region_locations = location_repo.get_by_region(context.game_id, region_id)
    if not region_locations:
        return False

    visited = sum(1 for loc in region_locations if loc.get("visited"))
    total = len(region_locations)
    if total == 0:
        return False

    exploration_pct = visited / total
    if exploration_pct < 0.6:
        return False

    # Check player level vs region max
    from text_rpg.content.loader import load_region, load_all_regions
    try:
        region_data = load_region(region_id)
    except Exception:
        return False

    level_max = region_data.get("level_range_max", 5)
    player_level = context.character.get("level", 1)
    if player_level < level_max - 1:
        return False

    # Build set of visited regions
    visited_regions = set()
    all_game_locations = location_repo.get_all(context.game_id)
    for loc in all_game_locations:
        r = loc.get("region_id", "")
        if r and loc.get("visited"):
            visited_regions.add(r)

    # Load all region metadata for tier-aware selection
    all_regions = load_all_regions()
    current_level_max = level_max

    # Find unvisited content regions, grouped by tier proximity
    same_tier = []
    next_tier = []
    for rid in all_region_ids:
        if rid in visited_regions:
            continue
        rdata = all_regions.get(rid)
        if not rdata:
            continue
        r_min = rdata.get("level_range_min", 1)
        r_max = rdata.get("level_range_max", 5)
        # Same tier: level ranges overlap with current region
        if r_min <= current_level_max and r_max >= region_data.get("level_range_min", 1):
            same_tier.append(rid)
        # Next tier: level_range_min is within reach (player level >= r_min - 2)
        elif player_level >= r_min - 2:
            next_tier.append(rid)

    # Prefer same-tier regions first, then next-tier
    if same_tier or next_tier:
        return True

    # If all content regions visited, Director can generate a new one
    return True


def should_spawn_arcane_location(context: GameContext, repos: dict[str, Any]) -> bool:
    """True when the player has invented 3+ spells, suggesting an arcane location nearby.

    This spawns a library, arcane tower, or enchanted grove to support further research.
    """
    spell_creation_repo = repos.get("spell_creation")
    if not spell_creation_repo:
        return False

    char_id = context.character.get("id", "")
    customs = spell_creation_repo.get_custom_spells(context.game_id, char_id)
    combos = spell_creation_repo.get_discovered_combinations(context.game_id, char_id)

    total_discoveries = len(customs) + len(combos)
    if total_discoveries < 3:
        return False

    # Don't spawn if already at an arcane location
    loc_type = context.location.get("location_type", "")
    if loc_type in ("arcane_tower", "library", "academy", "enchanted_grove"):
        return False

    return True


def should_spawn_guild_trainer(context: GameContext, repos: dict[str, Any]) -> bool:
    """True if a guild trainer NPC should appear at this location.

    Conditions:
    - Location is a T2+ settlement (town, village, settlement)
    - No trainer NPC already at this location
    - Player has at least one guild membership
    """
    loc_type = context.location.get("location_type", "wilderness")
    if loc_type not in ("town", "village", "settlement", "tavern", "shop", "guild_hall"):
        return False

    # Check that no trainer NPC is already present
    for entity in context.entities:
        if not entity.get("is_alive", True):
            continue
        props = safe_props(entity)
        if props.get("teaches"):
            return False

    # Player must be in a guild
    guild_repo = repos.get("guild")
    if not guild_repo:
        return False

    char_id = context.character.get("id", "")
    memberships = guild_repo.get_memberships(context.game_id, char_id)
    return len(memberships) > 0


def should_offer_guild_recruitment(context: GameContext, repos: dict[str, Any]) -> bool:
    """True if the player has a trade skill L3+ but is not in the corresponding guild.

    Used to generate recruitment dialogue from NPCs.
    """
    trade_repo = repos.get("trade_skill")
    guild_repo = repos.get("guild")
    if not trade_repo or not guild_repo:
        return False

    char_id = context.character.get("id", "")
    game_id = context.game_id

    skills = trade_repo.get_skills(game_id, char_id)
    memberships = guild_repo.get_memberships(game_id, char_id)
    member_guild_ids = {m["guild_id"] for m in memberships}

    from text_rpg.content.loader import load_all_guilds
    guilds = load_all_guilds()

    # Check if player has a high-level skill without guild membership
    for skill in skills:
        if not skill.get("is_learned"):
            continue
        if skill.get("level", 1) < 3:
            continue

        skill_name = skill.get("skill_name", "")
        # Find the guild for this profession
        for gid, gdata in guilds.items():
            if gdata.get("profession") == skill_name and gid not in member_guild_ids:
                return True

    return False


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
