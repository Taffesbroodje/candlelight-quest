"""Ollama LLM provider via LiteLLM."""
from __future__ import annotations

import json
import logging
from typing import Any

from text_rpg.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "mistral", base_url: str = "http://localhost:11434",
                 num_ctx: int = 4096):
        self._model = model
        self.base_url = base_url
        self._litellm_model = f"ollama/{model}"
        self._num_ctx = num_ctx

    def generate(self, prompt: str, system_prompt: str | None = None,
                 temperature: float = 0.8, max_tokens: int = 1024) -> str:
        try:
            import litellm
            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = litellm.completion(
                model=self._litellm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_base=self.base_url,
                num_ctx=self._num_ctx,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_response()

    def generate_structured(self, prompt: str, system_prompt: str | None = None,
                            temperature: float = 0.7, max_tokens: int = 512) -> dict[str, Any]:
        json_system = (system_prompt or "") + "\n\nYou MUST respond with valid JSON only. No other text."
        text = self.generate(prompt, json_system, temperature, max_tokens)
        return self._parse_json(text)

    def is_available(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                return self._model in models
        except Exception:
            return False

    @property
    def model_name(self) -> str:
        return self._model

    def _parse_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start) if "```" in text[start + 3:] else len(text)
            text = text[start:end].strip()
        for i, c in enumerate(text):
            if c in "{[":
                text = text[i:]
                break
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            logger.warning(f"LLM returned non-dict JSON ({type(parsed).__name__}), discarding")
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM: {text[:100]}...")
            return {}

    def _fallback_response(self) -> str:
        return "The scene unfolds before you, though the details remain hazy..."
