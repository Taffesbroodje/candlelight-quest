"""Guild mechanics — pure rank/perk/progress calculations, no I/O.

Handles guild rank computation, work order progress tracking,
training cost discounts, and reward scaling.
"""
from __future__ import annotations

from typing import Any

GUILD_RANKS = ["initiate", "apprentice", "journeyman", "expert", "master", "grandmaster"]

# Maximum simultaneous guild memberships
MAX_GUILDS = 3

# Maximum active work orders at once
MAX_ACTIVE_ORDERS = 2


def get_guild_rank(reputation: int, trade_level: int, rank_config: list[dict]) -> str:
    """Return the highest rank where both reputation and trade level gates are met.

    Args:
        reputation: Current faction reputation for this guild's faction.
        trade_level: Current trade skill level for this guild's profession.
        rank_config: List of rank dicts with min_rep, min_trade_level, id fields,
                     ordered from lowest to highest.

    Returns:
        The rank id string (e.g. "journeyman").
    """
    current_rank = "initiate"
    for rank in rank_config:
        if reputation >= rank.get("min_rep", 0) and trade_level >= rank.get("min_trade_level", 1):
            current_rank = rank["id"]
        else:
            break
    return current_rank


def rank_index(rank: str) -> int:
    """Return the numeric index of a rank (0-based)."""
    try:
        return GUILD_RANKS.index(rank)
    except ValueError:
        return 0


def can_join_guild(current_memberships: list[dict], guild_id: str) -> tuple[bool, str]:
    """Check if the player can join a guild.

    Returns (can_join, reason).
    """
    if len(current_memberships) >= MAX_GUILDS:
        return False, f"You can only be a member of {MAX_GUILDS} guilds at once."
    for m in current_memberships:
        if m.get("guild_id") == guild_id:
            return False, "You are already a member of this guild."
    return True, ""


def check_work_order_complete(requirements: dict, progress: dict) -> bool:
    """Check if all requirements of a work order are satisfied.

    Requirements format: {"item_id": quantity, ...} or {"craft_id": quantity, ...}
    Progress format: same keys with current counts.
    """
    for key, required in requirements.items():
        current = progress.get(key, 0)
        if current < required:
            return False
    return True


def update_work_order_progress(
    order: dict, event_type: str, details: dict,
) -> dict:
    """Increment work order progress counters based on a game event.

    Returns updated progress dict.

    Handles:
    - CRAFT_SUCCESS: increments recipe/item counts
    - ITEM_GATHERED: increments item counts
    """
    import json

    requirements = order.get("requirements", {})
    if isinstance(requirements, str):
        requirements = json.loads(requirements)

    progress = order.get("progress", {})
    if isinstance(progress, str):
        progress = json.loads(progress)

    progress = dict(progress)  # copy

    if event_type == "CRAFT_SUCCESS":
        recipe_id = details.get("recipe", "")
        result_item = details.get("result_item", "")
        # Check if the crafted recipe or result item matches a requirement
        if recipe_id in requirements:
            progress[recipe_id] = progress.get(recipe_id, 0) + 1
        if result_item in requirements:
            progress[result_item] = progress.get(result_item, 0) + 1

    elif event_type == "ITEM_GATHERED":
        item_id = details.get("item_id", "")
        if item_id in requirements:
            progress[item_id] = progress.get(item_id, 0) + details.get("quantity", 1)

    return progress


def get_rank_perks(guild_data: dict, rank: str) -> dict[str, Any]:
    """Accumulate all perks at or below the given rank.

    Returns dict of perk values: shop_discount, xp_multiplier, dc_reduction,
    crit_chance, unlocked_recipes.
    """
    perks: dict[str, Any] = {
        "shop_discount": 0.0,
        "xp_multiplier": 1.0,
        "dc_reduction": 0,
        "crit_chance": 0.0,
        "unlocked_recipes": [],
    }

    target_idx = rank_index(rank)
    ranks = guild_data.get("ranks", [])

    for r in ranks:
        r_idx = rank_index(r["id"])
        if r_idx > target_idx:
            break
        rank_perks = r.get("perks", {})
        perks["shop_discount"] = rank_perks.get("shop_discount", perks["shop_discount"])
        perks["xp_multiplier"] = rank_perks.get("xp_multiplier", perks["xp_multiplier"])
        perks["dc_reduction"] = rank_perks.get("dc_reduction", perks["dc_reduction"])
        perks["crit_chance"] = rank_perks.get("crit_chance", perks["crit_chance"])
        for recipe_id in rank_perks.get("unlocked_recipes", []):
            if recipe_id not in perks["unlocked_recipes"]:
                perks["unlocked_recipes"].append(recipe_id)

    return perks


def training_cost_with_guild(base_cost: int, is_member: bool, rank: str) -> int:
    """Calculate training cost with guild membership discount.

    Discount: initiate=50%, apprentice=40%, journeyman=30%, expert=20%,
    master=15%, grandmaster=10%.
    """
    if not is_member:
        return base_cost

    discounts = {
        "initiate": 0.50,
        "apprentice": 0.60,
        "journeyman": 0.70,
        "expert": 0.80,
        "master": 0.85,
        "grandmaster": 0.90,
    }
    multiplier = 1.0 - discounts.get(rank, 0.50)
    # Discount means paying less: cost * (1 - discount_rate)
    # e.g. initiate discount is 50%, so pay 50% of base
    return max(1, round(base_cost * (1.0 - discounts.get(rank, 0.0))))


def calculate_work_order_reward(
    base_gold_min: int, base_gold_max: int,
    rank: str, region_tier: int = 1,
) -> dict[str, int]:
    """Scale work order rewards based on rank and region tier.

    Returns {"gold": int, "bonus_xp": int}.
    """
    import random

    base_gold = random.randint(base_gold_min, base_gold_max)

    # Rank multiplier: higher ranks get better rewards
    rank_mult = 1.0 + rank_index(rank) * 0.15

    # Region tier multiplier
    tier_mult = 1.0 + (region_tier - 1) * 0.1

    gold = round(base_gold * rank_mult * tier_mult)
    bonus_xp = round(gold * 0.5)  # XP scales with gold

    return {"gold": gold, "bonus_xp": bonus_xp}
