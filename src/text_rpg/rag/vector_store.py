from __future__ import annotations

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import Any


class VectorStore:
    """ChromaDB wrapper managing separate collections for game data."""

    COLLECTIONS = ["game_lore", "events", "srd_reference"]

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        collection_prefix: str = "text_rpg",
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_prefix = collection_prefix
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self._collections: dict[str, chromadb.Collection] = {}

    def get_collection(self, name: str) -> chromadb.Collection:
        """Return (or lazily create) a namespaced ChromaDB collection."""
        full_name = f"{self.collection_prefix}_{name}"
        if full_name not in self._collections:
            self._collections[full_name] = self.client.get_or_create_collection(
                name=full_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[full_name]

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Add documents (with optional pre-computed embeddings) to a collection."""
        collection = self.get_collection(collection_name)
        kwargs: dict[str, Any] = {
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids,
        }
        if embeddings:
            kwargs["embeddings"] = embeddings
        collection.add(**kwargs)

    def query(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Semantic search against a collection using pre-computed query embeddings."""
        collection = self.get_collection(collection_name)
        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def count(self, collection_name: str) -> int:
        """Return the number of documents in a collection."""
        return self.get_collection(collection_name).count()

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection by its short name."""
        full_name = f"{self.collection_prefix}_{collection_name}"
        try:
            self.client.delete_collection(full_name)
            self._collections.pop(full_name, None)
        except ValueError:
            pass

    def reset_all(self) -> None:
        """Drop every known collection managed by this store."""
        for name in self.COLLECTIONS:
            self.delete_collection(name)
