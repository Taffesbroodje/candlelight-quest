"""Tests for src/text_rpg/mechanics/survival.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.survival import (
    ITEM_NEED_EFFECTS,
    NeedStatus,
    apply_item_to_needs,
    classify_need,
    get_total_needs_penalty,
    rest_effects,
    tick_needs,
)


class TestClassifyNeed:
    @pytest.mark.parametrize("value, expected_penalty", [
        (0, -5), (24, -5),
        (25, -2), (49, -2),
        (50, -1), (74, -1),
        (75, 0), (100, 0),
    ])
    def test_threshold_values(self, value, expected_penalty):
        status = classify_need("hunger", value)
        assert status.penalty == expected_penalty

    def test_is_critical(self):
        assert classify_need("hunger", 24).is_critical is True
        assert classify_need("hunger", 25).is_critical is False

    @pytest.mark.parametrize("name", ["hunger", "thirst", "warmth", "morale"])
    def test_all_need_types(self, name):
        status = classify_need(name, 50)
        assert isinstance(status, NeedStatus)
        assert status.name == name

    def test_unknown_need(self):
        status = classify_need("unknown", 50)
        assert status.label == "Moderate"


class TestGetTotalNeedsPenalty:
    def test_all_satisfied(self):
        assert get_total_needs_penalty(100, 100, 100, 100) == 0

    def test_single_critical(self):
        assert get_total_needs_penalty(0, 100, 100, 100) == -5

    def test_worst_penalty_wins(self):
        # hunger=50 → -1, thirst=0 → -5 → worst is -5
        assert get_total_needs_penalty(50, 0, 100, 100) == -5

    def test_moderate_and_low(self):
        # hunger=30 → -2, thirst=60 → -1
        assert get_total_needs_penalty(30, 60, 100, 100) == -2


class TestTickNeeds:
    def test_base_temperate_decay(self):
        result = tick_needs(100, 100, 100, 100)
        assert result["hunger"] == 99  # -1
        assert result["thirst"] == 98  # -2
        assert result["warmth"] == 100  # temperate, no decay

    def test_cold_climate_warmth(self):
        result = tick_needs(100, 100, 100, 100, climate="cold")
        assert result["warmth"] == 98  # -2 for cold

    def test_resting_slows_decay(self):
        result = tick_needs(100, 100, 100, 100, is_resting=True)
        assert result["hunger"] == 100  # decay 1-1=0
        assert result["thirst"] == 99   # decay 2-1=1

    def test_long_rest_restores(self):
        result = tick_needs(50, 50, 50, 50, is_long_rest=True)
        assert result["warmth"] == 70   # 50+20
        assert result["morale"] == 65   # 50+15

    def test_morale_recovery_when_met(self):
        result = tick_needs(80, 80, 60, 50)
        assert result["morale"] == 51  # +1 since hunger>=75, thirst>=75, warmth>=50

    def test_morale_decay_when_critical(self):
        result = tick_needs(20, 100, 100, 50)
        assert result["morale"] == 49  # -1 since hunger<25

    def test_never_below_0(self):
        result = tick_needs(0, 0, 0, 0, climate="freezing")
        assert all(v >= 0 for v in result.values())

    def test_never_above_100(self):
        result = tick_needs(100, 100, 100, 100, is_long_rest=True)
        assert all(v <= 100 for v in result.values())


class TestApplyItemToNeeds:
    @pytest.mark.parametrize("item_id", ["rations", "waterskin", "cooked_meal"])
    def test_known_items(self, item_id):
        result = apply_item_to_needs(item_id, 50, 50, 50, 50)
        assert result is not None
        effects = ITEM_NEED_EFFECTS[item_id]
        for need, boost in effects.items():
            assert result[need] == min(50 + boost, 100)

    def test_unknown_item_returns_none(self):
        assert apply_item_to_needs("magic_wand", 50, 50, 50, 50) is None

    def test_capped_at_100(self):
        result = apply_item_to_needs("rations", 90, 90, 90, 90)
        assert result["hunger"] == 100  # 90+40 capped at 100


class TestRestEffects:
    def test_long_rest(self):
        result = rest_effects(100, 100, 50, 50, "long")
        assert result["hunger"] == 85  # -15
        assert result["thirst"] == 90  # -10
        assert result["warmth"] == 70  # +20
        assert result["morale"] == 70  # +20

    def test_short_rest(self):
        result = rest_effects(100, 100, 50, 50, "short")
        assert result["hunger"] == 95  # -5
        assert result["thirst"] == 95  # -5
        assert result["warmth"] == 55  # +5
        assert result["morale"] == 60  # +10
