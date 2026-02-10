"""Migration 008: World clock, NPC schedules, and story state."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # Add world_time to games table (total minutes elapsed, start at 8:00 AM = 480)
    try:
        cur.execute("ALTER TABLE games ADD COLUMN world_time INTEGER DEFAULT 480")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Add schedule and profession to entities
    try:
        cur.execute("ALTER TABLE entities ADD COLUMN profession TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE entities ADD COLUMN schedule TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE entities ADD COLUMN unavailable_periods TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass

    # Story state tracking (for Phase 2 story seeds)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS story_state (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            seed_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            current_beat TEXT DEFAULT 'hook',
            resolved_variables TEXT DEFAULT '{}',
            activated_beats TEXT DEFAULT '[]',
            beat_turn_numbers TEXT DEFAULT '{}',
            quest_ids TEXT DEFAULT '[]',
            data TEXT DEFAULT '{}',
            created_at TEXT,
            UNIQUE(game_id, seed_id)
        )
    """)

    # World event cooldown tracking
    cur.execute("""
        CREATE TABLE IF NOT EXISTS world_event_cooldowns (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            last_triggered_turn INTEGER DEFAULT 0,
            UNIQUE(game_id, event_id)
        )
    """)
