from __future__ import annotations

import json
from typing import Any

from text_rpg.storage.database import Database

_JSON_FIELDS = frozenset({
    "ability_scores",
    "skill_proficiencies",
    "saving_throw_proficiencies",
    "class_features",
    "conditions",
    "spell_slots_remaining",
    "spell_slots_max",
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


class CharacterRepo:
    """Repository for player character records."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, character_dict: dict) -> None:
        """Insert or update a character record (UPSERT)."""
        data = _serialize(character_dict)
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k} = excluded.{k}" for k in data)
        sql = (
            f"INSERT INTO characters ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        with self.db.get_connection() as conn:
            conn.execute(sql, list(data.values()))

    def get(self, character_id: str) -> dict | None:
        """Fetch a character by id."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
        return _deserialize(row)

    def get_by_game(self, game_id: str) -> dict | None:
        """Fetch the character for a given game."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE game_id = ?", (game_id,)
            ).fetchone()
        return _deserialize(row)

    def update_field(self, character_id: str, field: str, value: Any) -> None:
        """Update a single field on a character."""
        if field in _JSON_FIELDS and value is not None and not isinstance(value, str):
            value = json.dumps(value)
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE characters SET {field} = ? WHERE id = ?",
                (value, character_id),
            )
