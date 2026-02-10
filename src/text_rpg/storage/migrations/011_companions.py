"""Migration 011: Companions system."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS companions (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            recruited_turn INTEGER DEFAULT 0,
            home_location TEXT
        )
    """)
