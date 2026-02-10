"""Tests for src/text_rpg/mechanics/spellcasting.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.spellcasting import (
    CANTRIP_SCALING_LEVELS,
    calculate_spell_dc,
    can_cast_spell,
    concentration_save_dc,
    find_usable_slot,
    get_arcane_recovery_slots,
    get_spell_slots,
    scale_cantrip_dice,
)


class TestGetSpellSlots:
    def test_wizard_level_1(self):
        slots = get_spell_slots("wizard", 1)
        assert slots == {1: 2}

    def test_wizard_level_3(self):
        slots = get_spell_slots("wizard", 3)
        assert slots == {1: 4, 2: 2}

    def test_wizard_level_5(self):
        slots = get_spell_slots("wizard", 5)
        assert slots == {1: 4, 2: 3, 3: 2}

    def test_unknown_class_empty(self):
        assert get_spell_slots("barbarian", 5) == {}

    def test_level_clamped_high(self):
        # Level 10 clamped to 5
        assert get_spell_slots("wizard", 10) == get_spell_slots("wizard", 5)

    def test_returns_copy(self):
        s1 = get_spell_slots("wizard", 1)
        s2 = get_spell_slots("wizard", 1)
        assert s1 == s2
        s1[1] = 99
        assert s2[1] != 99


class TestCanCastSpell:
    def test_cantrip_always(self):
        ok, reason = can_cast_spell({"level": 0}, 1, {}, "wizard")
        assert ok is True

    def test_has_slots(self):
        ok, _ = can_cast_spell({"level": 1}, 1, {1: 2}, "wizard")
        assert ok is True

    def test_no_slots_remaining(self):
        ok, reason = can_cast_spell({"level": 1}, 1, {1: 0}, "wizard")
        assert ok is False
        assert "no spell slots" in reason.lower()

    def test_level_too_high(self):
        ok, reason = can_cast_spell({"level": 3}, 1, {1: 2}, "wizard")
        assert ok is False
        assert "cannot cast" in reason.lower()

    def test_upcast_uses_higher_slot(self):
        # Level 1 spell, no level 1 slots but has level 2 slots
        ok, _ = can_cast_spell({"level": 1}, 3, {1: 0, 2: 2}, "wizard")
        assert ok is True


class TestFindUsableSlot:
    def test_exact_level(self):
        assert find_usable_slot(1, {1: 2, 2: 3}) == 1

    def test_upcast(self):
        assert find_usable_slot(1, {1: 0, 2: 1}) == 2

    def test_no_slots(self):
        assert find_usable_slot(1, {1: 0, 2: 0}) is None

    def test_empty_slots(self):
        assert find_usable_slot(1, {}) is None


class TestScaleCantripDice:
    @pytest.mark.parametrize("level, expected", [
        (1, "1d10"), (4, "1d10"), (5, "2d10"), (10, "2d10"),
        (11, "3d10"), (16, "3d10"), (17, "4d10"), (20, "4d10"),
    ])
    def test_scaling(self, level, expected):
        assert scale_cantrip_dice("1d10", level) == expected

    def test_multi_die_base(self):
        assert scale_cantrip_dice("2d6", 5) == "3d6"

    def test_no_scaling_at_level_1(self):
        # At level 1, no extra dice, so original is returned
        assert scale_cantrip_dice("1d10", 1) == "1d10"


class TestConcentrationSaveDC:
    @pytest.mark.parametrize("damage, expected", [
        (1, 10), (19, 10), (20, 10), (22, 11), (40, 20), (100, 50),
    ])
    def test_dc_values(self, damage, expected):
        assert concentration_save_dc(damage) == expected


class TestCalculateSpellDC:
    def test_basic_calculation(self):
        # 8 + modifier(16) + 2 = 8 + 3 + 2 = 13
        assert calculate_spell_dc(16, 2) == 13


class TestGetArcaneRecovery:
    @pytest.mark.parametrize("level, expected", [
        (1, 1), (2, 1), (3, 2), (4, 2), (5, 3),
    ])
    def test_recovery_slots(self, level, expected):
        assert get_arcane_recovery_slots(level) == expected
