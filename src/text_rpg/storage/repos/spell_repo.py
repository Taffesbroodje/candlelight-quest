"""Repository for spell knowledge and preparation."""
from __future__ import annotations

import uuid

from text_rpg.storage.database import Database


class SpellRepo:
    """Repository for known and prepared spells."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def learn_spell(self, game_id: str, character_id: str, spell_id: str, source: str = "class") -> None:
        """Record that a character knows a spell."""
        sid = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO known_spells (id, game_id, character_id, spell_id, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (sid, game_id, character_id, spell_id, source),
            )

    def get_known_spells(self, game_id: str, character_id: str) -> list[str]:
        """Get all known spell IDs for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT spell_id FROM known_spells WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return [r["spell_id"] for r in rows]

    def knows_spell(self, game_id: str, character_id: str, spell_id: str) -> bool:
        """Check if a character knows a specific spell."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM known_spells WHERE game_id = ? AND character_id = ? AND spell_id = ?",
                (game_id, character_id, spell_id),
            ).fetchone()
        return row is not None

    def prepare_spell(self, game_id: str, character_id: str, spell_id: str) -> None:
        """Mark a spell as prepared."""
        pid = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO prepared_spells (id, game_id, character_id, spell_id)
                   VALUES (?, ?, ?, ?)""",
                (pid, game_id, character_id, spell_id),
            )

    def unprepare_spell(self, game_id: str, character_id: str, spell_id: str) -> None:
        """Remove a spell from prepared list."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM prepared_spells WHERE game_id = ? AND character_id = ? AND spell_id = ?",
                (game_id, character_id, spell_id),
            )

    def get_prepared_spells(self, game_id: str, character_id: str) -> list[str]:
        """Get all prepared spell IDs for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT spell_id FROM prepared_spells WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return [r["spell_id"] for r in rows]

    def is_prepared(self, game_id: str, character_id: str, spell_id: str) -> bool:
        """Check if a spell is prepared."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM prepared_spells WHERE game_id = ? AND character_id = ? AND spell_id = ?",
                (game_id, character_id, spell_id),
            ).fetchone()
        return row is not None
