"""Repository for Director intents — planned future actions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from text_rpg.storage.database import Database


class IntentRepo:
    """Manages the intents table for Director-planned future content."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, intent_dict: dict) -> None:
        """Insert or update an intent record."""
        data = dict(intent_dict)
        if "data" in data and data["data"] is not None and not isinstance(data["data"], str):
            data["data"] = json.dumps(data["data"])
        now = datetime.now(timezone.utc).isoformat()
        data.setdefault("created_at", now)
        data["updated_at"] = now

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k} = excluded.{k}" for k in data)
        sql = (
            f"INSERT INTO intents ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        with self.db.get_connection() as conn:
            conn.execute(sql, list(data.values()))

    def get_active(self, game_id: str) -> list[dict]:
        """Return all active intents for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM intents WHERE game_id = ? AND is_active = 1",
                (game_id,),
            ).fetchall()
        return [self._deserialize(r) for r in rows]

    def get_by_type(self, game_id: str, intent_type: str) -> list[dict]:
        """Return active intents of a specific type."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM intents WHERE game_id = ? AND intent_type = ? AND is_active = 1",
                (game_id, intent_type),
            ).fetchall()
        return [self._deserialize(r) for r in rows]

    def deactivate(self, intent_id: str) -> None:
        """Mark an intent as no longer active."""
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE intents SET is_active = 0, updated_at = ? WHERE id = ?",
                (now, intent_id),
            )

    @staticmethod
    def _deserialize(row: Any) -> dict:
        if row is None:
            return {}
        result = dict(row)
        raw = result.get("data")
        if raw is not None and isinstance(raw, str):
            result["data"] = json.loads(raw)
        return result
