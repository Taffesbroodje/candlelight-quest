from __future__ import annotations

import json
from typing import Any

from text_rpg.storage.database import Database


def _deserialize(row: Any) -> dict | None:
    """Convert a sqlite3.Row to a dict with the mechanical_details field parsed."""
    if row is None:
        return None
    result = dict(row)
    raw = result.get("mechanical_details")
    if raw is not None and isinstance(raw, str):
        result["mechanical_details"] = json.loads(raw)
    return result


def _deserialize_many(rows: list) -> list[dict]:
    """Convert a list of sqlite3.Row objects to dicts."""
    return [_deserialize(r) for r in rows]


class EventLedgerRepo:
    """Append-only repository for the event ledger."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event_dict: dict) -> None:
        """Insert a new event. Events are immutable once written."""
        data = dict(event_dict)
        md = data.get("mechanical_details")
        if md is not None and not isinstance(md, str):
            data["mechanical_details"] = json.dumps(md)
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO events ({columns}) VALUES ({placeholders})"
        with self.db.get_connection() as conn:
            conn.execute(sql, list(data.values()))

    def get_recent(self, game_id: str, limit: int = 20) -> list[dict]:
        """Return the most recent events for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE game_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (game_id, limit),
            ).fetchall()
        return _deserialize_many(rows)

    def get_by_type(
        self, game_id: str, event_type: str, limit: int = 50
    ) -> list[dict]:
        """Return events of a given type for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE game_id = ? AND event_type = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (game_id, event_type, limit),
            ).fetchall()
        return _deserialize_many(rows)

    def get_by_actor(
        self, game_id: str, actor_id: str, limit: int = 50
    ) -> list[dict]:
        """Return events involving a given actor."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE game_id = ? AND actor_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (game_id, actor_id, limit),
            ).fetchall()
        return _deserialize_many(rows)

    def get_by_location(
        self, game_id: str, location_id: str, limit: int = 50
    ) -> list[dict]:
        """Return events at a given location."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE game_id = ? AND location_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (game_id, location_id, limit),
            ).fetchall()
        return _deserialize_many(rows)

    def count(self, game_id: str) -> int:
        """Return the total number of events for a game."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM events WHERE game_id = ?",
                (game_id,),
            ).fetchone()
        return row["cnt"] if row else 0
