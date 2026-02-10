"""Repository for companion data."""
from __future__ import annotations

import uuid
from typing import Any

from text_rpg.storage.database import Database


class CompanionRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_active_companions(self, game_id: str) -> list[dict]:
        """Get all active companions for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM companions WHERE game_id = ? AND status = 'active'",
                (game_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_companion_by_entity(self, game_id: str, entity_id: str) -> dict | None:
        """Get a companion record by entity ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companions WHERE game_id = ? AND entity_id = ?",
                (game_id, entity_id),
            ).fetchone()
        return dict(row) if row else None

    def recruit(self, game_id: str, entity_id: str, turn: int = 0, home_location: str | None = None) -> str:
        """Add a new companion. Returns the companion ID."""
        comp_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO companions (id, game_id, entity_id, status, recruited_turn, home_location) "
                "VALUES (?, ?, ?, 'active', ?, ?)",
                (comp_id, game_id, entity_id, turn, home_location),
            )
        return comp_id

    def dismiss(self, game_id: str, entity_id: str) -> None:
        """Dismiss a companion (set status to dismissed)."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE companions SET status = 'dismissed' WHERE game_id = ? AND entity_id = ?",
                (game_id, entity_id),
            )

    def set_status(self, game_id: str, entity_id: str, status: str) -> None:
        """Update companion status."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE companions SET status = ? WHERE game_id = ? AND entity_id = ?",
                (status, game_id, entity_id),
            )

    def get_all_companions(self, game_id: str) -> list[dict]:
        """Get all companions (including dismissed) for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM companions WHERE game_id = ?",
                (game_id,),
            ).fetchall()
        return [dict(r) for r in rows]
