from __future__ import annotations

import json
import urllib.request
import urllib.error
import logging
from typing import Any

logger = logging.getLogger(__name__)


class OllamaEmbeddings:
    """Generate embeddings using the Ollama local API."""

    DEFAULT_DIM = 768  # nomic-embed-text output dimension

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        return self._call_ollama(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts sequentially."""
        return [self._call_ollama(t) for t in texts]

    def _call_ollama(self, text: str) -> list[float]:
        """Call the Ollama embedding endpoint and return the vector."""
        url = f"{self.base_url}/api/embed"
        payload = json.dumps({"model": self.model, "input": text}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result: dict[str, Any] = json.loads(resp.read())
                return result["embeddings"][0]
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            logger.warning("Ollama embedding failed: %s. Zero-vector fallback.", exc)
            return [0.0] * self.DEFAULT_DIM
        except (KeyError, IndexError) as exc:
            logger.warning("Unexpected Ollama response: %s. Zero-vector fallback.", exc)
            return [0.0] * self.DEFAULT_DIM

    def is_available(self) -> bool:
        """Return True if Ollama is running and the model is available."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data: dict[str, Any] = json.loads(resp.read())
                models = [
                    m.get("name", "").split(":")[0]
                    for m in data.get("models", [])
                ]
                return self.model in models
        except Exception:
            return False
