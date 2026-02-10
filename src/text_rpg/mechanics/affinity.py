"""Affinity system — NPC relationship tiers with mechanical effects."""
from __future__ import annotations

from typing import Any

# Affinity tiers ordered by threshold
AFFINITY_TIERS = [
    {"name": "Stranger", "min_score": 0, "shop_discount": 0.0},
    {"name": "Acquaintance", "min_score": 5, "shop_discount": 0.0},
    {"name": "Companion", "min_score": 15, "shop_discount": 0.05},
    {"name": "Friend", "min_score": 30, "shop_discount": 0.10},
    {"name": "Close Friend", "min_score": 50, "shop_discount": 0.15},
    {"name": "Trusted Ally", "min_score": 75, "shop_discount": 0.20},
    {"name": "Sworn Bond", "min_score": 100, "shop_discount": 0.25},
]

# Required affinity to recruit as a companion
RECRUIT_THRESHOLD = 15  # "Companion" tier


def get_tier(score: int) -> dict:
    """Get the affinity tier for a given score."""
    tier = AFFINITY_TIERS[0]
    for t in AFFINITY_TIERS:
        if score >= t["min_score"]:
            tier = t
    return tier


def get_tier_name(score: int) -> str:
    """Get just the tier name for a score."""
    return get_tier(score)["name"]


def get_shop_discount(score: int) -> float:
    """Get the shop price discount based on affinity."""
    return get_tier(score)["shop_discount"]


def can_recruit(score: int) -> bool:
    """Check if affinity is high enough to recruit as companion."""
    return score >= RECRUIT_THRESHOLD


def affinity_from_gift(item_id: str, npc_preferences: dict) -> int:
    """Calculate affinity change from giving a gift.

    Args:
        item_id: The item being given
        npc_preferences: Dict with 'preferred_gifts' and 'disliked_gifts' lists

    Returns:
        Affinity change: +5 preferred, +2 neutral, -2 disliked
    """
    preferred = npc_preferences.get("preferred_gifts", [])
    disliked = npc_preferences.get("disliked_gifts", [])

    if item_id in preferred:
        return 5
    elif item_id in disliked:
        return -2
    return 2


def affinity_from_action(action_type: str) -> int:
    """Get affinity change for common actions."""
    changes = {
        "complete_quest": 5,
        "help_npc": 3,
        "successful_persuasion": 2,
        "conversation": 1,
        "failed_intimidation": -3,
        "theft_witnessed": -5,
        "attack_npc": -10,
        "kill_ally": -20,
    }
    return changes.get(action_type, 0)


def clamp_affinity(value: int) -> int:
    """Clamp affinity to valid range."""
    return max(0, min(100, value))
