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
