from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Connection(BaseModel):
    target_location_id: str
    direction: str
    description: str = ""
    is_locked: bool = False
    lock_dc: Optional[int] = None


class Location(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    region_id: str = ""
    description: str = ""
    location_type: str = "wilderness"
    connections: list[Connection] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    visited: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class Region(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    locations: list[str] = Field(default_factory=list)
    level_range_min: int = 1
    level_range_max: int = 5
    climate: str = "temperate"
    faction: Optional[str] = None
