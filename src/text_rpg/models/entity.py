from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from text_rpg.models.character import AbilityScores, HitPoints


class Attack(BaseModel):
    name: str
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    attack_bonus: int = 0
    properties: list[str] = Field(default_factory=list)


class LootEntry(BaseModel):
    item_id: str
    drop_chance: float = 1.0
    quantity_min: int = 1
    quantity_max: int = 1


class Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    entity_type: str = "npc"
    description: str = ""
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    hp: HitPoints = Field(default_factory=HitPoints)
    ac: int = 10
    speed: int = 30
    level: int = 1
    challenge_rating: Optional[float] = None
    attacks: list[Attack] = Field(default_factory=list)
    behaviors: list[str] = Field(default_factory=list)
    dialogue_tags: list[str] = Field(default_factory=list)
    location_id: str = ""
    loot_table: list[LootEntry] = Field(default_factory=list)
    is_hostile: bool = False
    is_alive: bool = True
    game_id: str = ""
