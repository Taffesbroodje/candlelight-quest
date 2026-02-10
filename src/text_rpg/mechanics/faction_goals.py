"""Pure functions for faction goal resolution and world event checks."""
from __future__ import annotations

import random
from typing import Any


def check_faction_goals(
    factions: dict[str, dict],
    turn_number: int,
    last_checked: dict[str, int] | None = None,
) -> list[dict]:
    """Check all faction goals and resolve any that are due.

    Args:
        factions: Faction data from TOML (keyed by faction_id).
        turn_number: Current game turn.
        last_checked: Dict mapping goal_id -> last turn checked.

    Returns:
        List of event dicts (success/failure) for goals that resolved this turn.
    """
    last_checked = last_checked or {}
    events: list[dict] = []

    for faction_id, faction in factions.items():
        goals = faction.get("goals", [])
        for goal in goals:
            goal_id = goal.get("id", "")
            interval = goal.get("check_interval", 20)
            last = last_checked.get(f"{faction_id}_{goal_id}", 0)

            if turn_number - last < interval:
                continue

            # Roll for success
            success_chance = goal.get("success_chance", 0.5)
            success = random.random() < success_chance

            if success:
                events.append({
                    "event_type": "FACTION_GOAL",
                    "description": goal.get("success_event", f"{faction.get('name', faction_id)} succeeded at {goal.get('description', 'a goal')}."),
                    "mechanical_details": {
                        "faction_id": faction_id,
                        "goal_id": goal_id,
                        "success": True,
                        "effects": goal.get("success_effects", []),
                    },
                })
            else:
                events.append({
                    "event_type": "FACTION_GOAL",
                    "description": goal.get("failure_event", f"{faction.get('name', faction_id)} failed at {goal.get('description', 'a goal')}."),
                    "mechanical_details": {
                        "faction_id": faction_id,
                        "goal_id": goal_id,
                        "success": False,
                        "effects": goal.get("failure_effects", []),
                    },
                })

    return events


def check_world_events(
    events_pool: list[dict],
    turn_number: int,
    world_time: int,
    location_type: str,
    cooldowns: dict[str, int] | None = None,
) -> list[dict]:
    """Check world events and return any that trigger this turn.

    Args:
        events_pool: All world events from TOML.
        turn_number: Current game turn.
        world_time: Current world time in minutes (for period check).
        location_type: Current location type (settlement, wilderness, etc.).
        cooldowns: Dict mapping event_id -> last triggered turn.

    Returns:
        List of triggered event dicts (usually 0-1 per turn).
    """
    from text_rpg.mechanics.world_clock import get_period

    cooldowns = cooldowns or {}
    period = get_period(world_time)
    triggered: list[dict] = []

    for event in events_pool:
        event_id = event.get("id", "")
        probability = event.get("probability", 0.05)
        cooldown = event.get("cooldown", 20)

        # Check cooldown
        last_triggered = cooldowns.get(event_id, 0)
        if turn_number - last_triggered < cooldown:
            continue

        # Check conditions
        conditions = event.get("conditions", {})
        if conditions:
            # Period filter
            allowed_periods = conditions.get("period", [])
            if allowed_periods and period not in allowed_periods:
                continue
            # Location type filter
            allowed_loc_types = conditions.get("location_type")
            if allowed_loc_types:
                if isinstance(allowed_loc_types, str):
                    allowed_loc_types = [allowed_loc_types]
                if location_type not in allowed_loc_types:
                    continue

        # Roll for trigger
        if random.random() < probability:
            triggered.append(event)

    # Only return one event per turn to avoid spam
    if triggered:
        return [random.choice(triggered)]
    return []


def apply_goal_effects(
    effects: list[dict],
    game_id: str,
    repos: dict[str, Any],
) -> None:
    """Apply effects from faction goals (faction rep changes, etc.)."""
    rep_repo = repos.get("reputation")
    if not rep_repo:
        return

    for effect in effects:
        effect_type = effect.get("type", "")
        if effect_type == "faction_rep":
            faction_id = effect.get("faction_id", "")
            delta = effect.get("delta", 0)
            if faction_id and delta:
                rep_repo.adjust_faction_rep(game_id, faction_id, delta)
