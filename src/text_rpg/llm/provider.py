"""Abstract LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None,
                 temperature: float = 0.8, max_tokens: int = 1024) -> str: ...

    @abstractmethod
    def generate_structured(self, prompt: str, system_prompt: str | None = None,
                            temperature: float = 0.7, max_tokens: int = 512) -> dict[str, Any]: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...
