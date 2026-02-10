"""Dice rolling engine — pure math, no I/O."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

# Pattern: NdM, NdMkhK, NdMklK, optional +/-X
_DICE_RE = re.compile(
    r"^(\d+)d(\d+)"
    r"(?:kh(\d+)|kl(\d+))?"
    r"([+-]\d+)?$",
    re.IGNORECASE,
)


@dataclass
class DiceResult:
    expression: str
    individual_rolls: list[int]
    modifier: int = 0
    total: int = 0


def roll(expression: str) -> DiceResult:
    """Roll dice from an expression like '2d6+3', '1d20', '4d6kh3'."""
    expr = expression.replace(" ", "")
    m = _DICE_RE.match(expr)
    if not m:
        raise ValueError(f"Invalid dice expression: {expression}")

    num_dice = int(m.group(1))
    die_size = int(m.group(2))
    keep_highest = int(m.group(3)) if m.group(3) else None
    keep_lowest = int(m.group(4)) if m.group(4) else None
    modifier = int(m.group(5)) if m.group(5) else 0

    rolls = [random.randint(1, die_size) for _ in range(num_dice)]

    if keep_highest is not None:
        kept = sorted(rolls, reverse=True)[:keep_highest]
    elif keep_lowest is not None:
        kept = sorted(rolls)[:keep_lowest]
    else:
        kept = rolls

    total = sum(kept) + modifier
    return DiceResult(
        expression=expression,
        individual_rolls=rolls,
        modifier=modifier,
        total=total,
    )


def roll_d20(modifier: int = 0) -> DiceResult:
    """Convenience: roll 1d20 + modifier."""
    r = roll("1d20")
    r.modifier = modifier
    r.total = r.individual_rolls[0] + modifier
    return r


def roll_with_advantage(expression: str = "1d20") -> tuple[DiceResult, DiceResult, DiceResult]:
    """Roll twice, return (best, roll1, roll2)."""
    r1 = roll(expression)
    r2 = roll(expression)
    best = r1 if r1.total >= r2.total else r2
    return best, r1, r2


def roll_with_disadvantage(expression: str = "1d20") -> tuple[DiceResult, DiceResult, DiceResult]:
    """Roll twice, return (worst, roll1, roll2)."""
    r1 = roll(expression)
    r2 = roll(expression)
    worst = r1 if r1.total <= r2.total else r2
    return worst, r1, r2
