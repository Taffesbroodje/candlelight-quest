"""LLM-powered content generators for the Director."""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from text_rpg.llm.provider import LLMProvider
from text_rpg.systems.base import GameContext
from text_rpg.systems.director.schemas import (
    validate_location,
    validate_npc,
    validate_plausibility,
    validate_quest,
)
from text_rpg.utils import safe_json, safe_props

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "llm" / "prompts"
_jinja_env: Environment | None = None


def _get_jinja() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=False,
        )
    return _jinja_env


# -- Context formatters (concise summaries for LLM prompts) --

def _format_character(char: dict) -> str:
    scores = safe_json(char.get("ability_scores"), {})
    profs = safe_json(char.get("skill_proficiencies"), [])
    return (
        f"{char.get('name', 'Unknown')} — Level {char.get('level', 1)} "
        f"{char.get('race', '?')} {char.get('char_class', '?')}\n"
        f"HP: {char.get('hp_current', 0)}/{char.get('hp_max', 0)} | AC: {char.get('ac', 10)}\n"
        f"STR {scores.get('strength', 10)} DEX {scores.get('dexterity', 10)} "
        f"CON {scores.get('constitution', 10)} INT {scores.get('intelligence', 10)} "
        f"WIS {scores.get('wisdom', 10)} CHA {scores.get('charisma', 10)}\n"
        f"Skills: {', '.join(profs) if profs else 'none'}"
    )


def _format_location(loc: dict) -> str:
    connections = safe_json(loc.get("connections"), [])
    exits = ", ".join(
        c.get("direction", "?") for c in connections if isinstance(c, dict)
    )
    return (
        f"{loc.get('name', 'Unknown')} ({loc.get('location_type', 'unknown')})\n"
        f"{loc.get('description', 'No description.')}\n"
        f"Exits: {exits if exits else 'none'}"
    )


def _format_entities(entities: list[dict]) -> str:
    if not entities:
        return "None present."
    parts = []
    for e in entities:
        if e.get("is_alive", True):
            parts.append(f"- {e['name']}: {e.get('description', 'No description.')[:100]}")
    return "\n".join(parts) if parts else "None present."


def _format_recent_events(events: list[dict]) -> str:
    if not events:
        return "Nothing notable has happened recently."
    parts = []
    for e in events[:5]:
        parts.append(f"- [{e.get('event_type', '?')}] {e.get('description', '')[:100]}")
    return "\n".join(parts)


def _format_inventory(inventory: dict | None) -> str:
    if not inventory:
        return "Empty pack."
    items = safe_json(inventory.get("items"), [])
    if not items:
        return "Empty pack."
    parts = [f"- {i.get('item_id', '?')} x{i.get('quantity', 1)}" for i in items[:10]]
    return "\n".join(parts)


# -- Generators --

def generate_npc(
    llm: LLMProvider,
    context: GameContext,
    location: dict,
    constraints: dict,
) -> dict:
    """Generate a new NPC fitting the given location. Returns validated NPC dict."""
    env = _get_jinja()
    template = env.get_template("director/npc_generation.j2")

    existing_npcs = _format_entities(context.entities)

    prompt = template.render(
        location_summary=_format_location(location),
        location_type=location.get("location_type", "wilderness"),
        region_name=location.get("region_id", "unknown"),
        character_summary=_format_character(context.character),
        existing_npcs=existing_npcs,
        world_context=_format_recent_events(context.recent_events),
    )

    raw = llm.generate_structured(prompt, temperature=0.9, max_tokens=512)
    npc_data = validate_npc(raw)

    # Assign faction based on location type / region
    loc_type = location.get("location_type", "wilderness")
    region = location.get("region_id", "unknown")
    if loc_type in ("town", "village", "settlement", "tavern", "shop"):
        npc_data.setdefault("faction_id", f"{region}_guard" if npc_data.get("is_hostile") else f"{region}_merchants")
    return npc_data


def generate_location(
    llm: LLMProvider,
    context: GameContext,
    direction: str,
    source_location: dict,
) -> dict:
    """Generate a new location in a given direction. Returns validated location dict."""
    env = _get_jinja()
    template = env.get_template("director/location_generation.j2")

    # Build list of existing locations from connections
    connections = safe_json(source_location.get("connections"), [])
    existing = ", ".join(
        c.get("description", c.get("target_location_id", "?"))
        for c in connections if isinstance(c, dict)
    )

    props = safe_props(source_location)

    prompt = template.render(
        source_location_summary=_format_location(source_location),
        direction=direction,
        region_description=props.get("region_description", source_location.get("description", "")),
        player_level=context.character.get("level", 1),
        existing_locations=existing if existing else "None known nearby.",
    )

    raw = llm.generate_structured(prompt, temperature=0.9, max_tokens=512)
    return validate_location(raw)


def generate_quest(
    llm: LLMProvider,
    context: GameContext,
    npc: dict,
) -> dict:
    """Generate a quest from an NPC's motivation. Returns validated quest dict."""
    env = _get_jinja()
    template = env.get_template("director/quest_generation.j2")

    props = safe_props(npc)

    prompt = template.render(
        npc_name=npc.get("name", "Unknown"),
        npc_description=npc.get("description", ""),
        npc_personality=", ".join(npc.get("dialogue_tags") or []),
        npc_motivation=props.get("motivation", "unknown"),
        quest_hook=props.get("quest_hook", "has a problem"),
        character_summary=_format_character(context.character),
        location_summary=_format_location(context.location),
        recent_events_summary=_format_recent_events(context.recent_events),
    )

    raw = llm.generate_structured(prompt, temperature=0.8, max_tokens=512)
    return validate_quest(raw)


