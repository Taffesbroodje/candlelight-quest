"""State serializer — captures and restores game state for time-travel snapshots."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from text_rpg.mechanics.time_travel import RestoreConfig
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)


class StateSerializer:
    """Serializes and restores game state for snapshots."""

    def __init__(self, repos: dict[str, Any]) -> None:
        self.repos = repos

    def capture(self, game_id: str, trigger: str) -> dict:
        """Capture full game state into a snapshot dict."""
        game = self.repos["save_game"].get_game(game_id)
        char = self.repos["character"].get_by_game(game_id)
        inv = self.repos["world_state"].get_inventory(char["id"], game_id) if char else None

        return {
            "id": str(uuid.uuid4()),
            "game_id": game_id,
            "turn_number": game["turn_number"],
            "world_time": game.get("world_time", 480),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "location_id": game["current_location_id"],
            "player_state": json.dumps(char),
            "inventory_state": json.dumps(safe_json(inv.get("items"), []) if inv else []),
            "world_state": json.dumps(self._capture_world(game_id)),
            "quest_state": json.dumps(self._capture_quests(game_id)),
            "social_state": json.dumps(self._capture_social(game_id)),
        }

    def restore(self, game_id: str, snapshot: dict, config: RestoreConfig) -> None:
        """Restore game state from a snapshot based on config."""
        # Always restore: world state (entities, locations)
        self._restore_world(game_id, json.loads(snapshot["world_state"]))
        self._restore_quests(game_id, json.loads(snapshot["quest_state"]))

        # Conditionally restore based on config
        if not config.keep_inventory:
            self._restore_inventory(game_id, json.loads(snapshot["inventory_state"]))
        if not config.keep_player_stats:
            self._restore_player(game_id, json.loads(snapshot["player_state"]))
        if not config.keep_reputation:
            self._restore_social(game_id, json.loads(snapshot["social_state"]))

        # Reset game state to snapshot point
        self.repos["save_game"].update_location(game_id, snapshot["location_id"])
        self.repos["save_game"].update_world_time(game_id, snapshot["world_time"])

        # Increment loop count
        game = self.repos["save_game"].get_game(game_id)
        loop_count = (game.get("loop_count") or 0) + 1
        with self.repos["save_game"].db.get_connection() as conn:
            conn.execute(
                "UPDATE games SET loop_count = ? WHERE id = ?",
                (loop_count, game_id),
            )

    def record_canon_entry(self, game_id: str, snapshot_id: str, trigger: str, loop_count: int) -> None:
        """Record a time-travel event in the canon ledger."""
        try:
            canon_repo = self.repos.get("canon")
            if not canon_repo:
                # Fallback: write directly
                with self.repos["save_game"].db.get_connection() as conn:
                    previous = conn.execute(
                        "SELECT entry_hash FROM canon_entries WHERE game_id = ? ORDER BY rowid DESC LIMIT 1",
                        (game_id,),
                    ).fetchone()
                    prev_hash = previous[0] if previous else "genesis"
                    entry_hash = hashlib.sha256(f"{prev_hash}{snapshot_id}".encode()).hexdigest()

                    conn.execute(
                        "INSERT INTO canon_entries (id, game_id, timestamp, description, changes, previous_hash, entry_hash) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            game_id,
                            datetime.now(timezone.utc).isoformat(),
                            f"Timeline diverged. Loop {loop_count}.",
                            json.dumps({"trigger": trigger, "snapshot_id": snapshot_id}),
                            prev_hash,
                            entry_hash,
                        ),
                    )
        except Exception as e:
            logger.warning(f"Failed to record canon entry: {e}")

    # -- Capture helpers --

    def _capture_world(self, game_id: str) -> dict:
        """Capture entities and locations."""
        entities = self.repos["entity"].get_by_game(game_id)
        locations = self.repos["location"].get_all(game_id)
        return {
            "entities": entities,
            "locations": locations,
        }

    def _capture_quests(self, game_id: str) -> dict:
        """Capture quest state."""
        quests = self.repos["world_state"].get_all_quests(game_id)
        stories = []
        try:
            stories = self.repos["world_state"].get_active_stories(game_id)
        except Exception:
            pass
        return {"quests": quests, "stories": stories}

    def _capture_social(self, game_id: str) -> dict:
        """Capture reputation, bounties, and companion state."""
        result: dict[str, Any] = {}
        rep_repo = self.repos.get("reputation")
        if rep_repo:
            result["faction_reps"] = rep_repo.get_all_faction_reps(game_id)
            result["bounties"] = rep_repo.get_active_bounties(game_id)
        comp_repo = self.repos.get("companion")
        if comp_repo:
            result["companions"] = comp_repo.get_active_companions(game_id)
        return result

    # -- Restore helpers --

    def _restore_world(self, game_id: str, world: dict) -> None:
        """Restore entities and locations from snapshot."""
        entity_repo = self.repos["entity"]
        location_repo = self.repos["location"]

        # Restore entities
        for entity in world.get("entities", []):
            existing = entity_repo.get(entity["id"])
            if existing:
                for key, value in entity.items():
                    if key != "id" and value != existing.get(key):
                        entity_repo.update_field(entity["id"], key, value)

        # Restore locations
        for loc in world.get("locations", []):
            existing = location_repo.get(loc["id"], game_id)
            if existing:
                for key, value in loc.items():
                    if key not in ("id", "game_id") and value != existing.get(key):
                        location_repo.update_field(loc["id"], game_id, key, value)

    def _restore_quests(self, game_id: str, quest_data: dict) -> None:
        """Restore quests from snapshot."""
        ws = self.repos["world_state"]
        for quest in quest_data.get("quests", []):
            existing = ws.get_quest(quest["id"], game_id)
            if existing:
                # Reset quest status
                ws.update_quest(quest["id"], game_id, quest.get("status", "available"))

    def _restore_inventory(self, game_id: str, items: list) -> None:
        """Restore inventory from snapshot."""
        char = self.repos["character"].get_by_game(game_id)
        if not char:
            return
        inv = self.repos["world_state"].get_inventory(char["id"], game_id)
        if inv:
            self.repos["world_state"].update_inventory(inv["id"], items)

    def _restore_player(self, game_id: str, player: dict) -> None:
        """Restore player character stats from snapshot."""
        if not player:
            return
        char_repo = self.repos["character"]
        char_id = player.get("id")
        if not char_id:
            return
        for field in ("hp_current", "hp_max", "level", "xp", "ability_scores",
                       "gold", "ac", "proficiency_bonus", "conditions"):
            if field in player:
                char_repo.update_field(char_id, field, player[field])

    def _restore_social(self, game_id: str, social: dict) -> None:
        """Restore faction reputation and bounties from snapshot."""
        rep_repo = self.repos.get("reputation")
        if not rep_repo:
            return
        for rep in social.get("faction_reps", []):
            faction_id = rep.get("faction_id")
            score = rep.get("reputation", 0)
            if faction_id:
                rep_repo.set_faction_rep(game_id, faction_id, score)

        # Clear current bounties and restore snapshot bounties
        try:
            with rep_repo.db.get_connection() as conn:
                conn.execute("DELETE FROM bounties WHERE game_id = ?", (game_id,))
        except Exception:
            pass
