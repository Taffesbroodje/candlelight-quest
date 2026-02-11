"""Migration 016: Character traits and behavior tracking tables."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_traits (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            tier INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            effects TEXT NOT NULL,
            behavior_source TEXT NOT NULL,
            acquired_turn INTEGER NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS behavior_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            category TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            last_updated_turn INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(id),
            UNIQUE(game_id, character_id, category)
        )
    """)
