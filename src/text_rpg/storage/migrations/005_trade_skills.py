"""Migration 005: Add trade skills table and crafting support."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Create trade_skills table for tracking non-combat skill progression."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trade_skills (
            id          TEXT PRIMARY KEY,
            game_id     TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            skill_name  TEXT NOT NULL,
            level       INTEGER NOT NULL DEFAULT 1,
            xp          INTEGER NOT NULL DEFAULT 0,
            is_learned  BOOLEAN NOT NULL DEFAULT 0,
            trainer_id  TEXT,
            UNIQUE(game_id, character_id, skill_name)
        );

        CREATE TABLE IF NOT EXISTS known_recipes (
            id          TEXT PRIMARY KEY,
            game_id     TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            recipe_id   TEXT NOT NULL,
            skill_name  TEXT NOT NULL,
            learned_at  TEXT,
            UNIQUE(game_id, character_id, recipe_id)
        );
    """)
