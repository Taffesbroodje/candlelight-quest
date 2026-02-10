"""Token counting and budget management."""
from __future__ import annotations


class TokenBudget:
    def __init__(self, max_context_tokens: int = 2048, chars_per_token: float = 4.0):
        self.max_context_tokens = max_context_tokens
        self.chars_per_token = chars_per_token

    @property
    def max_chars(self) -> int:
        return int(self.max_context_tokens * self.chars_per_token)

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / self.chars_per_token)

    def trim_to_budget(self, text: str, reserved_tokens: int = 0) -> str:
        available = self.max_chars - int(reserved_tokens * self.chars_per_token)
        if len(text) <= available:
            return text
        trimmed = text[:available]
        last_para = trimmed.rfind("\n\n")
        if last_para > available * 0.5:
            return trimmed[:last_para]
        last_sentence = trimmed.rfind(". ")
        if last_sentence > available * 0.5:
            return trimmed[: last_sentence + 1]
        return trimmed

    def fits_budget(self, text: str, reserved_tokens: int = 0) -> bool:
        available = self.max_context_tokens - reserved_tokens
        return self.estimate_tokens(text) <= available
