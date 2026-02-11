"""Behavior tracker — analyzes event history to detect player patterns.

Pure functions, no I/O. Used by the trait system to determine what
dynamic traits the player has earned through their playstyle.
"""
from __future__ import annotations

import re
from typing import Any

# Behavior categories and their trigger conditions.
# Each category maps event types + optional filters to accumulate a score.
BEHAVIOR_CATEGORIES: dict[str, dict[str, Any]] = {
    "fire_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "fire",
        "description": "Frequent use of fire damage",
    },
    "cold_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "cold",
        "description": "Frequent use of cold damage",
    },
    "lightning_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "lightning",
        "description": "Frequent use of lightning damage",
    },
    "radiant_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "radiant",
        "description": "Frequent use of radiant damage",
    },
    "necrotic_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "necrotic",
        "description": "Frequent use of necrotic damage",
    },
    "melee_combat": {
        "event_types": ["ATTACK"],
        "filter": "melee",
        "description": "Preference for melee combat",
    },
    "ranged_combat": {
        "event_types": ["ATTACK"],
        "filter": "ranged",
        "description": "Preference for ranged combat",
    },
    "spell_mastery": {
        "event_types": ["SPELL_CAST"],
        "filter": None,
        "description": "Heavy spellcasting usage",
    },
    "healer": {
        "event_types": ["HEAL", "SPELL_CAST"],
        "filter": "heal",
        "description": "Frequent healing of others",
    },
    "stealth_operative": {
        "event_types": ["SKILL_CHECK"],
        "filter": "stealth",
        "description": "Reliance on stealth tactics",
    },
    "social_adept": {
        "event_types": ["DIALOGUE", "SKILL_CHECK"],
        "filter": "persuasion|deception|intimidation",
        "description": "Social and persuasive approach",
    },
    "explorer": {
        "event_types": ["MOVE", "LOCATION_DISCOVER", "DISCOVERY"],
        "filter": None,
        "description": "Love of exploration and discovery",
    },
    "resilience": {
        "event_types": ["DAMAGE_TAKEN", "ATTACK"],
        "filter": "npc_attack",
        "description": "Enduring significant damage",
    },
    "protector": {
        "event_types": ["ALLY_DEFENDED", "CLASS_ABILITY"],
        "filter": "defend|protect|lay_on_hands|bardic_inspiration",
        "description": "Defending allies in combat",
    },
    "crafter": {
        "event_types": ["CRAFT", "CRAFT_SUCCESS"],
        "filter": None,
        "description": "Dedication to crafting",
    },
    "quest_achiever": {
        "event_types": ["QUEST_COMPLETE"],
        "filter": None,
        "description": "Prolific quest completion",
    },
    "poison_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "poison",
        "description": "Frequent use of poison damage",
    },
    "psychic_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "psychic",
        "description": "Frequent use of psychic damage",
    },
    "force_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "force",
        "description": "Frequent use of force damage",
    },
    "thunder_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "thunder",
        "description": "Frequent use of thunder damage",
    },
    "acid_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "acid",
        "description": "Frequent use of acid damage",
    },
    "water_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "water",
        "description": "Frequent use of water damage",
    },
    "earth_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "earth",
        "description": "Frequent use of earth damage",
    },
    "wind_affinity": {
        "event_types": ["SPELL_CAST", "ATTACK"],
        "filter": "wind",
        "description": "Frequent use of wind damage",
    },
    "spell_inventor": {
        "event_types": ["SPELL_CREATED", "SPELL_COMBINED"],
        "filter": None,
        "description": "Creating and combining new spells",
    },
    "guild_worker": {
        "event_types": ["WORK_ORDER_COMPLETE", "GUILD_RANK_UP"],
        "filter": None,
        "description": "Dedication to guild work and profession advancement",
    },
}


