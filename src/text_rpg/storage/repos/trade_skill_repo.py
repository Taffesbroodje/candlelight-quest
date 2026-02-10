"""Repository for trade skill records."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from text_rpg.storage.database import Database


class TradeSkillRepo:
    """Repository for trade skills and known recipes."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_skills(self, game_id: str, character_id: str) -> list[dict]:
        """Get all trade skills for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM trade_skills WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_skill(self, game_id: str, character_id: str, skill_name: str) -> dict | None:
        """Get a specific trade skill."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM trade_skills WHERE game_id = ? AND character_id = ? AND skill_name = ?",
                (game_id, character_id, skill_name),
            ).fetchone()
        return dict(row) if row else None

    def learn_skill(self, game_id: str, character_id: str, skill_name: str, trainer_id: str | None = None) -> None:
        """Learn a new trade skill (or mark as learned if it exists)."""
        skill_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO trade_skills (id, game_id, character_id, skill_name, level, xp, is_learned, trainer_id)
                   VALUES (?, ?, ?, ?, 1, 0, 1, ?)
                   ON CONFLICT(game_id, character_id, skill_name)
                   DO UPDATE SET is_learned = 1, trainer_id = excluded.trainer_id""",
                (skill_id, game_id, character_id, skill_name, trainer_id),
            )

    def add_xp(self, game_id: str, character_id: str, skill_name: str, xp: int) -> dict:
        """Add XP to a trade skill and return updated skill data."""
        skill = self.get_skill(game_id, character_id, skill_name)
        if not skill:
            return {}
        new_xp = skill.get("xp", 0) + xp
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE trade_skills SET xp = ? WHERE game_id = ? AND character_id = ? AND skill_name = ?",
                (new_xp, game_id, character_id, skill_name),
            )

        # Check for level up
        from text_rpg.mechanics.crafting import can_level_up_trade_skill, trade_skill_level_for_xp
        old_level = skill.get("level", 1)
        new_level = trade_skill_level_for_xp(new_xp)
        if new_level > old_level:
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE trade_skills SET level = ? WHERE game_id = ? AND character_id = ? AND skill_name = ?",
                    (new_level, game_id, character_id, skill_name),
                )

        return {"skill_name": skill_name, "xp": new_xp, "level": new_level, "leveled_up": new_level > old_level}

    def get_known_recipes(self, game_id: str, character_id: str) -> list[dict]:
        """Get all known recipes for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM known_recipes WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def learn_recipe(self, game_id: str, character_id: str, recipe_id: str, skill_name: str) -> None:
        """Record that a character has learned a recipe."""
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO known_recipes (id, game_id, character_id, recipe_id, skill_name, learned_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rec_id, game_id, character_id, recipe_id, skill_name, now),
            )

    def knows_recipe(self, game_id: str, character_id: str, recipe_id: str) -> bool:
        """Check if a character knows a specific recipe."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM known_recipes WHERE game_id = ? AND character_id = ? AND recipe_id = ?",
                (game_id, character_id, recipe_id),
            ).fetchone()
        return row is not None
