"""Base interface for pluggable game systems."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from text_rpg.models.action import Action, ActionResult


class GameContext:
    """Snapshot of current game state passed to systems."""

    def __init__(
        self,
        game_id: str,
        character: dict,
        location: dict,
        entities: list[dict],
        combat_state: dict | None = None,
        inventory: dict | None = None,
        recent_events: list[dict] | None = None,
        turn_number: int = 0,
        active_quests: list[dict] | None = None,
        world_time: int = 480,
        companions: list[dict] | None = None,
        loop_count: int = 0,
    ):
        self.game_id = game_id
        self.character = character
        self.location = location
        self.entities = entities
        self.combat_state = combat_state
        self.inventory = inventory
        self.recent_events = recent_events or []
        self.turn_number = turn_number
        self.active_quests = active_quests or []
        self.world_time = world_time
        self.companions = companions or []
        self.loop_count = loop_count


class GameSystem(ABC):
    """Base class for all pluggable game systems."""

    @property
    @abstractmethod
    def system_id(self) -> str: ...

    @property
    @abstractmethod
    def handled_action_types(self) -> set[str]: ...

    @abstractmethod
    def can_handle(self, action: Action, context: GameContext) -> bool: ...

    @abstractmethod
    def resolve(self, action: Action, context: GameContext) -> ActionResult: ...

    def get_available_actions(self, context: GameContext) -> list[dict]: ...

    def inject(self, *, director: Any = None, repos: dict | None = None, llm: Any = None, **kwargs: Any) -> None:
        """Inject runtime dependencies. Systems override to accept what they need."""

    def on_turn_start(self, context: GameContext) -> list[dict]:
        return []

    def on_turn_end(self, context: GameContext) -> list[dict]:
        return []
