from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from text_rpg.models.character import HitPoints


class CombatantType(str, Enum):
    PLAYER = "player"
    ALLY = "ally"
    ENEMY = "enemy"


class Combatant(BaseModel):
    entity_id: str
    name: str
    combatant_type: CombatantType
    initiative: int = 0
    initiative_bonus: int = 0
    hp: HitPoints = Field(default_factory=HitPoints)
    ac: int = 10
    is_active: bool = True
    conditions: list[str] = Field(default_factory=list)
    has_acted: bool = False


class CombatState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str
    is_active: bool = True
    round_number: int = 1
    current_turn_index: int = 0
    combatants: list[Combatant] = Field(default_factory=list)
    turn_order: list[str] = Field(default_factory=list)
