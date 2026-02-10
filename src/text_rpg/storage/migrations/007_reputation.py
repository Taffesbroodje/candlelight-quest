"""Migration 007: Reputation, faction, and bounty tables."""
from __future__ import annotations


def upgrade(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS faction_reputation (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            faction_id TEXT NOT NULL,
            reputation INTEGER DEFAULT 0,
            UNIQUE(game_id, faction_id)
        );

        CREATE TABLE IF NOT EXISTS npc_reputation (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            reputation INTEGER DEFAULT 0,
            UNIQUE(game_id, entity_id)
        );

        CREATE TABLE IF NOT EXISTS bounties (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            region TEXT NOT NULL,
            amount INTEGER DEFAULT 0,
            crimes TEXT DEFAULT '[]',
            UNIQUE(game_id, region)
        );
    """)

    # Add faction_id column to entities (ignore if already exists)
    try:
        conn.execute("ALTER TABLE entities ADD COLUMN faction_id TEXT")
    except Exception:
        pass  # Column already exists
