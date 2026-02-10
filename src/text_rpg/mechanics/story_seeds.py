"""Pure functions for the story seeds system — loading, selection, variable resolution."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


STORIES_DIR = Path(__file__).parent.parent / "content" / "stories"

BEAT_ORDER = ("hook", "development", "escalation", "resolution")


def load_all_seeds() -> list[dict]:
    """Load all story seeds from TOML files in content/stories/."""
    import tomllib

    seeds: list[dict] = []
    if not STORIES_DIR.exists():
        return seeds
    for f in STORIES_DIR.glob("*.toml"):
        if f.name == "world_events.toml":
            continue  # world events are separate
        with open(f, "rb") as fh:
            data = tomllib.load(fh)
        for seed in data.get("seeds", []):
            seed["_source_file"] = f.stem
            seeds.append(seed)
    return seeds


def select_seed(
    available_seeds: list[dict],
    game_state: dict,
    completed_ids: list[str] | None = None,
    active_tags: list[str] | None = None,
) -> dict | None:
    """Select a story seed via weighted random, respecting filters.

    Args:
        available_seeds: All loaded seeds.
        game_state: Current game state with turn_number, character level, etc.
        completed_ids: Seed IDs already completed/failed (no repeats).
        active_tags: Tags of currently active stories (for incompatibility check).

    Returns:
        Selected seed dict, or None if none eligible.
    """
    completed_ids = completed_ids or []
    active_tags = active_tags or []
    turn = game_state.get("turn_number", 0)
    level = game_state.get("character_level", 1)

    eligible: list[dict] = []
    weights: list[float] = []

    for seed in available_seeds:
        # Skip already completed
        if seed["id"] in completed_ids:
            continue

        # Check level range
        level_range = seed.get("level_range", [1, 20])
        if not (level_range[0] <= level <= level_range[1]):
            continue

        # Check incompatible tags
        incompatible = seed.get("incompatible_tags", [])
        if any(t in active_tags for t in incompatible):
            continue

        eligible.append(seed)
        weights.append(seed.get("weight", 1.0))

    if not eligible:
        return None

    return random.choices(eligible, weights=weights, k=1)[0]


def resolve_variables(seed: dict, context: Any) -> dict[str, str]:
    """Fill template variables like {settlement}, {npc}, etc. from context.

    Returns a dict mapping variable names to their resolved values.
    """
    resolved: dict[str, str] = {}

    # Find settlement (location_type == settlement/tavern/shop/temple)
    loc = context.location
    loc_type = loc.get("location_type", "")
    if loc_type in ("settlement", "tavern", "shop", "temple"):
        resolved["settlement"] = loc.get("name", "the settlement")
        resolved["settlement_id"] = loc.get("id", "")
    else:
        # Use location name as fallback
        resolved["settlement"] = loc.get("name", "the nearby village")
        resolved["settlement_id"] = loc.get("id", "")

    # Find wilderness location
    resolved["wilderness_location"] = "the nearby wilds"
    resolved["wilderness_location_id"] = ""

    # Find NPCs by role
    for entity in context.entities:
        if entity.get("entity_type") != "npc" or not entity.get("is_alive", True):
            continue
        name = entity.get("name", "someone")
        profession = (entity.get("profession") or "").lower()
        eid = entity.get("id", "")

        # Map professions to template variables
        if profession == "farmer" and "farmer" not in resolved:
            resolved["farmer"] = name
            resolved["farmer_id"] = eid
        elif profession == "guard" and "authority_npc" not in resolved:
            resolved["authority_npc"] = name
            resolved["authority_npc_id"] = eid
        elif profession == "healer" and "healer" not in resolved:
            resolved["healer"] = name
            resolved["healer_id"] = eid
        elif profession == "merchant" and "merchant" not in resolved:
            resolved["merchant"] = name
            resolved["merchant_id"] = eid
        elif profession == "innkeeper" and "innkeeper" not in resolved:
            resolved["innkeeper"] = name
            resolved["innkeeper_id"] = eid

        # Generic NPC fallback
        if "npc" not in resolved:
            resolved["npc"] = name
            resolved["npc_id"] = eid

    # Defaults for missing variables
    resolved.setdefault("npc", "a villager")
    resolved.setdefault("farmer", "a local farmer")
    resolved.setdefault("authority_npc", "the local authority")
    resolved.setdefault("healer", "a healer")
    resolved.setdefault("merchant", "a merchant")
    resolved.setdefault("innkeeper", "the innkeeper")

    return resolved


def fill_template(text: str, variables: dict[str, str]) -> str:
    """Replace {variable} placeholders in text."""
    for key, value in variables.items():
        text = text.replace(f"{{{key}}}", value)
    return text


def fill_templates(items: list[str], variables: dict[str, str]) -> list[str]:
    """Fill templates in a list of strings."""
    return [fill_template(t, variables) for t in items]


def check_beat_trigger(
    beat: dict,
    story_state: dict,
    game_state: dict,
) -> bool:
    """Check if a beat's trigger conditions are met.

    Args:
        beat: The beat definition from the seed.
        story_state: Current story tracking state.
        game_state: Current game state (turn_number, completed quests, etc.).
    """
    trigger_type = beat.get("trigger_type", "")
    turn = game_state.get("turn_number", 0)
    completed_quests = game_state.get("completed_quest_ids", [])
    beat_turns = story_state.get("beat_turn_numbers", {})

    if trigger_type == "turn_range":
        # Activate when turn is between min and max
        return beat.get("trigger_min", 0) <= turn <= beat.get("trigger_max", 999)

    elif trigger_type == "turn_offset":
        # Activate N turns after the previous beat was activated
        prev_beat = _previous_beat(story_state.get("current_beat", "hook"))
        prev_turn = beat_turns.get(prev_beat, 0)
        offset = beat.get("trigger_value", 20)
        return turn >= prev_turn + offset

    elif trigger_type == "quest_complete":
        # Activate when a specific quest is completed
        trigger_value = beat.get("trigger_value", "")
        if trigger_value == "hook_quest":
            quest_ids = story_state.get("quest_ids", [])
            return any(qid in completed_quests for qid in quest_ids)
        elif trigger_value == "escalation_quest":
            quest_ids = story_state.get("quest_ids", [])
            return any(qid in completed_quests for qid in quest_ids)
        return trigger_value in completed_quests

    return False


def get_narrator_hints(story_state: dict, seed: dict, variables: dict[str, str]) -> list[str]:
    """Get narrator hints from the current active beat."""
    current_beat = story_state.get("current_beat", "hook")
    beat = seed.get(current_beat, {})
    hints = beat.get("narrator_hints", [])
    return fill_templates(hints, variables)


def next_beat(current: str) -> str | None:
    """Return the next beat in sequence, or None if at resolution."""
    try:
        idx = BEAT_ORDER.index(current)
        if idx + 1 < len(BEAT_ORDER):
            return BEAT_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def _previous_beat(current: str) -> str:
    """Return the previous beat in sequence."""
    try:
        idx = BEAT_ORDER.index(current)
        if idx > 0:
            return BEAT_ORDER[idx - 1]
    except ValueError:
        pass
    return "hook"
