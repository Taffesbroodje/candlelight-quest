from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CharacterClass(str, Enum):
    FIGHTER = "fighter"
    WIZARD = "wizard"
    ROGUE = "rogue"
    CLERIC = "cleric"


class Race(str, Enum):
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"
    HALF_ORC = "half_orc"


class AbilityScores(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class HitPoints(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current: int = 0
    max: int = 0
    temp: int = 0


class Character(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    race: Race
    char_class: CharacterClass
    level: int = 1
    xp: int = 0
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    hp: HitPoints = Field(default_factory=HitPoints)
    ac: int = 10
    proficiency_bonus: int = 2
    skill_proficiencies: list[str] = Field(default_factory=list)
    saving_throw_proficiencies: list[str] = Field(default_factory=list)
    class_features: list[str] = Field(default_factory=list)
    inventory_id: Optional[str] = None
    equipped_weapon_id: Optional[str] = None
    equipped_armor_id: Optional[str] = None
    conditions: list[str] = Field(default_factory=list)
    hit_dice_remaining: int = 1
    speed: int = 30
    game_id: str
