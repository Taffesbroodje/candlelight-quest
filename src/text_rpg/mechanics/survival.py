"""Survival needs mechanics — pure calculations, no I/O.

Each need is an integer 0-100:
  100  = fully satisfied
  75+  = comfortable (no effect)
  50-74 = hungry/thirsty/chilly/low spirits (minor penalty)
  25-49 = very hungry/dehydrated/cold/despondent (moderate penalty)
  0-24 = starving/parched/freezing/broken (severe penalty)
"""
from __future__ import annotations

from dataclasses import dataclass

# How much each need drops per turn (base rate).
# A "turn" in the game is one action — roughly 10 minutes of in-world time.
HUNGER_DECAY_PER_TURN = 1  # ~100 turns to starve (~a full day of adventuring)
THIRST_DECAY_PER_TURN = 2  # Dehydration is faster
WARMTH_DECAY_PER_TURN = 0  # Only decays in cold environments
MORALE_DECAY_PER_TURN = 0  # Only decays from events

# Climate modifiers for warmth decay
CLIMATE_WARMTH_DECAY: dict[str, int] = {
    "freezing": 3,
    "cold": 2,
    "cool": 1,
    "temperate": 0,
    "warm": 0,
    "hot": 0,  # Could add heat mechanics later
    "arid": 0,
}

# Constitution bonus reduces hunger/thirst decay slightly
# (higher CON = you can go a bit longer without food/water)
CON_DECAY_REDUCTION = {
    -2: 0, -1: 0, 0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1,
}

# Effects of items on needs
ITEM_NEED_EFFECTS: dict[str, dict[str, int]] = {
    "rations": {"hunger": 40},
    "waterskin": {"thirst": 50},
    "torch": {"warmth": 10, "morale": 5},
    "bedroll": {"morale": 10},
    "healing_potion": {"morale": 5},
    "cooked_meal": {"hunger": 60, "morale": 15},
    "hearty_stew": {"hunger": 80, "thirst": 20, "warmth": 15, "morale": 25},
    "healing_herb": {"hunger": 5},
}


@dataclass
class NeedStatus:
    """The severity of a single need."""
    name: str
    value: int
    label: str  # "Satisfied", "Hungry", "Starving", etc.
    penalty: int  # Modifier to ability checks (0, -1, -2, -5)

    @property
    def is_critical(self) -> bool:
        return self.value < 25


def classify_need(name: str, value: int) -> NeedStatus:
    """Classify a need value into a severity level."""
    labels = {
        "hunger": ["Starving", "Very Hungry", "Hungry", "Satisfied"],
        "thirst": ["Parched", "Dehydrated", "Thirsty", "Hydrated"],
        "warmth": ["Freezing", "Cold", "Chilly", "Warm"],
        "morale": ["Broken", "Despondent", "Low Spirits", "Good Spirits"],
    }
    level_labels = labels.get(name, ["Critical", "Low", "Moderate", "Good"])

    if value < 25:
        return NeedStatus(name, value, level_labels[0], -5)
    elif value < 50:
        return NeedStatus(name, value, level_labels[1], -2)
    elif value < 75:
        return NeedStatus(name, value, level_labels[2], -1)
    else:
        return NeedStatus(name, value, level_labels[3], 0)


def get_total_needs_penalty(hunger: int, thirst: int, warmth: int, morale: int) -> int:
    """Get total penalty to ability checks from all needs.

    Uses the worst single penalty (not cumulative) — D&D style.
    """
    penalties = [
        classify_need("hunger", hunger).penalty,
        classify_need("thirst", thirst).penalty,
        classify_need("warmth", warmth).penalty,
        classify_need("morale", morale).penalty,
    ]
    return min(penalties)  # Most negative = worst


def tick_needs(
    hunger: int,
    thirst: int,
    warmth: int,
    morale: int,
    climate: str = "temperate",
    con_modifier: int = 0,
    is_resting: bool = False,
    is_long_rest: bool = False,
) -> dict[str, int]:
    """Advance survival needs by one turn tick.

    Returns updated need values.
    """
    # Calculate decay reduction from CON
    reduction = CON_DECAY_REDUCTION.get(min(con_modifier, 5), 0)

    hunger_decay = max(HUNGER_DECAY_PER_TURN - reduction, 0)
    thirst_decay = max(THIRST_DECAY_PER_TURN - reduction, 0)
    warmth_decay = CLIMATE_WARMTH_DECAY.get(climate, 0)

    # Resting slows hunger/thirst decay
    if is_resting:
        hunger_decay = max(hunger_decay - 1, 0)
        thirst_decay = max(thirst_decay - 1, 0)

    # Long rest restores some warmth and morale
    if is_long_rest:
        warmth = min(warmth + 20, 100)
        morale = min(morale + 15, 100)

    new_hunger = max(hunger - hunger_decay, 0)
    new_thirst = max(thirst - thirst_decay, 0)
    new_warmth = max(warmth - warmth_decay, 0)

    # Morale slowly recovers when other needs are met, decays when they're bad
    if hunger >= 75 and thirst >= 75 and warmth >= 50:
        morale = min(morale + 1, 100)
    elif hunger < 25 or thirst < 25 or warmth < 25:
        morale = max(morale - 1, 0)

    return {
        "hunger": new_hunger,
        "thirst": new_thirst,
        "warmth": new_warmth,
        "morale": morale,
    }


def apply_item_to_needs(
    item_id: str,
    hunger: int,
    thirst: int,
    warmth: int,
    morale: int,
) -> dict[str, int] | None:
    """Apply a consumable item's effects on survival needs.

    Returns updated values, or None if the item has no need effects.
    """
    effects = ITEM_NEED_EFFECTS.get(item_id)
    if not effects:
        return None

    return {
        "hunger": min(hunger + effects.get("hunger", 0), 100),
        "thirst": min(thirst + effects.get("thirst", 0), 100),
        "warmth": min(warmth + effects.get("warmth", 0), 100),
        "morale": min(morale + effects.get("morale", 0), 100),
    }


def rest_effects(
    hunger: int,
    thirst: int,
    warmth: int,
    morale: int,
    rest_type: str = "short",
) -> dict[str, int]:
    """Calculate need changes from resting."""
    if rest_type == "long":
        return {
            "hunger": max(hunger - 15, 0),  # Long rest burns calories
            "thirst": max(thirst - 10, 0),  # Need water
            "warmth": min(warmth + 20, 100),  # Camp warms you
            "morale": min(morale + 20, 100),  # Rest is good for spirits
        }
    else:
        return {
            "hunger": max(hunger - 5, 0),
            "thirst": max(thirst - 5, 0),
            "warmth": min(warmth + 5, 100),
            "morale": min(morale + 10, 100),
        }
