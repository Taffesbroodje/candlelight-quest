"""Tests for mechanics/guilds.py — pure guild rank/perk/progress calculations."""
from __future__ import annotations

import pytest

from src.text_rpg.mechanics.guilds import (
    GUILD_RANKS,
    MAX_ACTIVE_ORDERS,
    MAX_GUILDS,
    calculate_work_order_reward,
    can_join_guild,
    check_work_order_complete,
    get_guild_rank,
    get_rank_perks,
    rank_index,
    training_cost_with_guild,
    update_work_order_progress,
)


# -- Sample data --

SAMPLE_RANK_CONFIG = [
    {"id": "initiate", "min_rep": 0, "min_trade_level": 1},
    {"id": "apprentice", "min_rep": 10, "min_trade_level": 3},
    {"id": "journeyman", "min_rep": 25, "min_trade_level": 5},
    {"id": "expert", "min_rep": 45, "min_trade_level": 7},
    {"id": "master", "min_rep": 70, "min_trade_level": 9},
    {"id": "grandmaster", "min_rep": 90, "min_trade_level": 10},
]

SAMPLE_GUILD_DATA = {
    "name": "Order of the Anvil",
    "profession": "smithing",
    "ranks": [
        {
            "id": "initiate",
            "perks": {"shop_discount": 0.0, "xp_multiplier": 1.0, "dc_reduction": 0, "crit_chance": 0.0},
        },
        {
            "id": "apprentice",
            "perks": {"shop_discount": 0.05, "xp_multiplier": 1.1, "dc_reduction": 1, "crit_chance": 0.0},
        },
        {
            "id": "journeyman",
            "perks": {
                "shop_discount": 0.10, "xp_multiplier": 1.2, "dc_reduction": 2, "crit_chance": 0.05,
                "unlocked_recipes": ["forge_mithril_blade"],
            },
        },
        {
            "id": "expert",
            "perks": {"shop_discount": 0.15, "xp_multiplier": 1.3, "dc_reduction": 3, "crit_chance": 0.08},
        },
        {
            "id": "master",
            "perks": {
                "shop_discount": 0.20, "xp_multiplier": 1.5, "dc_reduction": 4, "crit_chance": 0.10,
                "unlocked_recipes": ["forge_adamantine_plate"],
            },
        },
        {
            "id": "grandmaster",
            "perks": {"shop_discount": 0.25, "xp_multiplier": 1.75, "dc_reduction": 5, "crit_chance": 0.15},
        },
    ],
}


class TestGuildRanks:
    """Tests for GUILD_RANKS constant and rank_index."""

    def test_guild_ranks_count(self):
        assert len(GUILD_RANKS) == 6

    def test_guild_ranks_order(self):
        assert GUILD_RANKS == ["initiate", "apprentice", "journeyman", "expert", "master", "grandmaster"]

    def test_rank_index_valid(self):
        assert rank_index("initiate") == 0
        assert rank_index("grandmaster") == 5

    def test_rank_index_unknown_defaults_to_zero(self):
        assert rank_index("unknown_rank") == 0


class TestGetGuildRank:
    """Tests for get_guild_rank — dual-gated rank calculation."""

    def test_lowest_rank_with_no_progress(self):
        assert get_guild_rank(0, 1, SAMPLE_RANK_CONFIG) == "initiate"

    def test_apprentice_requires_both_gates(self):
        # High rep but low trade level → still initiate
        assert get_guild_rank(50, 1, SAMPLE_RANK_CONFIG) == "initiate"
        # High trade level but low rep → still initiate
        assert get_guild_rank(5, 5, SAMPLE_RANK_CONFIG) == "initiate"
        # Both gates met
        assert get_guild_rank(10, 3, SAMPLE_RANK_CONFIG) == "apprentice"

    def test_journeyman_rank(self):
        assert get_guild_rank(25, 5, SAMPLE_RANK_CONFIG) == "journeyman"

    def test_expert_rank(self):
        assert get_guild_rank(45, 7, SAMPLE_RANK_CONFIG) == "expert"

    def test_master_rank(self):
        assert get_guild_rank(70, 9, SAMPLE_RANK_CONFIG) == "master"

    def test_grandmaster_rank(self):
        assert get_guild_rank(90, 10, SAMPLE_RANK_CONFIG) == "grandmaster"

    def test_over_qualified_still_gets_highest(self):
        assert get_guild_rank(100, 10, SAMPLE_RANK_CONFIG) == "grandmaster"

    def test_rep_gate_blocks_despite_high_trade(self):
        """Rep at 20 (below 25 for journeyman) with trade level 10 → apprentice only."""
        assert get_guild_rank(20, 10, SAMPLE_RANK_CONFIG) == "apprentice"

    def test_empty_rank_config_returns_initiate(self):
        assert get_guild_rank(100, 10, []) == "initiate"


