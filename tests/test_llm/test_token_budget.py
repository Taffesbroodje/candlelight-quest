"""Tests for src/text_rpg/llm/token_budget.py."""
from __future__ import annotations

import pytest

from text_rpg.llm.token_budget import TokenBudget


class TestTokenBudget:
    def test_max_chars(self):
        budget = TokenBudget(max_context_tokens=100, chars_per_token=4.0)
        assert budget.max_chars == 400

    def test_estimate_tokens(self):
        budget = TokenBudget(chars_per_token=4.0)
        assert budget.estimate_tokens("12345678") == 2

    def test_fits_budget_true(self):
        budget = TokenBudget(max_context_tokens=100, chars_per_token=1.0)
        assert budget.fits_budget("short text") is True

    def test_fits_budget_false(self):
        budget = TokenBudget(max_context_tokens=5, chars_per_token=1.0)
        assert budget.fits_budget("this is a longer text") is False

    def test_trim_short_text_unchanged(self):
        budget = TokenBudget(max_context_tokens=100, chars_per_token=1.0)
        text = "Short text."
        assert budget.trim_to_budget(text) == text

    def test_trim_long_text_truncated(self):
        budget = TokenBudget(max_context_tokens=20, chars_per_token=1.0)
        text = "First paragraph.\n\nSecond paragraph that is much longer than the budget allows."
        result = budget.trim_to_budget(text)
        assert len(result) <= 20

    def test_trim_preserves_paragraph_boundary(self):
        budget = TokenBudget(max_context_tokens=40, chars_per_token=1.0)
        text = "First paragraph here.\n\nSecond paragraph that pushes over limit."
        result = budget.trim_to_budget(text)
        # Should cut at paragraph boundary if possible
        assert len(result) <= 40

    def test_trim_with_reserved_tokens(self):
        budget = TokenBudget(max_context_tokens=50, chars_per_token=1.0)
        text = "A" * 45
        # With 10 reserved tokens (10 chars at 1.0 ratio), available = 40
        result = budget.trim_to_budget(text, reserved_tokens=10)
        assert len(result) <= 40

    def test_fits_budget_with_reserved(self):
        budget = TokenBudget(max_context_tokens=100, chars_per_token=4.0)
        text = "A" * 360  # 90 tokens
        assert budget.fits_budget(text) is True
        assert budget.fits_budget(text, reserved_tokens=20) is False
