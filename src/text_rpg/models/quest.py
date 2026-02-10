from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuestStatus(str, Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestObjective(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    is_complete: bool = False
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    required_count: int = 1
    current_count: int = 0


class Quest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    quest_giver_id: Optional[str] = None
    status: QuestStatus = QuestStatus.AVAILABLE
    objectives: list[QuestObjective] = Field(default_factory=list)
    xp_reward: int = 0
    item_rewards: list[str] = Field(default_factory=list)
    gold_reward: int = 0
    level_requirement: int = 1
    game_id: str