def _event_matches_filter(event: dict, filter_str: str | None) -> bool:
    """Check if an event's details match a filter string.

    Filter can be a simple string (exact match in description/details)
    or pipe-separated alternatives (e.g. "persuasion|deception|intimidation").
    """
    if filter_str is None:
        return True

    # Build search text from event description + mechanical details (keys AND values)
    desc = (event.get("description") or "").lower()
    details = event.get("mechanical_details", {})
    if isinstance(details, str):
        details_text = details.lower()
    elif isinstance(details, dict):
        details_text = " ".join(
            f"{k} {v}" for k, v in details.items()
        ).lower()
    else:
        details_text = ""

    search_text = f"{desc} {details_text}"

    # Check each alternative in the filter
    for alt in filter_str.split("|"):
        if alt.strip().lower() in search_text:
            return True
    return False


def analyze_behavior(events: list[dict], character: dict) -> dict[str, int]:
    """Count behavior scores from event history.

    Scans all events and increments category counters based on
    event_type matching and optional filter matching.

    Returns {category_name: count}.
    """
    scores: dict[str, int] = {cat: 0 for cat in BEHAVIOR_CATEGORIES}

    for event in events:
        event_type = event.get("event_type", "")
        for cat_name, cat_def in BEHAVIOR_CATEGORIES.items():
            if event_type in cat_def["event_types"]:
                if _event_matches_filter(event, cat_def.get("filter")):
                    scores[cat_name] += 1

    return scores


def get_dominant_patterns(
    behavior_scores: dict[str, int],
    threshold: int = 10,
) -> list[str]:
    """Return behavior categories above threshold, sorted by score descending.

    Only categories with a score >= threshold are considered "dominant".
    """
    dominant = [
        (cat, score)
        for cat, score in behavior_scores.items()
        if score >= threshold
    ]
    dominant.sort(key=lambda x: x[1], reverse=True)
    return [cat for cat, _ in dominant]


def next_threshold(traits_earned: int) -> int:
    """Get the event count needed for the next trait in a category.

    Progression: 10, 25, 50, 100, 200, 400, 800, ...
    Doubles after the third threshold, so early traits come fast
    but mastery takes real dedication.
    """
    if traits_earned == 0:
        return 10
    if traits_earned == 1:
        return 25
    if traits_earned == 2:
        return 50
    return 50 * (2 ** (traits_earned - 2))


def trait_tier_for_count(traits_earned: int) -> int:
    """Determine the tier (and thus budget) for the Nth trait in a category.

    First trait: tier 1 (budget 2), second: tier 2 (budget 4),
    third+: tier 3 (budget 6). Higher tiers = more powerful effects.
    """
    return min(traits_earned + 1, 3)


def check_behavior_thresholds(
    behavior_scores: dict[str, int],
    traits_per_category: dict[str, int],
) -> list[tuple[str, int]]:
    """Check which behavior categories have crossed their next threshold.

    Args:
        behavior_scores: {category: event_count} from behavior tracking.
        traits_per_category: {category: num_traits_already_earned}.

    Returns list of (category, tier) for each category ready for a new trait.
    Sorted by score descending (strongest pattern first).
    """
    ready = []
    for category, count in behavior_scores.items():
        earned = traits_per_category.get(category, 0)
        threshold = next_threshold(earned)
        if count >= threshold:
            tier = trait_tier_for_count(earned)
            ready.append((category, tier, count))

    # Sort by count descending so the strongest pattern triggers first
    ready.sort(key=lambda x: x[2], reverse=True)
    return [(cat, tier) for cat, tier, _ in ready]


def is_eligible_for_trait(
    character_level: int,
    existing_traits: list[dict],
) -> tuple[bool, int]:
    """Legacy compatibility — always eligible, tier based on trait count.

    Deprecated: Use check_behavior_thresholds() instead.
    """
    return True, min(len(existing_traits) + 1, 3)


def update_behavior_from_events(
    new_events: list[dict],
    current_counts: dict[str, int],
) -> dict[str, int]:
    """Incrementally update behavior counts from new events.

    Rather than re-analyzing all events, this takes new events and
    adds their contributions to existing counts.
    """
    updated = dict(current_counts)
    for event in new_events:
        event_type = event.get("event_type", "")
        for cat_name, cat_def in BEHAVIOR_CATEGORIES.items():
            if event_type in cat_def["event_types"]:
                if _event_matches_filter(event, cat_def.get("filter")):
                    updated[cat_name] = updated.get(cat_name, 0) + 1
    return updated
