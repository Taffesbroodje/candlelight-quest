"""Repository for time-travel snapshots."""
from __future__ import annotations

import json

from text_rpg.storage.database import Database


class SnapshotRepo:
    """CRUD for game state snapshots."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_snapshot(self, snapshot: dict) -> None:
        """Insert a new snapshot."""
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO snapshots "
                "(id, game_id, turn_number, world_time, timestamp, trigger, "
                "location_id, player_state, inventory_state, world_state, "
                "quest_state, social_state, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot["id"],
                    snapshot["game_id"],
                    snapshot["turn_number"],
                    snapshot["world_time"],
                    snapshot["timestamp"],
                    snapshot["trigger"],
                    snapshot["location_id"],
                    snapshot["player_state"],
                    snapshot["inventory_state"],
                    snapshot["world_state"],
                    snapshot["quest_state"],
                    snapshot["social_state"],
                    snapshot.get("metadata"),
                ),
            )

    def get_latest(self, game_id: str) -> dict | None:
        """Get the most recent snapshot for a game."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE game_id = ? ORDER BY turn_number DESC LIMIT 1",
                (game_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_turn(self, game_id: str, turn_number: int) -> dict | None:
        """Get the snapshot closest to (but not after) a specific turn."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE game_id = ? AND turn_number <= ? "
                "ORDER BY turn_number DESC LIMIT 1",
                (game_id, turn_number),
            ).fetchone()
        return dict(row) if row else None

    def list_snapshots(self, game_id: str, limit: int = 20) -> list[dict]:
        """List recent snapshots for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, turn_number, world_time, timestamp, trigger, location_id "
                "FROM snapshots WHERE game_id = ? ORDER BY turn_number DESC LIMIT ?",
                (game_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_old(self, game_id: str, keep_count: int = 10) -> None:
        """Delete oldest snapshots, keeping the most recent `keep_count`."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM snapshots WHERE game_id = ? AND id NOT IN "
                "(SELECT id FROM snapshots WHERE game_id = ? ORDER BY turn_number DESC LIMIT ?)",
                (game_id, game_id, keep_count),
            )
