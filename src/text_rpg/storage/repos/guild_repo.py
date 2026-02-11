"""Repository for guild memberships and work orders."""
from __future__ import annotations

import json
import uuid
from typing import Any

from text_rpg.storage.database import Database


class GuildRepo:
    """CRUD for guild_membership, active_work_orders, and work_order_history."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Guild Membership --

    def join_guild(
        self, game_id: str, char_id: str, guild_id: str, turn: int,
        is_primary: bool = False,
    ) -> None:
        """Create a guild membership record."""
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO guild_membership "
                "(id, game_id, character_id, guild_id, rank, joined_turn, is_primary) "
                "VALUES (?, ?, ?, ?, 'initiate', ?, ?)",
                (str(uuid.uuid4()), game_id, char_id, guild_id, turn, int(is_primary)),
            )

    def get_memberships(self, game_id: str, char_id: str) -> list[dict]:
        """Return all guild memberships for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM guild_membership WHERE game_id = ? AND character_id = ?",
                (game_id, char_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_membership(self, game_id: str, char_id: str, guild_id: str) -> dict | None:
        """Return membership for a specific guild, or None."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM guild_membership "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ?",
                (game_id, char_id, guild_id),
            ).fetchone()
        return dict(row) if row else None

    def update_rank(self, game_id: str, char_id: str, guild_id: str, new_rank: str) -> None:
        """Update a member's rank."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE guild_membership SET rank = ? "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ?",
                (new_rank, game_id, char_id, guild_id),
            )

    def set_primary(self, game_id: str, char_id: str, guild_id: str) -> None:
        """Set a guild as the primary guild (unsets others)."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE guild_membership SET is_primary = 0 "
                "WHERE game_id = ? AND character_id = ?",
                (game_id, char_id),
            )
            conn.execute(
                "UPDATE guild_membership SET is_primary = 1 "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ?",
                (game_id, char_id, guild_id),
            )

    def leave_guild(self, game_id: str, char_id: str, guild_id: str) -> None:
        """Remove a guild membership."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM guild_membership "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ?",
                (game_id, char_id, guild_id),
            )

    # -- Work Orders --

    def accept_work_order(self, order_data: dict) -> None:
        """Create an active work order."""
        order_id = order_data.get("id", str(uuid.uuid4()))
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO active_work_orders "
                "(id, game_id, character_id, guild_id, template_id, order_type, "
                "description, requirements, progress, reward_gold, reward_xp, "
                "reward_rep, accepted_turn, expires_turn, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')",
                (
                    order_id,
                    order_data["game_id"],
                    order_data["character_id"],
                    order_data["guild_id"],
                    order_data["template_id"],
                    order_data["order_type"],
                    order_data.get("description", ""),
                    json.dumps(order_data.get("requirements", {})),
                    json.dumps(order_data.get("progress", {})),
                    order_data.get("reward_gold", 0),
                    order_data.get("reward_xp", 0),
                    order_data.get("reward_rep", 0),
                    order_data.get("accepted_turn", 0),
                    order_data.get("expires_turn"),
                ),
            )

    def get_active_orders(self, game_id: str, char_id: str) -> list[dict]:
        """Return all active work orders for a character."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM active_work_orders "
                "WHERE game_id = ? AND character_id = ? AND status = 'active'",
                (game_id, char_id),
            ).fetchall()
        return [self._order_to_dict(r) for r in rows]

    def get_active_orders_for_guild(
        self, game_id: str, char_id: str, guild_id: str,
    ) -> list[dict]:
        """Return active orders for a specific guild."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM active_work_orders "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ? AND status = 'active'",
                (game_id, char_id, guild_id),
            ).fetchall()
        return [self._order_to_dict(r) for r in rows]

    def update_order_progress(self, order_id: str, progress: dict) -> None:
        """Update progress on a work order."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE active_work_orders SET progress = ? WHERE id = ?",
                (json.dumps(progress), order_id),
            )

    def complete_order(self, order_id: str, game_id: str, char_id: str, turn: int) -> dict | None:
        """Mark a work order as completed and move to history. Returns order data."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM active_work_orders WHERE id = ? AND status = 'active'",
                (order_id,),
            ).fetchone()
            if not row:
                return None

            order = self._order_to_dict(row)

            conn.execute(
                "UPDATE active_work_orders SET status = 'completed' WHERE id = ?",
                (order_id,),
            )

            conn.execute(
                "INSERT INTO work_order_history "
                "(id, game_id, character_id, guild_id, template_id, completed_turn, "
                "reward_gold, reward_xp, reward_rep) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    game_id,
                    char_id,
                    order["guild_id"],
                    order["template_id"],
                    turn,
                    order.get("reward_gold", 0),
                    order.get("reward_xp", 0),
                    order.get("reward_rep", 0),
                ),
            )

        return order

    def abandon_order(self, order_id: str) -> bool:
        """Mark a work order as abandoned."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE active_work_orders SET status = 'abandoned' "
                "WHERE id = ? AND status = 'active'",
                (order_id,),
            )
        return cursor.rowcount > 0

    def get_completed_count(self, game_id: str, char_id: str, guild_id: str) -> int:
        """Count completed work orders for a guild."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM work_order_history "
                "WHERE game_id = ? AND character_id = ? AND guild_id = ?",
                (game_id, char_id, guild_id),
            ).fetchone()
        return row[0] if row else 0

    def delete_all(self, game_id: str) -> None:
        """Delete all guild data for a game (cascade deletion)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM guild_membership WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM active_work_orders WHERE game_id = ?", (game_id,))
            conn.execute("DELETE FROM work_order_history WHERE game_id = ?", (game_id,))

    @staticmethod
    def _order_to_dict(row: Any) -> dict:
        """Convert a sqlite3.Row to a work order dict with JSON deserialization."""
        d = dict(row)
        d["requirements"] = json.loads(d.get("requirements") or "{}")
        d["progress"] = json.loads(d.get("progress") or "{}")
        return d
