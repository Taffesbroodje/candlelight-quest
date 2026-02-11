from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    # Combat
    COMBAT_START = "COMBAT_START"
    COMBAT_END = "COMBAT_END"
    ATTACK = "ATTACK"
    DAMAGE = "DAMAGE"
    HEAL = "HEAL"
    DEATH = "DEATH"
    WOUND = "WOUND"
    PLAYER_DEFEAT = "PLAYER_DEFEAT"
    COMBAT_FLEE = "COMBAT_FLEE"
    COMBAT_FLEE_FAIL = "COMBAT_FLEE_FAIL"
    NPC_FLEE = "NPC_FLEE"
    # Movement & exploration
    MOVE = "MOVE"
    DISCOVERY = "DISCOVERY"
    EXPLORATION_FAIL = "EXPLORATION_FAIL"
    GUARD_CONFRONTATION = "GUARD_CONFRONTATION"
    # Social
    DIALOGUE = "DIALOGUE"
    QUEST_NEGOTIATION = "QUEST_NEGOTIATION"
    COMPANION_RECRUIT = "COMPANION_RECRUIT"
    COMPANION_DISMISS = "COMPANION_DISMISS"
    GIFT_GIVEN = "GIFT_GIVEN"
    # Items & inventory
    ITEM_PICKUP = "ITEM_PICKUP"
    ITEM_DROP = "ITEM_DROP"
    ITEM_USE = "ITEM_USE"
    ITEM_STORED = "ITEM_STORED"
    ITEM_RETRIEVED = "ITEM_RETRIEVED"
    EQUIP = "EQUIP"
    UNEQUIP = "UNEQUIP"
    SCROLL_USE = "SCROLL_USE"
    # Quests
    QUEST_START = "QUEST_START"
    QUEST_COMPLETE = "QUEST_COMPLETE"
    QUEST_UPDATE = "QUEST_UPDATE"
    QUEST_FAILED = "QUEST_FAILED"
    # Spells
    SPELL_CAST = "SPELL_CAST"
    SPELL_CONCENTRATION_LOST = "SPELL_CONCENTRATION_LOST"
    SPELL_CREATED = "SPELL_CREATED"
    SPELL_COMBINED = "SPELL_COMBINED"
    SPELL_CREATION_FAIL = "SPELL_CREATION_FAIL"
    WILD_MAGIC_SURGE = "WILD_MAGIC_SURGE"
    # Crafting & skills
    CRAFT_SUCCESS = "CRAFT_SUCCESS"
    CRAFT_FAIL = "CRAFT_FAIL"
    SKILL_LEARNED = "SKILL_LEARNED"
    # Economy & shops
    SHOP_BROWSE = "SHOP_BROWSE"
    SHOP_BUY = "SHOP_BUY"
    SHOP_SELL = "SHOP_SELL"
    # Housing
    HOME_PURCHASED = "HOME_PURCHASED"
    HOME_UPGRADED = "HOME_UPGRADED"
    # Puzzles
    PUZZLE_SOLVED = "PUZZLE_SOLVED"
    PUZZLE_FAILED = "PUZZLE_FAILED"
    TRAP_DAMAGE = "TRAP_DAMAGE"
    # Director & world
    CREATIVE_ACTION = "CREATIVE_ACTION"
    CREATIVE_ACTION_FAIL = "CREATIVE_ACTION_FAIL"
    DIRECTOR_NPC_SPAWN = "DIRECTOR_NPC_SPAWN"
    DIRECTOR_QUEST_AVAILABLE = "DIRECTOR_QUEST_AVAILABLE"
    DIRECTOR_QUEST_FOLLOW_UP = "DIRECTOR_QUEST_FOLLOW_UP"
    WORLD_EVENT = "WORLD_EVENT"
    STORY_BEAT = "STORY_BEAT"
    FACTION_GOAL = "FACTION_GOAL"
    # Core
    LEVEL_UP = "LEVEL_UP"
    REST = "REST"
    WORLD_CHANGE = "WORLD_CHANGE"
    # Time travel (Phase 6)
    TIME_TRAVEL = "TIME_TRAVEL"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    # Fallback
    CUSTOM = "CUSTOM"


class GameEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str
    event_type: EventType
    turn_number: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    location_id: Optional[str] = None
    description: str = ""
    mechanical_details: dict[str, Any] = Field(default_factory=dict)
    is_canonical: bool = True
