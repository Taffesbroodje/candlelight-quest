"""Tests for src/text_rpg/mechanics/combat_math.py."""
from __future__ import annotations

import random

import pytest

from text_rpg.mechanics.combat_math import (
    attack_roll,
    calculate_ac,
    calculate_ac_unarmored,
    calculate_flee_dc,
    damage_roll,
    determine_turn_order,
    npc_choose_action,
)


class TestAttackRoll:
    def test_nat20_always_hits_and_crits(self):
        random.seed(42)
        # Run many times to find a nat 20
        for _ in range(1000):
            hit, crit, result = attack_roll(0, 30)
            if result.individual_rolls[0] == 20:
                assert hit is True
                assert crit is True
                break

    def test_nat1_always_misses(self):
        random.seed(42)
        for _ in range(1000):
            hit, crit, result = attack_roll(100, 1)
            if result.individual_rolls[0] == 1:
                assert hit is False
                assert crit is False
                break

    def test_normal_hit(self, seeded_rng):
        # With +20 bonus, should hit AC 10 most of the time
        hits = sum(attack_roll(20, 10)[0] for _ in range(50))
        assert hits > 40

    def test_normal_miss(self, seeded_rng):
        # With -5 bonus vs AC 25, should miss most of the time
        misses = sum(not attack_roll(-5, 25)[0] for _ in range(50))
        assert misses > 30

    def test_advantage(self, seeded_rng):
        # Advantage should hit more often than normal
        normal_hits = sum(attack_roll(0, 15)[0] for _ in range(200))
        random.seed(42)  # reset seed
        adv_hits = sum(attack_roll(0, 15, advantage=True)[0] for _ in range(200))
        assert adv_hits >= normal_hits

    def test_disadvantage(self, seeded_rng):
        # Disadvantage should hit less often
        normal_hits = sum(attack_roll(0, 11)[0] for _ in range(200))
        random.seed(42)
        dis_hits = sum(attack_roll(0, 11, disadvantage=True)[0] for _ in range(200))
        assert dis_hits <= normal_hits


class TestDamageRoll:
    def test_basic(self, seeded_rng):
        result = damage_roll("1d8", 3)
        assert result.modifier == 3
        assert result.total >= 4  # min 1+3
        assert result.total <= 11  # max 8+3

    def test_critical_doubles_dice(self, seeded_rng):
        result = damage_roll("1d8", 0, is_critical=True)
        assert len(result.individual_rolls) == 2  # 2d8
        assert result.total >= 2

    def test_minimum_zero(self, seeded_rng):
        result = damage_roll("1d4", -10)
        assert result.total >= 0

    def test_multi_die_critical(self, seeded_rng):
        result = damage_roll("2d6", 0, is_critical=True)
        assert len(result.individual_rolls) == 4  # 4d6


class TestCalculateAC:
    @pytest.mark.parametrize("base, dex, armor_type, shield, expected", [
        (11, 3, "light", False, 14),
        (14, 3, "medium", False, 16),  # medium caps dex at 2
        (18, 3, "heavy", False, 18),   # heavy ignores dex
        (11, 3, "light", True, 16),    # +2 shield
        (10, 5, "light", False, 15),
        (14, 1, "medium", True, 17),   # 14+1+2
    ])
    def test_armor_types(self, base, dex, armor_type, shield, expected):
        assert calculate_ac(base, dex, armor_type, shield) == expected

    def test_other_bonuses(self):
        assert calculate_ac(11, 2, "light", False, 1) == 14  # 11+2+1


class TestCalculateACUnarmored:
    @pytest.mark.parametrize("dex, expected", [
        (0, 10), (2, 12), (-1, 9), (5, 15),
    ])
    def test_unarmored(self, dex, expected):
        assert calculate_ac_unarmored(dex) == expected

    def test_with_bonuses(self):
        assert calculate_ac_unarmored(2, 1) == 13


class TestDetermineTurnOrder:
    def test_highest_first(self, seeded_rng):
        order = determine_turn_order([("a", 10), ("b", 20), ("c", 15)])
        assert order[0] == "b"
        assert order[2] == "a"

    def test_single(self, seeded_rng):
        assert determine_turn_order([("a", 5)]) == ["a"]

    def test_empty(self, seeded_rng):
        assert determine_turn_order([]) == []


class TestCalculateFleeDC:
    @pytest.mark.parametrize("enemies, expected", [
        (0, 12), (1, 12), (2, 14), (3, 16),
    ])
    def test_dc_values(self, enemies, expected):
        assert calculate_flee_dc(enemies) == expected


class TestNpcChooseAction:
    def test_flee_at_low_hp(self):
        npc = {"entity_id": "goblin", "hp": {"current": 1, "max": 10}}
        targets = [{"entity_id": "player", "hp": {"current": 20, "max": 20}}]
        action = npc_choose_action(npc, targets)
        assert action["action"] == "flee"

    def test_attack_weakest_target(self):
        npc = {"entity_id": "goblin", "hp": {"current": 10, "max": 10}}
        targets = [
            {"entity_id": "tank", "hp": {"current": 30, "max": 30}},
            {"entity_id": "wizard", "hp": {"current": 5, "max": 10}},
        ]
        action = npc_choose_action(npc, targets)
        assert action["action"] == "attack"
        assert action["target_id"] == "wizard"

    def test_dodge_when_no_alive_targets(self):
        npc = {"entity_id": "goblin", "hp": {"current": 10, "max": 10}}
        targets = [{"entity_id": "player", "hp": {"current": 0, "max": 20}}]
        action = npc_choose_action(npc, targets)
        assert action["action"] == "dodge"

    def test_attack_only_alive(self):
        npc = {"entity_id": "goblin", "hp": {"current": 10, "max": 10}}
        targets = [
            {"entity_id": "dead", "hp": {"current": 0, "max": 20}},
            {"entity_id": "alive", "hp": {"current": 15, "max": 20}},
        ]
        action = npc_choose_action(npc, targets)
        assert action["target_id"] == "alive"
