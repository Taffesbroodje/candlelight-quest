"""Reputation mechanics — pure functions, no I/O."""
from __future__ import annotations

REPUTATION_TIERS = {
    (-100, -61): "hated",
    (-60, -21): "hostile",
    (-20, -6): "unfriendly",
    (-5, 5): "neutral",
    (6, 20): "friendly",
    (21, 60): "trusted",
    (61, 100): "honored",
}

REPUTATION_EFFECTS = {
    "hated": {"shop_price_mult": 2.0, "quest_available": False, "attack_on_sight": True},
    "hostile": {"shop_price_mult": 1.5, "quest_available": False, "attack_on_sight": False},
    "unfriendly": {"shop_price_mult": 1.25, "quest_available": False, "attack_on_sight": False},
    "neutral": {"shop_price_mult": 1.0, "quest_available": True, "attack_on_sight": False},
    "friendly": {"shop_price_mult": 0.9, "quest_available": True, "attack_on_sight": False},
    "trusted": {"shop_price_mult": 0.75, "quest_available": True, "attack_on_sight": False},
    "honored": {"shop_price_mult": 0.5, "quest_available": True, "attack_on_sight": False},
}

# Maps action types to faction reputation deltas.
# Positive = good, negative = bad. Context can modify these.
_ACTION_DELTAS = {
    "kill_npc": -15,
    "kill_hostile": 5,
    "complete_quest": 10,
    "fail_quest": -5,
    "steal": -10,
    "help": 5,
    "donate": 8,
    "assault": -12,
    "trespass": -3,
}


def get_tier(reputation: int) -> str:
    """Return the named tier for a reputation value."""
    rep = clamp_reputation(reputation)
    for (low, high), tier_name in REPUTATION_TIERS.items():
        if low <= rep <= high:
            return tier_name
    return "neutral"


def clamp_reputation(value: int) -> int:
    """Clamp reputation to [-100, 100]."""
    return max(-100, min(100, value))


def adjust_reputation(current: int, delta: int) -> int:
    """Adjust reputation by delta and clamp."""
    return clamp_reputation(current + delta)


def get_effects(reputation: int) -> dict:
    """Get the gameplay effects for a reputation value."""
    tier = get_tier(reputation)
    return dict(REPUTATION_EFFECTS.get(tier, REPUTATION_EFFECTS["neutral"]))


def reputation_from_action(action_type: str, context: dict | None = None) -> dict[str, int]:
    """Return {faction_id: delta} for a given action.

    Args:
        action_type: One of the _ACTION_DELTAS keys.
        context: Optional dict with 'faction_id', 'opposing_faction_id', 'witnesses'.

    Returns:
        Dict mapping faction_id to reputation delta.
    """
    context = context or {}
    base_delta = _ACTION_DELTAS.get(action_type, 0)
    if base_delta == 0:
        return {}

    result: dict[str, int] = {}

    faction_id = context.get("faction_id")
    if faction_id:
        # Witnesses increase the magnitude
        witnesses = context.get("witnesses", 0)
        multiplier = 1.0 + (0.25 * min(witnesses, 4))
        result[faction_id] = int(base_delta * multiplier)

    # Opposing faction gets inverse (half magnitude)
    opposing = context.get("opposing_faction_id")
    if opposing and opposing != faction_id:
        result[opposing] = int(-base_delta * 0.5)

    return result
