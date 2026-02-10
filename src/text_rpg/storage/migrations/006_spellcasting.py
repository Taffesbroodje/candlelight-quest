"""Migration 006: Add spellcasting tables and character columns."""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Add spellcasting support: character columns + known/prepared spell tables."""
    # Add spellcasting columns to characters (IF NOT EXISTS via try/except)
    for col, col_type in [
        ("spellcasting_ability", "TEXT"),
        ("spell_slots_remaining", "TEXT"),
        ("spell_slots_max", "TEXT"),
        ("concentration_spell", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE characters ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS known_spells (
            id           TEXT PRIMARY KEY,
            game_id      TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            spell_id     TEXT NOT NULL,
            source       TEXT DEFAULT 'class',
            UNIQUE(game_id, character_id, spell_id)
        );

        CREATE TABLE IF NOT EXISTS prepared_spells (
            id           TEXT PRIMARY KEY,
            game_id      TEXT NOT NULL REFERENCES games(id),
            character_id TEXT NOT NULL,
            spell_id     TEXT NOT NULL,
            UNIQUE(game_id, character_id, spell_id)
        );
    """)
