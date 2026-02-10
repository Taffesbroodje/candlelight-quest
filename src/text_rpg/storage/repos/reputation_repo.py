"""Repository for faction reputation, NPC reputation, and bounties."""
from __future__ import annotations

import json
import uuid
from typing import Any

from text_rpg.storage.database import Database


class ReputationRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Faction Reputation --

    def get_faction_rep(self, game_id: str, faction_id: str) -> int:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT reputation FROM faction_reputation WHERE game_id = ? AND faction_id = ?",
                (game_id, faction_id),
            ).fetchone()
        return row["reputation"] if row else 0

    def set_faction_rep(self, game_id: str, faction_id: str, value: int) -> None:
        from text_rpg.mechanics.reputation import clamp_reputation
        value = clamp_reputation(value)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM faction_reputation WHERE game_id = ? AND faction_id = ?",
                (game_id, faction_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE faction_reputation SET reputation = ? WHERE id = ?",
                    (value, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO faction_reputation (id, game_id, faction_id, reputation) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), game_id, faction_id, value),
                )

    def adjust_faction_rep(self, game_id: str, faction_id: str, delta: int) -> int:
        """Adjust faction rep by delta. Returns new value."""
        from text_rpg.mechanics.reputation import adjust_reputation
        current = self.get_faction_rep(game_id, faction_id)
        new_val = adjust_reputation(current, delta)
        self.set_faction_rep(game_id, faction_id, new_val)
        return new_val

    def get_all_faction_reps(self, game_id: str) -> dict[str, int]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT faction_id, reputation FROM faction_reputation WHERE game_id = ?",
                (game_id,),
            ).fetchall()
        return {row["faction_id"]: row["reputation"] for row in rows}

    # -- NPC Reputation --

    def get_npc_rep(self, game_id: str, entity_id: str) -> int:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT reputation FROM npc_reputation WHERE game_id = ? AND entity_id = ?",
                (game_id, entity_id),
            ).fetchone()
        return row["reputation"] if row else 0

    def adjust_npc_rep(self, game_id: str, entity_id: str, delta: int) -> int:
        """Adjust NPC rep by delta. Returns new value."""
        from text_rpg.mechanics.reputation import adjust_reputation, clamp_reputation
        current = self.get_npc_rep(game_id, entity_id)
        new_val = adjust_reputation(current, delta)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM npc_reputation WHERE game_id = ? AND entity_id = ?",
                (game_id, entity_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE npc_reputation SET reputation = ? WHERE id = ?",
                    (new_val, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO npc_reputation (id, game_id, entity_id, reputation) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), game_id, entity_id, new_val),
                )
        return new_val

    # -- Bounties --

    def get_bounty(self, game_id: str, region: str) -> dict:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM bounties WHERE game_id = ? AND region = ?",
                (game_id, region),
            ).fetchone()
        if not row:
            return {"region": region, "amount": 0, "crimes": []}
        result = dict(row)
        crimes = result.get("crimes", "[]")
        if isinstance(crimes, str):
            result["crimes"] = json.loads(crimes)
        return result

    def add_bounty(self, game_id: str, region: str, amount: int, crime_desc: str) -> None:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, amount, crimes FROM bounties WHERE game_id = ? AND region = ?",
                (game_id, region),
            ).fetchone()
            if row:
                old_crimes = json.loads(row["crimes"]) if isinstance(row["crimes"], str) else (row["crimes"] or [])
                old_crimes.append(crime_desc)
                conn.execute(
                    "UPDATE bounties SET amount = ?, crimes = ? WHERE id = ?",
                    (row["amount"] + amount, json.dumps(old_crimes), row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO bounties (id, game_id, region, amount, crimes) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), game_id, region, amount, json.dumps([crime_desc])),
                )

    def pay_bounty(self, game_id: str, region: str) -> int:
        """Pay off bounty in a region. Returns amount paid."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, amount FROM bounties WHERE game_id = ? AND region = ?",
                (game_id, region),
            ).fetchone()
            if not row or row["amount"] <= 0:
                return 0
            amount = row["amount"]
            conn.execute(
                "UPDATE bounties SET amount = 0, crimes = '[]' WHERE id = ?",
                (row["id"],),
            )
            return amount

    def decay_bounty(self, game_id: str, region: str, amount: int) -> None:
        """Reduce bounty by amount (e.g., on long rest). Minimum 0."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT id, amount FROM bounties WHERE game_id = ? AND region = ?",
                (game_id, region),
            ).fetchone()
            if row and row["amount"] > 0:
                new_amount = max(0, row["amount"] - amount)
                conn.execute(
                    "UPDATE bounties SET amount = ? WHERE id = ?",
                    (new_amount, row["id"]),
                )

    def get_all_bounties(self, game_id: str) -> list[dict]:
        """Get all bounties for a game."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bounties WHERE game_id = ? AND amount > 0",
                (game_id,),
            ).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            crimes = result.get("crimes", "[]")
            if isinstance(crimes, str):
                result["crimes"] = json.loads(crimes)
            results.append(result)
        return results
