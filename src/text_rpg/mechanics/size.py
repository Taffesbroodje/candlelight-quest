"""Size mechanics — pure functions for Small/Medium/Large effects."""
from __future__ import annotations

SIZE_CATEGORIES: dict[str, int] = {"Small": -1, "Medium": 0, "Large": 1}


def carrying_capacity_multiplier(size: str) -> float:
    """Small: x0.5, Medium: x1, Large: x2."""
    if size == "Small":
        return 0.5
    if size == "Large":
        return 2.0
    return 1.0


def grapple_size_advantage(attacker_size: str, defender_size: str) -> tuple[bool, bool]:
    """Returns (advantage, disadvantage) for grapple checks.

    Larger vs smaller = advantage. Smaller vs larger = disadvantage.
    Can't grapple creatures 2+ sizes larger (returns False, True as auto-fail signal).
    """
    atk = SIZE_CATEGORIES.get(attacker_size, 0)
    dfn = SIZE_CATEGORIES.get(defender_size, 0)
    diff = atk - dfn

    if diff <= -2:
        # Can't grapple — too large a gap
        return False, True
    if diff >= 1:
        return True, False
    if diff <= -1:
        return False, True
    return False, False


def stealth_modifier(size: str) -> int:
    """Small: +2 bonus, Medium: 0, Large: -2 penalty."""
    rank = SIZE_CATEGORIES.get(size, 0)
    return -rank * 2


def intimidation_modifier(size: str) -> int:
    """Small: -2 penalty, Medium: 0, Large: +2 bonus."""
    rank = SIZE_CATEGORIES.get(size, 0)
    return rank * 2


def squeeze_through_narrow(size: str) -> dict:
    """Returns movement cost and disadvantage info for squeezing.

    Large: costs double movement through normal passages, attack disadvantage.
    Small: can squeeze through tiny openings.
    Medium: normal movement.
    """
    if size == "Large":
        return {
            "movement_multiplier": 2,
            "attack_disadvantage": True,
            "can_squeeze_tiny": False,
            "description": "You must squeeze through, costing double movement with attack disadvantage.",
        }
    if size == "Small":
        return {
            "movement_multiplier": 1,
            "attack_disadvantage": False,
            "can_squeeze_tiny": True,
            "description": "Your small frame lets you squeeze through tiny openings.",
        }
    return {
        "movement_multiplier": 1,
        "attack_disadvantage": False,
        "can_squeeze_tiny": False,
        "description": "Normal movement.",
    }
