"""Migration 003: Add gold column to characters."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Add gold column to characters table."""
    cursor = conn.execute("PRAGMA table_info(characters)")
    existing = {row[1] for row in cursor.fetchall()}
    if "gold" not in existing:
        conn.execute("ALTER TABLE characters ADD COLUMN gold INTEGER NOT NULL DEFAULT 0")
