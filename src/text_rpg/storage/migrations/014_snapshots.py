"""Migration 014: Snapshots table for time travel, loop tracking, timeline IDs."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            world_time INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            trigger TEXT NOT NULL,
            location_id TEXT NOT NULL,
            player_state TEXT NOT NULL,
            inventory_state TEXT NOT NULL,
            world_state TEXT NOT NULL,
            quest_state TEXT NOT NULL,
            social_state TEXT NOT NULL,
            metadata TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshot_game
            ON snapshots(game_id, turn_number DESC);
    """)

    # Add loop_count and timeline_id to games (idempotent)
    for col, col_type, default in [
        ("loop_count", "INTEGER", "0"),
        ("timeline_id", "TEXT", "'prime'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} {col_type} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Add timeline_id to events (idempotent)
    try:
        conn.execute("ALTER TABLE events ADD COLUMN timeline_id TEXT DEFAULT 'prime'")
    except sqlite3.OperationalError:
        pass
