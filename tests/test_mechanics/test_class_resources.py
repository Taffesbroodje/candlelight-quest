"""Tests for src/text_rpg/mechanics/class_resources.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.class_resources import (
    calculate_rage_damage,
    calculate_smite_damage,
    get_inspiration_die,
    get_inspiration_uses,
    get_ki_points,
    get_lay_on_hands_pool,
    get_pact_slots,
    get_rage_uses,
    get_sorcery_points,
    get_wild_shape_temp_hp,
    get_wild_shape_uses,
    ki_ability_dc,
    points_to_slot,
    rage_resistances,
    slot_to_points,
)


class TestRage:
    @pytest.mark.parametrize("level, expected", [
        (1, 2), (2, 2), (3, 3), (5, 3), (6, 4), (12, 5), (17, 6), (20, 999),
    ])
    def test_rage_uses(self, level, expected):
        assert get_rage_uses(level) == expected

    @pytest.mark.parametrize("level, expected", [
        (1, 2), (8, 2), (9, 3), (15, 3), (16, 4), (20, 4),
    ])
    def test_rage_damage(self, level, expected):
        assert calculate_rage_damage(level) == expected

    def test_rage_resistances(self):
        r = rage_resistances()
        assert "bludgeoning" in r
        assert "piercing" in r
        assert "slashing" in r
        assert len(r) == 3

    def test_rage_uses_clamped_low(self):
        assert get_rage_uses(0) == get_rage_uses(1)

    def test_rage_uses_clamped_high(self):
        assert get_rage_uses(25) == get_rage_uses(20)


class TestKi:
    @pytest.mark.parametrize("level, expected", [
        (1, 1), (2, 2), (5, 5), (10, 10), (20, 20),
    ])
    def test_ki_points(self, level, expected):
        assert get_ki_points(level) == expected

    def test_ki_points_zero(self):
        assert get_ki_points(0) == 0

    def test_ki_points_negative(self):
        assert get_ki_points(-1) == 0

    @pytest.mark.parametrize("wis, prof, expected", [
        (10, 2, 10),   # 8 + 0 + 2
        (16, 2, 13),   # 8 + 3 + 2
        (14, 3, 13),   # 8 + 2 + 3
        (20, 6, 19),   # 8 + 5 + 6
    ])
    def test_ki_ability_dc(self, wis, prof, expected):
        assert ki_ability_dc(wis, prof) == expected


class TestSorceryPoints:
    @pytest.mark.parametrize("level, expected", [
        (1, 0), (2, 2), (5, 5), (10, 10), (20, 20),
    ])
    def test_sorcery_points(self, level, expected):
        assert get_sorcery_points(level) == expected

    @pytest.mark.parametrize("slot_level, expected", [
        (1, 2), (2, 3), (3, 5), (4, 6), (5, 7),
    ])
    def test_slot_to_points(self, slot_level, expected):
        assert slot_to_points(slot_level) == expected

    @pytest.mark.parametrize("points, expected", [
        (2, 1), (3, 2), (5, 3), (6, 4), (7, 5),
    ])
    def test_points_to_slot(self, points, expected):
        assert points_to_slot(points) == expected

    def test_points_to_slot_invalid(self):
        assert points_to_slot(1) is None
        assert points_to_slot(4) is None
        assert points_to_slot(10) is None


class TestLayOnHands:
    @pytest.mark.parametrize("level, expected", [
        (1, 5), (2, 10), (5, 25), (10, 50), (20, 100),
    ])
    def test_pool(self, level, expected):
        assert get_lay_on_hands_pool(level) == expected

    def test_zero_level(self):
        assert get_lay_on_hands_pool(0) == 0


class TestBardicInspiration:
    @pytest.mark.parametrize("cha, expected", [
        (8, 1),   # -1 mod → minimum 1
        (10, 1),  # 0 mod → minimum 1
        (12, 1),  # +1 mod
        (14, 2),  # +2 mod
        (20, 5),  # +5 mod
    ])
    def test_inspiration_uses(self, cha, expected):
        assert get_inspiration_uses(cha) == expected

    @pytest.mark.parametrize("level, expected", [
        (1, "1d6"), (4, "1d6"), (5, "1d8"), (9, "1d8"),
        (10, "1d10"), (14, "1d10"), (15, "1d12"), (20, "1d12"),
    ])
    def test_inspiration_die(self, level, expected):
        assert get_inspiration_die(level) == expected


class TestWildShape:
    def test_uses_always_2(self):
        assert get_wild_shape_uses() == 2

    @pytest.mark.parametrize("level, expected", [
        (1, 4), (2, 8), (5, 20), (10, 40), (20, 80),
    ])
    def test_temp_hp(self, level, expected):
        assert get_wild_shape_temp_hp(level) == expected

    def test_temp_hp_zero(self):
        assert get_wild_shape_temp_hp(0) == 0


class TestDivineSmite:
    def test_level_1_slot(self):
        assert calculate_smite_damage(1) == "2d8"

    def test_level_2_slot(self):
        assert calculate_smite_damage(2) == "3d8"

    def test_level_3_slot(self):
        assert calculate_smite_damage(3) == "4d8"

    def test_level_4_slot_cap(self):
        # 1 + 4 = 5d8 (cap)
        assert calculate_smite_damage(4) == "5d8"

    def test_level_5_slot_still_cap(self):
        # 1 + 5 = 6 but capped at 5
        assert calculate_smite_damage(5) == "5d8"

    def test_vs_undead_extra_die(self):
        assert calculate_smite_damage(1, is_undead_or_fiend=True) == "3d8"

    def test_vs_undead_plus_high_slot(self):
        # 5d8 cap + 1d8 undead = 6d8
        assert calculate_smite_damage(4, is_undead_or_fiend=True) == "6d8"


class TestPactMagic:
    @pytest.mark.parametrize("level, expected_slots, expected_level", [
        (1, 1, 1), (2, 2, 1), (3, 2, 2), (5, 2, 3),
        (7, 2, 4), (9, 2, 5), (11, 3, 5), (17, 4, 5), (20, 4, 5),
    ])
    def test_pact_slots(self, level, expected_slots, expected_level):
        num, lvl = get_pact_slots(level)
        assert num == expected_slots
        assert lvl == expected_level

    def test_clamped_low(self):
        assert get_pact_slots(0) == get_pact_slots(1)

    def test_clamped_high(self):
        assert get_pact_slots(25) == get_pact_slots(20)
