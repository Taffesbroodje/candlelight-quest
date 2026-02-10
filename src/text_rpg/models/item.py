from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemType(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    POTION = "potion"
    SCROLL = "scroll"
    MISC = "misc"
    QUEST = "quest"
    TOOL = "tool"
    AMMUNITION = "ammunition"


class WeaponProperties(BaseModel):
    damage_dice: str = "1d4"
    damage_type: str = "bludgeoning"
    weapon_type: str = "melee"
    properties: list[str] = Field(default_factory=list)
    range_normal: Optional[int] = None
    range_long: Optional[int] = None


class ArmorProperties(BaseModel):
    ac_base: int = 10
    armor_type: str = "light"
    max_dex_bonus: Optional[int] = None
    stealth_disadvantage: bool = False
    strength_requirement: Optional[int] = None


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    item_type: ItemType = ItemType.MISC
    weight: float = 0.0
    value_gp: int = 0
    rarity: str = "common"
    weapon_properties: Optional[WeaponProperties] = None
    armor_properties: Optional[ArmorProperties] = None
    effects: dict[str, Any] = Field(default_factory=dict)
    consumable: bool = False
    stack_size: int = 1
