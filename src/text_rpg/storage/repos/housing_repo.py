"""Repository for player housing data."""
from __future__ import annotations

import json
import uuid
from typing import Any

from text_rpg.storage.database import Database


class HousingRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_home(self, game_id: str, character_id: str) -> dict | None:
        """Get the player's home."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM housing WHERE game_id = ? AND character_id = ?",
                (game_id, character_id),
            ).fetchone()
        return dict(row) if row else None

    def buy_home(self, game_id: str, character_id: str, location_id: str,
                 name: str = "Home", turn: int = 0) -> str:
        """Purchase a home. Returns the housing ID."""
        home_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO housing (id, game_id, character_id, location_id, name, purchased_turn) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (home_id, game_id, character_id, location_id, name, turn),
            )
        return home_id

    def store_item(self, game_id: str, character_id: str, item_id: str, quantity: int = 1) -> None:
        """Store an item in the home."""
        home = self.get_home(game_id, character_id)
        if not home:
            return
        storage = json.loads(home.get("storage_items", "[]"))
        # Check if item already exists
        for entry in storage:
            if entry.get("item_id") == item_id:
                entry["quantity"] = entry.get("quantity", 0) + quantity
                break
        else:
            storage.append({"item_id": item_id, "quantity": quantity})
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE housing SET storage_items = ? WHERE id = ?",
                (json.dumps(storage), home["id"]),
            )

    def retrieve_item(self, game_id: str, character_id: str, item_id: str) -> bool:
        """Remove one item from home storage. Returns True if found."""
        home = self.get_home(game_id, character_id)
        if not home:
            return False
        storage = json.loads(home.get("storage_items", "[]"))
        for entry in storage:
            if entry.get("item_id") == item_id and entry.get("quantity", 0) > 0:
                entry["quantity"] -= 1
                if entry["quantity"] <= 0:
                    storage.remove(entry)
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE housing SET storage_items = ? WHERE id = ?",
                        (json.dumps(storage), home["id"]),
                    )
                return True
        return False

    def add_upgrade(self, game_id: str, character_id: str, upgrade_id: str) -> None:
        """Add an upgrade to the home."""
        home = self.get_home(game_id, character_id)
        if not home:
            return
        upgrades = json.loads(home.get("upgrades", "[]"))
        if upgrade_id not in upgrades:
            upgrades.append(upgrade_id)
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE housing SET upgrades = ? WHERE id = ?",
                    (json.dumps(upgrades), home["id"]),
                )

    def get_storage_items(self, game_id: str, character_id: str) -> list[dict]:
        """Get items in home storage."""
        home = self.get_home(game_id, character_id)
        if not home:
            return []
        return json.loads(home.get("storage_items", "[]"))

    def get_upgrades(self, game_id: str, character_id: str) -> list[str]:
        """Get home upgrades."""
        home = self.get_home(game_id, character_id)
        if not home:
            return []
        return json.loads(home.get("upgrades", "[]"))
