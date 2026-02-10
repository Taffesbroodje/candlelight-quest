from __future__ import annotations

import logging
from typing import Any

from text_rpg.rag.vector_store import VectorStore
from text_rpg.rag.embeddings import OllamaEmbeddings

logger = logging.getLogger(__name__)


class RetrievalResult:
    """A single result from a vector-store query."""

    def __init__(self, text: str, metadata: dict[str, Any], distance: float) -> None:
        self.text = text
        self.metadata = metadata
        self.distance = distance

    def __repr__(self) -> str:
        return f"RetrievalResult(distance={self.distance:.3f}, text={self.text[:60]}...)"


class Retriever:
    """Retrieves relevant context from the vector store."""

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings: OllamaEmbeddings,
        top_k: int = 5,
    ) -> None:
        self.store = vector_store
        self.embeddings = embeddings
        self.top_k = top_k
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Lazy-check whether Ollama is reachable."""
        if self._available is None:
            self._available = self.embeddings.is_available()
        return self._available

    # ------------------------------------------------------------------
    # High-level retrieval methods
    # ------------------------------------------------------------------

    def retrieve_relevant_lore(
        self, query: str, top_k: int | None = None
    ) -> list[RetrievalResult]:
        """Find lore relevant to the current scene."""
        if not self.is_available:
            return []
        return self._query_collection("game_lore", query, top_k or self.top_k)

    def retrieve_relevant_events(
        self, query: str, game_id: str, top_k: int | None = None
    ) -> list[RetrievalResult]:
        """Find past events relevant to the current context."""
        if not self.is_available:
            return []
        return self._query_collection(
            "events", query, top_k or self.top_k, where={"game_id": game_id}
        )

    def retrieve_srd_reference(
        self, query: str, top_k: int | None = None
    ) -> list[RetrievalResult]:
        """Find SRD reference material."""
        if not self.is_available:
            return []
        return self._query_collection("srd_reference", query, top_k or self.top_k)

    def retrieve_npc_history(
        self, npc_id: str, game_id: str, top_k: int | None = None
    ) -> list[RetrievalResult]:
        """Retrieve all known facts about an NPC."""
        if not self.is_available:
            return []
        results: list[RetrievalResult] = []
        # NPC facts from the lore collection
        lore_results = self._query_collection(
            "game_lore",
            f"NPC {npc_id}",
            top_k or self.top_k,
            where={"npc_id": npc_id},
        )
        results.extend(lore_results)
        # Events involving this NPC
        event_results = self._query_collection(
            "events",
            f"NPC {npc_id}",
            top_k or self.top_k,
            where={"actor_id": npc_id},
        )
        results.extend(event_results)
        return results

    # ------------------------------------------------------------------
    # Context builder (convenience for LLM prompt assembly)
    # ------------------------------------------------------------------

    def build_context(
        self,
        scene_description: str,
        game_id: str,
        location_id: str | None = None,
    ) -> dict[str, list[str]]:
        """Build a complete context packet for the LLM.

        Returns a dict with keys ``relevant_lore``, ``past_events``, and
        ``srd_reference``, each mapping to a list of text snippets.
        """
        context: dict[str, list[str]] = {
            "relevant_lore": [],
            "past_events": [],
            "srd_reference": [],
        }
        if not self.is_available:
            return context

        # Relevant lore
        lore = self.retrieve_relevant_lore(scene_description, top_k=3)
        context["relevant_lore"] = [r.text for r in lore]

        # Relevant past events
        events = self.retrieve_relevant_events(scene_description, game_id, top_k=5)
        context["past_events"] = [r.text for r in events]

        # SRD reference
        srd = self.retrieve_srd_reference(scene_description, top_k=2)
        context["srd_reference"] = [r.text for r in srd]

        return context

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _query_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Query a specific collection and return typed results."""
        try:
            if self.store.count(collection_name) == 0:
                return []
            embedding = self.embeddings.embed(query)
            results = self.store.query(
                collection_name, [embedding], n_results=top_k, where=where
            )
            output: list[RetrievalResult] = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                output.append(RetrievalResult(doc, meta, dist))
            return output
        except Exception as exc:
            logger.warning("RAG query failed for %s: %s", collection_name, exc)
            return []
