from __future__ import annotations

import json
from typing import Any

from text_rpg.storage.database import Database

_JSON_FIELDS = frozenset({
    "ability_scores",
    "attacks",
    "behaviors",
    "dialogue_tags",
    "loot_table",
    "properties",
    "schedule",
    "unavailable_periods",
})


def _serialize(data: dict) -> dict:
    """Return a copy with JSON fields serialized to strings."""
    out = dict(data)
    for field in _JSON_FIELDS:
        if field in out and out[field] is not None and not isinstance(out[field], str):
            out[field] = json.dumps(out[field])
    return out


def _deserialize(row: Any) -> dict | None:
    """Convert a sqlite3.Row to a dict with JSON fields parsed."""
    if row is None:
        return None
    result = dict(row)
    for field in _JSON_FIELDS:
        raw = result.get(field)
        if raw is not None and isinstance(raw, str):
            result[field] = json.loads(raw)
    return result


def _deserialize_many(rows: list) -> list[dict]:
    """Convert a list of sqlite3.Row objects to dicts."""
    return [_deserialize(r) for r in rows]


class EntityRepo:
    """Repository for NPC and creature entity records."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, entity_dict: dict) -> None:
        """Insert or update an entity record (UPSERT)."""
        data = _serialize(entity_dict)
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k} = excluded.{k}" for k in data)
        sql = (
            f"INSERT INTO entities ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        with self.db.get_connection() as conn:
            conn.execute(sql, list(data.values()))

    def get(self, entity_id: str) -> dict | None:
        """Fetch an entity by id."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,)
            ).fetchone()
        return _deserialize(row)

    def get_by_location(self, game_id: str, location_id: str) -> list[dict]:
        """Return all entities at a given location in a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM entities WHERE game_id = ? AND location_id = ?",
                (game_id, location_id),
            ).fetchall()
        return _deserialize_many(rows)

    def get_by_game(self, game_id: str) -> list[dict]:
        """Return all entities in a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM entities WHERE game_id = ?", (game_id,)
            ).fetchall()
        return _deserialize_many(rows)

    def update_field(self, entity_id: str, field: str, value: Any) -> None:
        """Update a single field on an entity."""
        if field in _JSON_FIELDS and value is not None and not isinstance(value, str):
            value = json.dumps(value)
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE entities SET {field} = ? WHERE id = ?",
                (value, entity_id),
            )

    def delete(self, entity_id: str) -> None:
        """Delete an entity by id."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
