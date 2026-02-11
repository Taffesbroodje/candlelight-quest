"""Migration 019: Add origin_id column to characters table."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ALTER TABLE characters ADD COLUMN origin_id TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
