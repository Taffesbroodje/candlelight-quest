"""Economy mechanics — pure calculations for buy/sell pricing, no I/O."""
from __future__ import annotations


def calculate_buy_price(base_price: int, rep_mult: float = 1.0, supply_mult: float = 1.0) -> int:
    """Calculate the price a player pays to buy an item.

    Args:
        base_price: Item's base value in gold.
        rep_mult: Reputation-based price modifier (from faction reputation effects).
        supply_mult: Supply/demand modifier based on current stock levels.

    Returns:
        Final buy price (minimum 1 gp).
    """
    return max(1, round(base_price * rep_mult * supply_mult))


def calculate_sell_price(base_price: int) -> int:
    """Calculate the price a shop pays the player for an item (50% of base)."""
    return max(1, base_price // 2)


def supply_demand_modifier(stock_qty: int, base_stock: int) -> float:
    """Price modifier based on current stock vs base stock.

    Low stock → higher prices. Overstock → lower prices.
    Returns a multiplier between 0.8 and 1.5.
    """
    if base_stock <= 0:
        return 1.0
    ratio = stock_qty / base_stock
    if ratio <= 0:
        return 1.5  # Out of stock — premium price if restocked
    elif ratio < 0.5:
        return 1.3  # Low stock
    elif ratio < 1.0:
        return 1.1  # Slightly below normal
    elif ratio > 2.0:
        return 0.8  # Overstock discount
    return 1.0
