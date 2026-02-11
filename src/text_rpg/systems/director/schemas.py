"""Validation schemas for Director-generated content."""
from __future__ import annotations

import uuid


def validate_npc(data: dict) -> dict:
    """Validate and normalize a generated NPC dict. Returns cleaned data or raises ValueError."""
    required = {"name", "description"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Generated NPC missing required fields: {missing}")

    name = str(data["name"]).strip()
    if not name or len(name) > 100:
        raise ValueError(f"Invalid NPC name: '{name}'")

    # Ensure sensible stat ranges
    scores = data.get("ability_scores", {})
    for ability in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
        val = scores.get(ability, 10)
        if not isinstance(val, (int, float)):
            scores[ability] = 10
        else:
            scores[ability] = max(1, min(30, int(val)))
    data["ability_scores"] = scores

    hp = data.get("hp_max", 10)
    if not isinstance(hp, (int, float)) or hp < 1:
        hp = 10
    hp = int(hp)
    data["hp_max"] = hp
    data["hp_current"] = data.get("hp_current", hp)

    ac = data.get("ac", 10)
    if not isinstance(ac, (int, float)) or ac < 1 or ac > 30:
        ac = 10
    data["ac"] = int(ac)

    # Ensure required defaults
    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("entity_type", "npc")
    data.setdefault("dialogue_tags", [])
    data.setdefault("behaviors", [])
    data.setdefault("attacks", [])
    data.setdefault("loot_table", [])
    data.setdefault("is_hostile", False)
    data.setdefault("is_alive", True)
    data.setdefault("generated", True)
    data.setdefault("speed", 30)
    data.setdefault("level", 1)
    data.setdefault("hp_temp", 0)
    data.setdefault("properties", {})

    return data


def validate_location(data: dict) -> dict:
    """Validate and normalize a generated location dict."""
    required = {"name", "description"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Generated location missing required fields: {missing}")

    name = str(data["name"]).strip()
    if not name or len(name) > 100:
        raise ValueError(f"Invalid location name: '{name}'")

    # Ensure connections is a list
    connections = data.get("connections", [])
    if not isinstance(connections, list):
        connections = []
    data["connections"] = connections

    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("location_type", "wilderness")
    data.setdefault("entities", [])
    data.setdefault("items", [])
    data.setdefault("visited", False)
    data.setdefault("generated", True)
    data.setdefault("properties", {})

    return data


def validate_quest(data: dict) -> dict:
    """Validate and normalize a generated quest dict."""
    required = {"name", "description"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Generated quest missing required fields: {missing}")

    objectives = data.get("objectives", [])
    if not isinstance(objectives, list):
        objectives = []
    # Ensure each objective has required fields
    cleaned_objectives = []
    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        obj.setdefault("id", str(uuid.uuid4()))
        obj.setdefault("description", "Complete the objective")
        obj.setdefault("is_complete", False)
        obj.setdefault("required_count", 1)
        obj.setdefault("current_count", 0)
        obj.setdefault("negotiable", False)
        cleaned_objectives.append(obj)
    data["objectives"] = cleaned_objectives

    data.setdefault("id", str(uuid.uuid4()))
    data.setdefault("status", "active")
    data.setdefault("xp_reward", 50)
    data.setdefault("item_rewards", [])
    data.setdefault("gold_reward", 0)
    data.setdefault("level_requirement", 1)
    data.setdefault("generated", True)
    data.setdefault("npc_motivation", "")
    data.setdefault("completion_flexibility", "low")

    return data


def validate_region(data: dict) -> dict:
    """Validate and normalize a generated region dict."""
    required = {"name", "description"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Generated region missing required fields: {missing}")

    name = str(data["name"]).strip()
    if not name or len(name) > 100:
        raise ValueError(f"Invalid region name: '{name}'")

    data.setdefault("id", str(uuid.uuid4()).replace("-", "_"))
    data.setdefault("climate", "temperate")
    data.setdefault("level_range_min", 1)
    data.setdefault("level_range_max", 5)

    # Clamp level ranges
    data["level_range_min"] = max(1, min(20, int(data["level_range_min"])))
    data["level_range_max"] = max(data["level_range_min"], min(20, int(data["level_range_max"])))

    # Validate locations list
    locations = data.get("locations", [])
    if not isinstance(locations, list):
        locations = []
    cleaned_locations = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        loc.setdefault("id", str(uuid.uuid4()))
        loc.setdefault("name", "Unknown Location")
        loc.setdefault("description", "An unexplored area.")
        loc.setdefault("location_type", "wilderness")
        loc.setdefault("connections", [])
        loc.setdefault("entities", [])
        loc.setdefault("items", [])
        loc.setdefault("visited", False)
        loc.setdefault("properties", {})
        cleaned_locations.append(loc)
    data["locations"] = cleaned_locations

    # Validate NPCs list
    npcs = data.get("npcs", [])
    if not isinstance(npcs, list):
        npcs = []
    cleaned_npcs = []
    for npc in npcs:
        if not isinstance(npc, dict):
            continue
        try:
            cleaned_npcs.append(validate_npc(npc))
        except ValueError:
            continue
    data["npcs"] = cleaned_npcs

    return data


def validate_plausibility(data: dict) -> dict:
    """Validate plausibility evaluation output."""
    if not isinstance(data, dict):
        data = {"plausibility": 0.5}
    p = data.get("plausibility", 0.5)
    if not isinstance(p, (int, float)):
        p = 0.5
    data["plausibility"] = max(0.001, min(1.0, float(p)))

    data.setdefault("skill", "athletics")
    data.setdefault("ability", "strength")
    data.setdefault("reasoning", "")
    data.setdefault("success_description", "You succeed.")
    data.setdefault("failure_description", "You fail.")

    return data


def validate_spell_proposal(data: dict) -> dict:
    """Validate LLM-generated spell proposal output."""
    if not isinstance(data, dict):
        data = {}

    data.setdefault("name", "Unknown Spell")
    data.setdefault("description", "A mysterious magical effect.")
    data.setdefault("reasoning", "")

    # Clamp level to 0-6
    level = data.get("level", 1)
    if not isinstance(level, (int, float)):
        level = 1
    data["level"] = max(0, min(6, int(level)))

    # Validate school
    valid_schools = {
        "abjuration", "conjuration", "divination", "enchantment",
        "evocation", "illusion", "necromancy", "transmutation",
    }
    school = data.get("school", "evocation")
    if school not in valid_schools:
        data["school"] = "evocation"

    # Clamp plausibility
    p = data.get("plausibility", 0.5)
    if not isinstance(p, (int, float)):
        p = 0.5
    data["plausibility"] = max(0.001, min(1.0, float(p)))

    # Ensure elements is a list
    elements = data.get("elements", [])
    if not isinstance(elements, list):
        elements = []
    data["elements"] = elements

    # Ensure mechanics is a dict with a type
    mechanics = data.get("mechanics", {})
    if not isinstance(mechanics, dict):
        mechanics = {}
    mechanics.setdefault("type", "utility")
    data["mechanics"] = mechanics

    return data
