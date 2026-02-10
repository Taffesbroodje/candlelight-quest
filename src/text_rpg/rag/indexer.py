from __future__ import annotations

import uuid
import logging
from typing import Any

from text_rpg.rag.vector_store import VectorStore
from text_rpg.rag.embeddings import OllamaEmbeddings

logger = logging.getLogger(__name__)


class Indexer:
    """Indexes game events, lore, and content into the vector store."""

    def __init__(self, vector_store: VectorStore, embeddings: OllamaEmbeddings) -> None:
        self.store = vector_store
        self.embeddings = embeddings
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Lazy-check whether Ollama is reachable."""
        if self._available is None:
            self._available = self.embeddings.is_available()
        return self._available

    # ------------------------------------------------------------------
    # Event indexing
    # ------------------------------------------------------------------

    def index_event(
        self,
        game_id: str,
        event_type: str,
        description: str,
        location_id: str | None = None,
        actor_id: str | None = None,
        turn_number: int = 0,
    ) -> None:
        """Index a game event for later retrieval."""
        if not self.is_available:
            return
        doc_id = str(uuid.uuid4())
        embedding = self.embeddings.embed(description)
        metadata: dict[str, Any] = {
            "game_id": game_id,
            "event_type": event_type,
            "turn_number": turn_number,
            "doc_type": "event",
        }
        if location_id:
            metadata["location_id"] = location_id
        if actor_id:
            metadata["actor_id"] = actor_id
        self.store.add_documents(
            "events", [description], [metadata], [doc_id], [embedding]
        )

    # ------------------------------------------------------------------
    # Lore indexing
    # ------------------------------------------------------------------

    def index_lore(
        self,
        content: str,
        category: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Index world lore or generated content."""
        if not self.is_available:
            return
        doc_id = str(uuid.uuid4())
        embedding = self.embeddings.embed(content)
        metadata: dict[str, Any] = {"category": category, "doc_type": "lore"}
        if tags:
            metadata.update(tags)
        self.store.add_documents(
            "game_lore", [content], [metadata], [doc_id], [embedding]
        )

    # ------------------------------------------------------------------
    # NPC fact indexing
    # ------------------------------------------------------------------

    def index_npc_fact(
        self,
        game_id: str,
        npc_id: str,
        npc_name: str,
        fact: str,
    ) -> None:
        """Index a fact about an NPC."""
        if not self.is_available:
            return
        doc_id = str(uuid.uuid4())
        text = f"{npc_name}: {fact}"
        embedding = self.embeddings.embed(text)
        metadata: dict[str, Any] = {
            "game_id": game_id,
            "npc_id": npc_id,
            "npc_name": npc_name,
            "doc_type": "npc_fact",
        }
        self.store.add_documents(
            "game_lore", [text], [metadata], [doc_id], [embedding]
        )

    # ------------------------------------------------------------------
    # Bulk / seed data
    # ------------------------------------------------------------------

    def index_seed_data(self, documents: list[dict[str, Any]]) -> None:
        """Bulk index SRD seed data.

        Each document dict must contain at least *content*.  Optional keys:
        *category* (defaults to ``"general"``) and *id* (auto-generated when
        absent).
        """
        if not self.is_available:
            logger.info("Ollama not available, skipping seed data indexing.")
            return
        texts = [d["content"] for d in documents]
        ids = [d.get("id", str(uuid.uuid4())) for d in documents]
        metadatas: list[dict[str, Any]] = [
            {"category": d.get("category", "general"), "doc_type": "srd"}
            for d in documents
        ]
        embeddings = self.embeddings.embed_batch(texts)
        self.store.add_documents("srd_reference", texts, metadatas, ids, embeddings)
        logger.info("Indexed %d seed documents.", len(documents))
