"""Migration 004: Add survival needs columns to characters."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Add survival need columns to characters table.

    Each need is 0-100 (100 = fully satisfied, 0 = critical).
    """
    _add_column_if_missing(conn, "characters", "hunger", "INTEGER NOT NULL DEFAULT 100")
    _add_column_if_missing(conn, "characters", "thirst", "INTEGER NOT NULL DEFAULT 100")
    _add_column_if_missing(conn, "characters", "warmth", "INTEGER NOT NULL DEFAULT 80")
    _add_column_if_missing(conn, "characters", "morale", "INTEGER NOT NULL DEFAULT 75")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_def: str
) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
