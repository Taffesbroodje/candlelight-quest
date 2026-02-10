"""Tests for src/text_rpg/mechanics/economy.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.economy import (
    calculate_buy_price,
    calculate_sell_price,
    supply_demand_modifier,
)


class TestCalculateBuyPrice:
    @pytest.mark.parametrize("base, rep, supply, expected", [
        (100, 1.0, 1.0, 100),
        (100, 1.5, 1.0, 150),
        (100, 0.5, 1.0, 50),
        (100, 1.0, 1.3, 130),
        (50, 0.9, 1.1, 50),  # round(50 * 0.9 * 1.1) = round(49.5) = 50
    ])
    def test_normal_cases(self, base, rep, supply, expected):
        assert calculate_buy_price(base, rep, supply) == expected

    def test_zero_base_returns_1(self):
        assert calculate_buy_price(0, 1.0, 1.0) == 1

    def test_negative_base_returns_1(self):
        assert calculate_buy_price(-10, 1.0, 1.0) == 1

    def test_rounding(self):
        # 15 * 1.0 * 1.1 = 16.5 -> rounds to 16
        assert calculate_buy_price(15, 1.0, 1.1) == round(15 * 1.1)


class TestCalculateSellPrice:
    @pytest.mark.parametrize("base, expected", [
        (100, 50), (10, 5), (1, 1), (3, 1), (200, 100),
    ])
    def test_half_price(self, base, expected):
        assert calculate_sell_price(base) == expected

    def test_minimum_1(self):
        assert calculate_sell_price(0) == 1


class TestSupplyDemandModifier:
    @pytest.mark.parametrize("stock, base, expected", [
        (0, 10, 1.5),     # out of stock
        (3, 10, 1.3),     # low stock (<0.5)
        (7, 10, 1.1),     # slightly below normal
        (10, 10, 1.0),    # normal
        (15, 10, 1.0),    # slightly above (ratio=1.5, <=2.0)
        (25, 10, 0.8),    # overstock (>2.0)
    ])
    def test_modifier_ranges(self, stock, base, expected):
        assert supply_demand_modifier(stock, base) == expected

    def test_zero_base_returns_1(self):
        assert supply_demand_modifier(5, 0) == 1.0

    def test_negative_base_returns_1(self):
        assert supply_demand_modifier(5, -1) == 1.0
