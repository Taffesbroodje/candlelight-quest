"""Migration 018: Guild membership and work orders."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS guild_membership (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            rank TEXT NOT NULL DEFAULT 'initiate',
            joined_turn INTEGER NOT NULL DEFAULT 0,
            is_primary BOOLEAN NOT NULL DEFAULT 0,
            UNIQUE(game_id, character_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS active_work_orders (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            order_type TEXT NOT NULL,
            description TEXT,
            requirements TEXT NOT NULL,
            progress TEXT NOT NULL DEFAULT '{}',
            reward_gold INTEGER NOT NULL DEFAULT 0,
            reward_xp INTEGER NOT NULL DEFAULT 0,
            reward_rep INTEGER NOT NULL DEFAULT 0,
            accepted_turn INTEGER NOT NULL DEFAULT 0,
            expires_turn INTEGER,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS work_order_history (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            completed_turn INTEGER NOT NULL,
            reward_gold INTEGER NOT NULL DEFAULT 0,
            reward_xp INTEGER NOT NULL DEFAULT 0,
            reward_rep INTEGER NOT NULL DEFAULT 0
        );
    """)
