"""Post-turn event handlers — quest notifications, reputation changes, bounties."""
from __future__ import annotations

from typing import Any

from text_rpg.utils import safe_json


class PostTurnEventHandler:
    """Handles post-turn events: quest notifications, reputation changes."""

    def __init__(self, game_id: str, repos: dict[str, Any], display: Any):
        self.game_id = game_id
        self.repos = repos
        self.display = display

    def process(self, result: Any) -> None:
        """Process all post-turn events from a turn result."""
        self._check_quest_events(result)
        self._check_reputation_events(result)

    def _check_quest_events(self, result: Any) -> None:
        """Detect quest-related events and show notifications."""
        if not result.events:
            return
        for event in result.events:
            event_type = event.get("event_type", "")
            details = safe_json(event.get("mechanical_details"), {})

            if event_type in ("DIRECTOR_QUEST_AVAILABLE", "DIRECTOR_QUEST_FOLLOW_UP"):
                quest_name = details.get("quest_name", "")
                if quest_name:
                    self.display.show_quest_notification(quest_name, "new")
            elif event_type == "QUEST_COMPLETE":
                quest_name = details.get("quest_name", "A quest")
                self.display.show_quest_notification(quest_name, "completed")
            elif event_type == "QUEST_NEGOTIATION":
                if details.get("accepted"):
                    quest_name = details.get("quest_name", "")
                    if quest_name:
                        self.display.show_quest_notification(
                            f"{quest_name} (terms negotiated)", "updated"
                        )
            elif event_type == "STORY_BEAT":
                story_name = details.get("story_name", "")
                beat_name = details.get("beat_name", "")
                if story_name:
                    self.display.show_story_notification(story_name, beat_name)

    def _check_reputation_events(self, result: Any) -> None:
        """Check combat events for reputation/bounty consequences."""
        if not result.events:
            return
        rep_repo = self.repos.get("reputation")
        if not rep_repo:
            return

        for event in result.events:
            event_type = event.get("event_type", "")
            details = safe_json(event.get("mechanical_details"), {})

            if event_type == "DEATH":
                self._handle_kill_event(event, rep_repo)
            elif event_type == "QUEST_COMPLETE":
                rep_repo.adjust_faction_rep(self.game_id, "thornfield_guard", 5)
                rep_repo.adjust_faction_rep(self.game_id, "thornfield_merchants", 3)
            elif event_type == "QUEST_FAILED":
                rep_repo.adjust_faction_rep(self.game_id, "thornfield_guard", -5)
                rep_repo.adjust_faction_rep(self.game_id, "thornfield_merchants", -3)

    def _handle_kill_event(self, event: dict, rep_repo: Any) -> None:
        """Handle reputation/bounty consequences of killing an entity."""
        target_id = event.get("target_id", "")
        entity = self.repos["entity"].get(target_id) if target_id else None
        if not entity:
            return

        faction_id = entity.get("faction_id")
        is_hostile = entity.get("is_hostile", False)

        if is_hostile:
            rep_repo.adjust_faction_rep(self.game_id, "thornfield_guard", 3)
        elif faction_id:
            rep_repo.adjust_faction_rep(self.game_id, faction_id, -15)
            region = self._get_current_region()
            npc_name = entity.get("name", "someone")
            rep_repo.add_bounty(self.game_id, region, 25, f"Murder of {npc_name}")
            self.display.console.print(
                f"\n  [red]Your actions have consequences. Bounty added in the region.[/red]"
            )
        else:
            region = self._get_current_region()
            npc_name = entity.get("name", "someone")
            rep_repo.add_bounty(self.game_id, region, 15, f"Murder of {npc_name}")
            rep_repo.adjust_faction_rep(self.game_id, "thornfield_guard", -10)

    def _get_current_region(self) -> str:
        """Get the region_id for the player's current location."""
        game = self.repos["save_game"].get_game(self.game_id)
        loc_id = game.get("current_location_id", "") if game else ""
        loc = self.repos["location"].get(loc_id, self.game_id) if loc_id else None
        return loc.get("region_id", "verdant_reach") if loc else "verdant_reach"
