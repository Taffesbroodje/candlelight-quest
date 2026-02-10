"""Migration 002: Director support — generated flags, entity properties, quest flexibility."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Add Director-related columns to existing tables."""
    # -- entities: add 'generated' flag and 'properties' JSON column --
    _add_column_if_missing(conn, "entities", "generated", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "entities", "properties", "TEXT")

    # -- locations: add 'generated' flag --
    _add_column_if_missing(conn, "locations", "generated", "BOOLEAN NOT NULL DEFAULT 0")

    # -- quests: add 'generated' flag and flexible quest fields --
    _add_column_if_missing(conn, "quests", "generated", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "quests", "npc_motivation", "TEXT")
    _add_column_if_missing(conn, "quests", "completion_flexibility", "TEXT NOT NULL DEFAULT 'low'")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_def: str
) -> None:
    """Add a column only if it doesn't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