class TestCanJoinGuild:
    """Tests for can_join_guild — membership limits."""

    def test_can_join_first_guild(self):
        ok, reason = can_join_guild([], "smiths_guild")
        assert ok is True
        assert reason == ""

    def test_can_join_up_to_max(self):
        memberships = [
            {"guild_id": "guild_1"},
            {"guild_id": "guild_2"},
        ]
        ok, reason = can_join_guild(memberships, "guild_3")
        assert ok is True

    def test_cannot_exceed_max_guilds(self):
        memberships = [
            {"guild_id": f"guild_{i}"} for i in range(MAX_GUILDS)
        ]
        ok, reason = can_join_guild(memberships, "guild_new")
        assert ok is False
        assert str(MAX_GUILDS) in reason

    def test_cannot_rejoin_same_guild(self):
        memberships = [{"guild_id": "smiths_guild"}]
        ok, reason = can_join_guild(memberships, "smiths_guild")
        assert ok is False
        assert "already" in reason.lower()


class TestWorkOrderProgress:
    """Tests for work order progress tracking."""

    def test_check_complete_all_met(self):
        reqs = {"iron_ingot": 5, "coal": 3}
        progress = {"iron_ingot": 5, "coal": 3}
        assert check_work_order_complete(reqs, progress) is True

    def test_check_complete_exceeded(self):
        reqs = {"iron_ingot": 5}
        progress = {"iron_ingot": 10}
        assert check_work_order_complete(reqs, progress) is True

    def test_check_incomplete(self):
        reqs = {"iron_ingot": 5, "coal": 3}
        progress = {"iron_ingot": 5, "coal": 1}
        assert check_work_order_complete(reqs, progress) is False

    def test_check_missing_key(self):
        reqs = {"iron_ingot": 5}
        progress = {}
        assert check_work_order_complete(reqs, progress) is False

    def test_check_empty_requirements_is_complete(self):
        assert check_work_order_complete({}, {}) is True

    def test_update_progress_craft_success(self):
        order = {
            "requirements": {"forge_dagger": 3},
            "progress": {"forge_dagger": 1},
        }
        new_progress = update_work_order_progress(
            order, "CRAFT_SUCCESS", {"recipe": "forge_dagger"},
        )
        assert new_progress["forge_dagger"] == 2

    def test_update_progress_craft_no_match(self):
        order = {
            "requirements": {"forge_dagger": 3},
            "progress": {},
        }
        new_progress = update_work_order_progress(
            order, "CRAFT_SUCCESS", {"recipe": "brew_potion"},
        )
        assert new_progress.get("forge_dagger", 0) == 0

    def test_update_progress_item_gathered(self):
        order = {
            "requirements": {"iron_ingot": 5},
            "progress": {"iron_ingot": 2},
        }
        new_progress = update_work_order_progress(
            order, "ITEM_GATHERED", {"item_id": "iron_ingot", "quantity": 3},
        )
        assert new_progress["iron_ingot"] == 5

    def test_update_progress_with_json_strings(self):
        """Requirements and progress can be JSON strings (from DB)."""
        import json
        order = {
            "requirements": json.dumps({"forge_dagger": 3}),
            "progress": json.dumps({"forge_dagger": 0}),
        }
        new_progress = update_work_order_progress(
            order, "CRAFT_SUCCESS", {"recipe": "forge_dagger"},
        )
        assert new_progress["forge_dagger"] == 1

    def test_update_progress_result_item_match(self):
        """CRAFT_SUCCESS can also match by result_item."""
        order = {
            "requirements": {"dagger": 3},
            "progress": {},
        }
        new_progress = update_work_order_progress(
            order, "CRAFT_SUCCESS", {"recipe": "forge_dagger", "result_item": "dagger"},
        )
        assert new_progress["dagger"] == 1


