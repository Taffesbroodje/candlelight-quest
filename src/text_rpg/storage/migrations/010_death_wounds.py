"""Migration 010: Death penalty wounds and safe location tracking."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # Wounds: JSON array of wound dicts e.g. [{"type": "deep_gash", "ability": "strength", "penalty": -2}]
    try:
        cur.execute("ALTER TABLE characters ADD COLUMN wounds TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Last safe location (settlement) for death respawn
    try:
        cur.execute("ALTER TABLE characters ADD COLUMN last_safe_location TEXT")
    except sqlite3.OperationalError:
        pass
