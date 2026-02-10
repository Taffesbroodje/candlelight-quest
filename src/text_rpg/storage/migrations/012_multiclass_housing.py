"""Migration 012: Multiclassing and player housing."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # class_levels tracks multiclass: {"fighter": 3, "wizard": 2}
    try:
        cur.execute("ALTER TABLE characters ADD COLUMN class_levels TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass  # column already exists

    cur.execute("""
        CREATE TABLE IF NOT EXISTS housing (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            character_id TEXT NOT NULL,
            location_id TEXT NOT NULL,
            name TEXT DEFAULT 'Home',
            storage_items TEXT DEFAULT '[]',
            upgrades TEXT DEFAULT '[]',
            purchased_turn INTEGER DEFAULT 0
        )
    """)
