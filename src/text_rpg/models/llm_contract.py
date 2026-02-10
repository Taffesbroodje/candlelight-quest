from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class NarrativeRequest(BaseModel):
    scene_description: str
    mechanical_outcome: str
    tone: str = "neutral"
    max_length: int = 200


class NarrativeResponse(BaseModel):
    narrative_text: str = ""
    suggested_hooks: list[str] = Field(default_factory=list)


class ScenePlan(BaseModel):
    available_actions: list[str] = Field(default_factory=list)
    environmental_details: list[str] = Field(default_factory=list)
    npc_intentions: dict[str, str] = Field(default_factory=dict)
    tension_level: str = "low"


class ActionClassification(BaseModel):
    action_type: str = "custom"
    target: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
