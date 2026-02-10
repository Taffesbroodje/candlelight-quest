"""Companion AI and movement mechanics."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.combat_math import npc_choose_action
from text_rpg.models.action import StateMutation
from text_rpg.utils import safe_json


MAX_ACTIVE_COMPANIONS = 2


def companion_ai_action(companion: dict, enemies: list[dict]) -> dict[str, Any]:
    """Choose a combat action for a companion. Reuses NPC AI but targets enemies."""
    return npc_choose_action(companion, enemies)


def companion_follow(companion_entity_id: str, new_location_id: str) -> StateMutation:
    """Create a mutation to move a companion to a new location."""
    return StateMutation(
        target_type="entity",
        target_id=companion_entity_id,
        field="location_id",
        old_value=None,
        new_value=new_location_id,
    )


def can_recruit_companion(active_companions: list[dict]) -> bool:
    """Check if the player can recruit another companion."""
    active = [c for c in active_companions if c.get("status") == "active"]
    return len(active) < MAX_ACTIVE_COMPANIONS


def build_companion_combatant(entity: dict) -> dict:
    """Build a combat combatant entry from a companion entity."""
    scores = safe_json(entity.get("ability_scores"), {})
    dex_mod = modifier(scores.get("dexterity", 10))

    from text_rpg.mechanics.combat_math import initiative_roll
    init = initiative_roll(dex_mod)

    return {
        "entity_id": entity["id"],
        "name": entity.get("name", "Companion"),
        "combatant_type": "companion",
        "initiative": init.total,
        "initiative_bonus": dex_mod,
        "hp": {
            "current": entity.get("hp_current", 10),
            "max": entity.get("hp_max", 10),
            "temp": 0,
        },
        "ac": entity.get("ac", 10),
        "is_active": True,
        "conditions": [],
        "has_acted": False,
    }
