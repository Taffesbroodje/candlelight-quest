"""Migration 009: Shops and economy."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            owner_entity_id TEXT NOT NULL,
            location_id TEXT NOT NULL,
            shop_type TEXT NOT NULL DEFAULT 'general',
            stock TEXT,
            gold_reserve INTEGER DEFAULT 500,
            price_modifier REAL DEFAULT 1.0,
            restock_turn INTEGER DEFAULT 0
        )
    """)
