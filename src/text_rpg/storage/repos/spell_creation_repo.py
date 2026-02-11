"""Repository for spell creation: discovered combinations and custom spells."""
from __future__ import annotations

import json
import uuid
from typing import Any

from text_rpg.storage.database import Database


class SpellCreationRepo:
    """CRUD for discovered_combinations and custom_spells tables."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Discovered Combinations --

    def discover_combination(
        self, game_id: str, char_id: str, combination_id: str, turn: int,
    ) -> None:
        """Record a newly discovered spell combination."""
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO discovered_combinations "
                "(id, game_id, character_id, combination_id, discovered_turn) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), game_id, char_id, combination_id, turn),
            )

    def get_discovered_combinations(self, game_id: str, char_id: str) -> list[str]:
        """Return list of combination_ids discovered by this character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT combination_id FROM discovered_combinations "
                "WHERE game_id = ? AND character_id = ?",
                (game_id, char_id),
            ).fetchall()
        return [r[0] for r in rows]

    def has_discovered(self, game_id: str, char_id: str, combination_id: str) -> bool:
        """Check if a specific combination has been discovered."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM discovered_combinations "
                "WHERE game_id = ? AND character_id = ? AND combination_id = ?",
                (game_id, char_id, combination_id),
            ).fetchone()
        return row is not None

    # -- Custom Spells --

    def save_custom_spell(self, spell_data: dict[str, Any]) -> None:
        """Save a player-invented spell."""
        spell_id = spell_data.get("id", str(uuid.uuid4()))
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO custom_spells "
                "(id, game_id, character_id, name, level, school, description, "
                "mechanics, elements, plausibility, creation_dc, created_turn, location_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    spell_id,
                    spell_data["game_id"],
                    spell_data["character_id"],
                    spell_data["name"],
                    spell_data["level"],
                    spell_data.get("school", "evocation"),
                    spell_data["description"],
                    json.dumps(spell_data.get("mechanics", {})),
                    json.dumps(spell_data.get("elements", [])),
                    spell_data.get("plausibility"),
                    spell_data.get("creation_dc"),
                    spell_data["created_turn"],
                    spell_data.get("location_id"),
                ),
            )

    def get_custom_spells(self, game_id: str, char_id: str) -> list[dict[str, Any]]:
        """Return all custom spells for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM custom_spells "
                "WHERE game_id = ? AND character_id = ? ORDER BY created_turn",
                (game_id, char_id),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_custom_spell(self, spell_id: str) -> dict[str, Any] | None:
        """Return a single custom spell by ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM custom_spells WHERE id = ?",
                (spell_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def delete_all(self, game_id: str) -> None:
        """Delete all spell creation data for a game (used in game deletion cascade)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM discovered_combinations WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM custom_spells WHERE game_id = ?", (game_id,))

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert a sqlite3.Row to a spell dict."""
        d = dict(row)
        d["mechanics"] = json.loads(d.get("mechanics", "{}"))
        d["elements"] = json.loads(d.get("elements", "[]"))
        return d