class TestGetRankPerks:
    """Tests for get_rank_perks — perk accumulation."""

    def test_initiate_perks(self):
        perks = get_rank_perks(SAMPLE_GUILD_DATA, "initiate")
        assert perks["shop_discount"] == 0.0
        assert perks["xp_multiplier"] == 1.0
        assert perks["dc_reduction"] == 0
        assert perks["crit_chance"] == 0.0
        assert perks["unlocked_recipes"] == []

    def test_journeyman_accumulates_recipes(self):
        perks = get_rank_perks(SAMPLE_GUILD_DATA, "journeyman")
        assert perks["shop_discount"] == 0.10
        assert perks["dc_reduction"] == 2
        assert "forge_mithril_blade" in perks["unlocked_recipes"]

    def test_master_accumulates_all_recipes(self):
        perks = get_rank_perks(SAMPLE_GUILD_DATA, "master")
        assert "forge_mithril_blade" in perks["unlocked_recipes"]
        assert "forge_adamantine_plate" in perks["unlocked_recipes"]
        assert perks["xp_multiplier"] == 1.5
        assert perks["dc_reduction"] == 4

    def test_grandmaster_perks(self):
        perks = get_rank_perks(SAMPLE_GUILD_DATA, "grandmaster")
        assert perks["shop_discount"] == 0.25
        assert perks["xp_multiplier"] == 1.75
        assert perks["crit_chance"] == 0.15


class TestTrainingCostWithGuild:
    """Tests for guild training cost discounts."""

    def test_no_discount_without_membership(self):
        assert training_cost_with_guild(100, False, "initiate") == 100

    def test_initiate_discount(self):
        cost = training_cost_with_guild(100, True, "initiate")
        assert cost == 50  # 50% off

    def test_apprentice_discount(self):
        cost = training_cost_with_guild(100, True, "apprentice")
        assert cost == 40  # 60% off

    def test_grandmaster_discount(self):
        cost = training_cost_with_guild(100, True, "grandmaster")
        assert cost == 10  # 90% off

    def test_minimum_cost_is_one(self):
        cost = training_cost_with_guild(1, True, "grandmaster")
        assert cost >= 1


class TestCalculateWorkOrderReward:
    """Tests for reward scaling."""

    def test_reward_within_range(self):
        reward = calculate_work_order_reward(10, 20, "initiate", 1)
        assert 10 <= reward["gold"] <= 40  # With multipliers, shouldn't exceed too much
        assert reward["bonus_xp"] > 0

    def test_higher_rank_gives_more(self):
        rewards_low = [
            calculate_work_order_reward(10, 10, "initiate", 1)["gold"]
            for _ in range(20)
        ]
        rewards_high = [
            calculate_work_order_reward(10, 10, "grandmaster", 1)["gold"]
            for _ in range(20)
        ]
        # Grandmaster should average higher than initiate
        avg_low = sum(rewards_low) / len(rewards_low)
        avg_high = sum(rewards_high) / len(rewards_high)
        assert avg_high > avg_low

    def test_higher_region_tier_gives_more(self):
        rewards_t1 = [
            calculate_work_order_reward(10, 10, "initiate", 1)["gold"]
            for _ in range(20)
        ]
        rewards_t3 = [
            calculate_work_order_reward(10, 10, "initiate", 3)["gold"]
            for _ in range(20)
        ]
        avg_t1 = sum(rewards_t1) / len(rewards_t1)
        avg_t3 = sum(rewards_t3) / len(rewards_t3)
        assert avg_t3 > avg_t1
