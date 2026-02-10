"""Death penalty mechanics — pure calculations, no I/O.

When a player is defeated in combat:
- Lose 25% of gold
- Get teleported to last safe location (settlement)
- Gain 'weakened' condition for 5 turns (-2 to all checks)
"""
from __future__ import annotations

import random


def calculate_death_penalty(gold: int) -> dict:
    """Calculate gold lost on death. Returns {"gold_lost": int}."""
    gold_lost = gold // 4  # 25% loss
    return {"gold_lost": gold_lost}


def get_weakened_condition() -> dict:
    """Return the 'weakened' condition applied after death.

    Duration: 5 turns, -2 to all ability checks.
    """
    return {
        "name": "weakened",
        "description": "Recently defeated. -2 to all ability checks.",
        "penalty": -2,
        "duration_turns": 5,
        "turns_remaining": 5,
    }


def find_safe_location(locations: list[dict]) -> str | None:
    """Find the best safe location to respawn at.

    Prefers settlements (villages, towns), then any visited location.
    Returns location_id or None.
    """
    settlements = []
    visited = []

    for loc in locations:
        if not loc.get("visited"):
            continue
        visited.append(loc["id"])
        loc_type = (loc.get("location_type") or loc.get("type") or "").lower()
        if loc_type in ("village", "town", "settlement", "city"):
            settlements.append(loc["id"])
        elif "village" in loc.get("name", "").lower() or "town" in loc.get("name", "").lower():
            settlements.append(loc["id"])

    if settlements:
        return settlements[0]
    if visited:
        return visited[0]
    return None
