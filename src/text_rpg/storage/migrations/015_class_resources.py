"""Migration 015: Class resource columns for new classes."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    columns = [
        ("rage_remaining", "INTEGER", "NULL"),
        ("ki_remaining", "INTEGER", "NULL"),
        ("sorcery_points_remaining", "INTEGER", "NULL"),
        ("lay_on_hands_remaining", "INTEGER", "NULL"),
        ("bardic_inspiration_remaining", "INTEGER", "NULL"),
        ("wild_shape_remaining", "INTEGER", "NULL"),
        ("pact_slots_remaining", "TEXT", "NULL"),
        ("class_resources", "TEXT", "NULL"),
    ]
    for col, col_type, default in columns:
        try:
            conn.execute(
                f"ALTER TABLE characters ADD COLUMN {col} {col_type} DEFAULT {default}"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists
