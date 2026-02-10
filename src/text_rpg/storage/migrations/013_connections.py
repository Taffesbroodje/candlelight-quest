"""Migration 013: Dedicated location_connections table.

Extracts embedded JSON connections from the locations table into a proper
relational table with indexes for fast lookups in both directions.
"""
from __future__ import annotations

import json
import sqlite3
import uuid


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS location_connections (
            id                 TEXT PRIMARY KEY,
            game_id            TEXT NOT NULL,
            source_location_id TEXT NOT NULL,
            target_location_id TEXT NOT NULL,
            direction          TEXT NOT NULL,
            description        TEXT DEFAULT '',
            is_locked          BOOLEAN DEFAULT 0,
            UNIQUE(game_id, source_location_id, direction)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_conn_source
        ON location_connections(game_id, source_location_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_conn_target
        ON location_connections(game_id, target_location_id)
    """)

    # Migrate existing JSON connections from locations table.
    rows = cur.execute("SELECT id, game_id, connections FROM locations").fetchall()
    for row in rows:
        loc_id = row[0]
        game_id = row[1]
        raw_conns = row[2]

        if not raw_conns:
            continue

        try:
            connections = json.loads(raw_conns) if isinstance(raw_conns, str) else raw_conns
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(connections, list):
            continue

        for c in connections:
            if not isinstance(c, dict):
                continue
            target_id = c.get("target_location_id", "")
            direction = c.get("direction", "")
            if not target_id or not direction:
                continue

            # Skip if this exact connection already exists (idempotent)
            existing = cur.execute(
                "SELECT 1 FROM location_connections "
                "WHERE game_id = ? AND source_location_id = ? AND direction = ?",
                (game_id, loc_id, direction),
            ).fetchone()
            if existing:
                continue

            cur.execute(
                "INSERT INTO location_connections "
                "(id, game_id, source_location_id, target_location_id, direction, description, is_locked) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    game_id,
                    loc_id,
                    target_id,
                    direction,
                    c.get("description", ""),
                    1 if c.get("is_locked") else 0,
                ),
            )
