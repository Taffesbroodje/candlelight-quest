from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    ATTACK = "attack"
    DODGE = "dodge"
    DASH = "dash"
    DISENGAGE = "disengage"
    HELP = "help"
    HIDE = "hide"
    MOVE = "move"
    LOOK = "look"
    SEARCH = "search"
    INTERACT = "interact"
    TALK = "talk"
    USE_ITEM = "use_item"
    REST = "rest"
    CAST_SPELL = "cast_spell"
    CUSTOM = "custom"


@dataclass
class DiceRoll:
    dice_expression: str = ""
    rolls: list[int] = field(default_factory=list)
    modifier: int = 0
    total: int = 0
    purpose: str = ""
    advantage: bool = False
    disadvantage: bool = False


@dataclass
class StateMutation:
    target_type: str = ""
    target_id: str = ""
    field: str = ""
    old_value: Any = None
    new_value: Any = None


@dataclass
class Action:
    action_type: str
    actor_id: str
    target_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ActionResult:
    action_id: str = ""
    success: bool = False
    outcome_description: str = ""
    dice_rolls: list[DiceRoll] = field(default_factory=list)
    state_mutations: list[StateMutation] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    xp_gained: int = 0
