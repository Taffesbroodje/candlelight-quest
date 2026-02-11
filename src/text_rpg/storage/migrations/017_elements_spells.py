"""Migration 017: Spell creation tables — discovered combinations and custom spells."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS discovered_combinations (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            combination_id TEXT NOT NULL,
            discovered_turn INTEGER NOT NULL,
            UNIQUE(game_id, character_id, combination_id)
        );

        CREATE TABLE IF NOT EXISTS custom_spells (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER NOT NULL,
            school TEXT NOT NULL DEFAULT 'evocation',
            description TEXT NOT NULL,
            mechanics TEXT NOT NULL,
            elements TEXT NOT NULL,
            plausibility REAL,
            creation_dc INTEGER,
            created_turn INTEGER NOT NULL,
            location_id TEXT
        );
    """)
