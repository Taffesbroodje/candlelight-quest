"""Multiclassing mechanics — ability requirements and class level management."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.mechanics.leveling import HIT_DICE, proficiency_bonus
from text_rpg.utils import safe_json

# Primary ability requirement for multiclassing (need 13+ to qualify)
CLASS_PREREQUISITES: dict[str, str] = {
    "fighter": "strength",
    "wizard": "intelligence",
    "rogue": "dexterity",
    "cleric": "wisdom",
}

# Maximum number of classes a character can have
MAX_CLASSES = 2


def can_multiclass(ability_scores: dict, target_class: str, current_classes: dict) -> tuple[bool, str]:
    """Check if a character can multiclass into target_class.

    Args:
        ability_scores: Character's ability scores dict
        target_class: The class to multiclass into
        current_classes: Dict of {class_name: level}

    Returns:
        (can_multiclass, reason)
    """
    ability_scores = safe_json(ability_scores, {})
    current_classes = safe_json(current_classes, {})

    target_class = target_class.lower()

    # Already have this class
    if target_class in current_classes:
        return True, f"Already have {target_class} levels."

    # Check max classes
    if len(current_classes) >= MAX_CLASSES and target_class not in current_classes:
        return False, f"Maximum {MAX_CLASSES} classes allowed."

    # Check prerequisite ability score
    required_ability = CLASS_PREREQUISITES.get(target_class)
    if not required_ability:
        return False, f"Unknown class: {target_class}"

    score = ability_scores.get(required_ability, 10)
    if score < 13:
        return False, f"Need {required_ability.title()} 13+ to multiclass into {target_class.title()} (current: {score})."

    # Also need 13+ in current class primary abilities
    for cls_name in current_classes:
        cls_req = CLASS_PREREQUISITES.get(cls_name)
        if cls_req and ability_scores.get(cls_req, 10) < 13:
            return False, f"Need {cls_req.title()} 13+ in your current class {cls_name.title()} to multiclass."

    return True, "Meets prerequisites."


def multiclass_level_up(character: dict, new_class: str) -> dict[str, Any]:
    """Calculate what a character gains from leveling up in a new class.

    Returns:
        Dict with: hit_die, hp_roll_dice, new_class_levels, new_total_level, new_proficiency_bonus
    """
    class_levels = safe_json(character.get("class_levels"), {})

    new_class = new_class.lower()
    old_class_level = class_levels.get(new_class, 0)
    new_class_level = old_class_level + 1

    new_levels = dict(class_levels)
    new_levels[new_class] = new_class_level

    total_level = sum(new_levels.values())
    hit_die = HIT_DICE.get(new_class, "1d8")

    return {
        "hit_die": hit_die,
        "hp_roll_dice": hit_die,
        "new_class_levels": new_levels,
        "new_total_level": total_level,
        "new_proficiency_bonus": proficiency_bonus(total_level),
        "class_leveled": new_class,
        "class_level": new_class_level,
    }


def get_total_level(class_levels: dict | str) -> int:
    """Get total character level from all classes."""
    class_levels = safe_json(class_levels, {})
    return sum(class_levels.values()) if class_levels else 0


def format_class_display(class_levels: dict | str, primary_class: str = "") -> str:
    """Format class levels for display. e.g. 'Fighter 3 / Wizard 2'."""
    class_levels = safe_json(class_levels, {})
    if not class_levels:
        return primary_class.title() if primary_class else "Unknown"

    parts = []
    for cls, lvl in sorted(class_levels.items(), key=lambda x: x[1], reverse=True):
        parts.append(f"{cls.title()} {lvl}")
    return " / ".join(parts)
