"""Repository for character traits and behavior tracking."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.storage.database import Database


class TraitRepo:
    """CRUD for character_traits and behavior_events tables."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Character Traits --

    def save_trait(self, trait: dict) -> None:
        """Insert a new trait."""
        data = dict(trait)
        if "effects" in data and not isinstance(data["effects"], str):
            data["effects"] = json.dumps(data["effects"])
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO character_traits ({columns}) VALUES ({placeholders})"
        with self.db.get_connection() as conn:
            conn.execute(sql, list(data.values()))

    def get_traits(self, game_id: str, character_id: str) -> list[dict]:
        """Get all traits for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM character_traits WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return [self._deserialize_trait(r) for r in rows]

    def get_trait_by_tier(self, game_id: str, character_id: str, tier: int) -> dict | None:
        """Get a trait at a specific tier, or None."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM character_traits WHERE game_id = ? AND character_id = ? AND tier = ?",
                (game_id, character_id, tier),
            ).fetchone()
        return self._deserialize_trait(row) if row else None

    @staticmethod
    def _deserialize_trait(row: Any) -> dict:
        result = dict(row)
        effects = result.get("effects")
        if effects and isinstance(effects, str):
            result["effects"] = json.loads(effects)
        return result

    # -- Behavior Events --

    def update_behavior_count(
        self, game_id: str, character_id: str, category: str, count: int, turn: int,
    ) -> None:
        """Upsert a behavior count."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO behavior_events (game_id, character_id, category, count, last_updated_turn)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(game_id, character_id, category)
                DO UPDATE SET count = ?, last_updated_turn = ?""",
                (game_id, character_id, category, count, turn, count, turn),
            )

    def get_behavior_counts(self, game_id: str, character_id: str) -> dict[str, int]:
        """Get all behavior counts as {category: count}."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT category, count FROM behavior_events WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return {row["category"]: row["count"] for row in rows}

    def count_traits_by_category(self, game_id: str, character_id: str) -> dict[str, int]:
        """Count how many traits have been earned per behavior_source category."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT behavior_source, COUNT(*) as cnt "
                "FROM character_traits WHERE game_id = ? AND character_id = ? "
                "GROUP BY behavior_source",
                (game_id, character_id),
            ).fetchall()
        return {row["behavior_source"]: row["cnt"] for row in rows}

    def delete_all(self, game_id: str) -> None:
        """Delete all traits and behavior events for a game (for delete_game cascade)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM character_traits WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM behavior_events WHERE game_id = ?", (game_id,))
