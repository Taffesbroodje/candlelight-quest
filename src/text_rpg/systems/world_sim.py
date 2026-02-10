"""World simulator — runs once per turn to advance NPC schedules and ambient state."""
from __future__ import annotations

import json
import logging
from typing import Any

from text_rpg.mechanics import world_clock
from text_rpg.mechanics.world_sim import get_npc_location, is_npc_available
from text_rpg.utils import safe_json, safe_props

logger = logging.getLogger(__name__)


class WorldSimulator:
    """Lightweight system called once per turn (not a GameSystem)."""

    def __init__(self, repos: dict[str, Any]) -> None:
        self.repos = repos
        self._last_period: str | None = None

    def tick(self, game_id: str, world_time: int) -> list[dict]:
        """Advance world state based on time. Returns events to record."""
        period = world_clock.get_period(world_time)

        # Only move NPCs when the period actually changes
        if period == self._last_period:
            return []
        self._last_period = period

        events: list[dict] = []
        events += self._update_npc_locations(game_id, period)
        self._cleanup_expired_entities(game_id, world_time)
        self._update_shop_prices_from_events(game_id)
        return events

    def _update_npc_locations(self, game_id: str, period: str) -> list[dict]:
        """Move NPCs with schedules to their current scheduled location."""
        events: list[dict] = []
        try:
            entity_repo = self.repos.get("entity")
            if not entity_repo:
                return events

            # Get all NPCs for this game
            all_npcs = entity_repo.get_by_game(game_id)
            for npc in all_npcs:
                if npc.get("entity_type") != "npc" or not npc.get("is_alive", True):
                    continue

                scheduled_loc = get_npc_location(npc, period)
                if scheduled_loc is None:
                    continue  # NPC is unavailable (sleeping etc.)

                current_loc = npc.get("location_id", "")
                if current_loc != scheduled_loc:
                    # Move the NPC
                    entity_repo.update_field(npc["id"], "location_id", scheduled_loc)
                    logger.debug(f"NPC {npc['name']} moved from {current_loc} to {scheduled_loc}")
        except Exception as e:
            logger.warning(f"NPC schedule update failed: {e}")

        return events

    def _update_shop_prices_from_events(self, game_id: str) -> None:
        """Check for world events that affect shop prices."""
        try:
            shop_repo = self.repos.get("shop")
            event_repo = self.repos.get("event_ledger")
            if not shop_repo or not event_repo:
                return
            recent = event_repo.get_recent(game_id, limit=5)
            for event in recent:
                details = safe_json(event.get("mechanical_details"), {})
                if not details:
                    continue
                effect = details.get("economy_effect")
                if effect == "trade_route_disrupted":
                    # Increase prices at all shops temporarily
                    location_id = event.get("location_id", "")
                    if location_id:
                        shops = shop_repo.get_shop_by_location(game_id, location_id)
                        for s in shops:
                            if s.get("price_modifier", 1.0) < 1.3:
                                shop_repo.update_price_modifier(s["id"], 1.3)
                elif effect == "trade_route_restored":
                    location_id = event.get("location_id", "")
                    if location_id:
                        shops = shop_repo.get_shop_by_location(game_id, location_id)
                        for s in shops:
                            if s.get("price_modifier", 1.0) > 1.0:
                                shop_repo.update_price_modifier(s["id"], 1.0)
        except Exception as e:
            logger.warning(f"Shop price update failed: {e}")

    def _cleanup_expired_entities(self, game_id: str, world_time: int) -> None:
        """Remove temporary entities whose duration has expired."""
        try:
            entity_repo = self.repos.get("entity")
            if not entity_repo:
                return

            all_entities = entity_repo.get_by_game(game_id)
            for entity in all_entities:
                props = safe_props(entity)
                if not props:
                    continue

                expires_at = props.get("expires_at_time")
                if expires_at is not None and world_time >= expires_at:
                    # Remove the temporary entity
                    entity_repo.update_field(entity["id"], "is_alive", False)
                    logger.debug(f"Temporary entity {entity.get('name')} expired and removed")
        except Exception as e:
            logger.warning(f"Entity cleanup failed: {e}")