def generate_follow_up_quest(
    llm: LLMProvider,
    context: GameContext,
    completed_quest: dict,
) -> dict:
    """Generate a follow-up quest after completion. Returns validated quest dict."""
    env = _get_jinja()
    template = env.get_template("director/quest_generation.j2")

    # Re-use quest_generation template with follow-up context
    prompt = template.render(
        npc_name="the quest giver",
        npc_description="The person who gave you the previous quest.",
        npc_personality="grateful, thoughtful",
        npc_motivation=f"Follow-up to completed quest: {completed_quest.get('name', 'unknown')}",
        quest_hook=f"After completing '{completed_quest.get('name', '')}', a new situation has arisen.",
        character_summary=_format_character(context.character),
        location_summary=_format_location(context.location),
        recent_events_summary=_format_recent_events(context.recent_events),
    )

    raw = llm.generate_structured(prompt, temperature=0.8, max_tokens=512)
    data = validate_quest(raw)

    # Track chain depth
    old_props = safe_props(completed_quest)
    chain_depth = old_props.get("chain_depth", 0) + 1
    data.setdefault("properties", {})
    data["properties"] = safe_json(data["properties"], {})
    data["properties"]["chain_depth"] = chain_depth
    data["properties"]["predecessor_quest_id"] = completed_quest.get("id")

    return data


def evaluate_plausibility(
    llm: LLMProvider,
    action_description: str,
    context: GameContext,
) -> dict:
    """Evaluate how plausible a creative player action is. Returns validated dict."""
    env = _get_jinja()
    template = env.get_template("director/plausibility_check.j2")

    prompt = template.render(
        action_description=action_description,
        character_summary=_format_character(context.character),
        location_summary=_format_location(context.location),
        entities_summary=_format_entities(context.entities),
        recent_events_summary=_format_recent_events(context.recent_events),
        inventory_summary=_format_inventory(context.inventory),
    )

    raw = llm.generate_structured(prompt, temperature=0.7, max_tokens=512)
    return validate_plausibility(raw)


def evaluate_creative_solution(
    llm: LLMProvider,
    quest: dict,
    player_action: str,
    context: GameContext,
) -> dict:
    """Evaluate if a creative approach satisfies a quest."""
    env = _get_jinja()
    template = env.get_template("director/evaluate_creative_solution.j2")

    objectives = safe_json(quest.get("objectives"), [])

    prompt = template.render(
        quest_name=quest.get("name", "Unknown"),
        quest_description=quest.get("description", ""),
        npc_motivation=quest.get("npc_motivation", "unknown"),
        completion_flexibility=quest.get("completion_flexibility", "low"),
        objectives=objectives,
        player_action=player_action,
        context_summary=_format_location(context.location),
    )

    raw = llm.generate_structured(prompt, temperature=0.7, max_tokens=512)

    # Validate basics
    raw.setdefault("satisfies_quest", False)
    raw.setdefault("reasoning", "")
    raw.setdefault("npc_reaction", "")
    raw.setdefault("partial_credit", False)
    raw.setdefault("xp_modifier", 1.0)
    return raw


def negotiate_quest(
    llm: LLMProvider,
    quest: dict,
    npc: dict,
    player_proposal: str,
    check_total: int,
    check_dc: int,
    check_success: bool,
) -> dict:
    """Evaluate a player's quest negotiation attempt."""
    env = _get_jinja()
    template = env.get_template("director/negotiate_quest.j2")

    props = safe_props(npc)
    relationships = props.get("relationships", {})
    player_rel = relationships.get("player", {})

    objectives = safe_json(quest.get("objectives"), [])

    prompt = template.render(
        npc_name=npc.get("name", "Unknown"),
        npc_personality=", ".join(npc.get("dialogue_tags") or []),
        disposition=player_rel.get("disposition", "neutral"),
        trust_level=player_rel.get("trust", 0),
        quest_name=quest.get("name", "Unknown"),
        quest_description=quest.get("description", ""),
        npc_motivation=quest.get("npc_motivation", "unknown"),
        objectives=objectives,
        player_proposal=player_proposal,
        check_total=check_total,
        check_dc=check_dc,
        check_success=check_success,
    )

    raw = llm.generate_structured(prompt, temperature=0.7, max_tokens=512)

    # Validate basics
    raw.setdefault("accepted", False)
    raw.setdefault("modified_objectives", objectives)
    raw.setdefault("npc_response", "The NPC considers your words carefully.")
    raw.setdefault("disposition_change", 0)
    return raw


def plausibility_to_dc(plausibility: float) -> int:
    """Map a plausibility score (0.001–1.0) to a D&D-style DC (5–40).

    Uses a logarithmic scale:
    1.0  → DC 5   (trivial)
    0.8  → DC 8
    0.5  → DC 12  (standard)
    0.3  → DC 15
    0.1  → DC 20
    0.05 → DC 25
    0.01 → DC 30
    0.001→ DC 40
    """
    p = max(0.001, min(1.0, plausibility))
    # Logarithmic mapping: DC = 5 - 8.33 * ln(p)
    dc = 5 - 8.33 * math.log(p)
    return max(5, min(40, round(dc)))
