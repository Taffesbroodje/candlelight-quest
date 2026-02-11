"""Spell invention mechanics — DC calculation, validation, and wild magic surges.

Pure mechanics — no I/O. Used by SpellCreationSystem when players invent new spells.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from text_rpg.mechanics.elements import DamageType

# Location bonuses for spell invention (negative = easier)
LOCATION_BONUSES: dict[str, int] = {
    "arcane_tower": -8,
    "academy": -6,
    "library": -4,
    "temple": -3,
    "enchanted_grove": -3,
    "ley_line": -5,
    "workshop": -2,
}

# DC modifiers per spell level (higher level = harder to invent)
SPELL_LEVEL_DC_MODIFIER: dict[int, int] = {
    0: 0,
    1: 5,
    2: 10,
    3: 15,
    4: 22,
    5: 30,
    6: 40,
}

# Maximum damage dice allowed per spell level (for validation)
MAX_DAMAGE_DICE: dict[int, str] = {
    0: "1d10",
    1: "4d6",
    2: "5d8",
    3: "8d6",
    4: "8d8",
    5: "10d8",
    6: "12d8",
}

VALID_SCHOOLS = frozenset({
    "abjuration", "conjuration", "divination", "enchantment",
    "evocation", "illusion", "necromancy", "transmutation",
})


@dataclass
class SpellProposal:
    """LLM-evaluated spell concept from the player."""
    name: str
    description: str
    level: int
    school: str
    elements: list[str]
    mechanics: dict[str, Any]
    plausibility: float
    reasoning: str


@dataclass
class WildMagicSurge:
    """Result of a failed spell invention attempt."""
    description: str
    damage_to_caster: int
    conditions_applied: list[str]
    slot_wasted: bool


def calculate_invention_dc(
    plausibility: float,
    spell_level: int,
    location_type: str | None,
    arcana_proficient: bool,
    affinity_count: int,
) -> int:
    """Calculate the DC for inventing a new spell.

    Uses plausibility_to_dc() as the base, then adds modifiers:
    - Spell level modifier from SPELL_LEVEL_DC_MODIFIER
    - Location bonus from LOCATION_BONUSES (if applicable)
    - Arcana proficiency: -2
    - Per-element affinity trait: -1 each (up to -3)

    Clamped to [5, 45].
    """
    from text_rpg.systems.director.generators import plausibility_to_dc

    base_dc = plausibility_to_dc(plausibility)
    level_mod = SPELL_LEVEL_DC_MODIFIER.get(spell_level, 20)
    location_bonus = LOCATION_BONUSES.get(location_type or "", 0)
    arcana_bonus = -2 if arcana_proficient else 0
    affinity_bonus = -min(3, affinity_count)

    dc = base_dc + level_mod + location_bonus + arcana_bonus + affinity_bonus
    return max(5, min(45, dc))


def validate_spell_proposal(
    proposal: SpellProposal,
    caster_level: int,
) -> tuple[bool, str]:
    """Validate a spell proposal against game constraints.

    Checks:
    - Spell level is within caster's ability (max level = ceil(caster_level/2), cap 6)
    - Damage dice don't exceed MAX_DAMAGE_DICE for the level
    - School is valid

    Returns (is_valid, reason).
    """
    max_spell_level = min(6, (caster_level + 1) // 2)
    if proposal.level > max_spell_level:
        return False, f"A level {caster_level} caster cannot create level {proposal.level} spells (max: {max_spell_level})."

    if proposal.school not in VALID_SCHOOLS:
        return False, f"'{proposal.school}' is not a valid school of magic."

    # Validate damage dice if present
    damage_dice = proposal.mechanics.get("damage_dice")
    if damage_dice:
        max_dice = MAX_DAMAGE_DICE.get(proposal.level, "12d8")
        if not _dice_within_limit(damage_dice, max_dice):
            return False, f"Damage dice '{damage_dice}' exceeds maximum '{max_dice}' for level {proposal.level} spells."

    return True, ""


def generate_wild_magic_surge(
    spell_level: int,
    margin_of_failure: int,
) -> WildMagicSurge:
    """Generate a wild magic surge from a failed spell invention.

    Severity based on margin of failure:
    - 1-5: Minor (slot wasted, cosmetic effect)
    - 6-10: Moderate (1d6 damage to caster, possible condition)
    - 11+: Severe (2d8 damage, condition applied)
    """
    if margin_of_failure <= 5:
        descriptions = [
            "Sparks fizzle harmlessly from your fingertips.",
            "The air crackles briefly, then fades to nothing.",
            "A puff of colored smoke escapes your hands.",
            "Your spell fizzles with a quiet pop.",
        ]
        return WildMagicSurge(
            description=random.choice(descriptions),
            damage_to_caster=0,
            conditions_applied=[],
            slot_wasted=True,
        )

    if margin_of_failure <= 10:
        damage = random.randint(1, 6) * max(1, spell_level)
        descriptions = [
            f"Wild magic surges back through you, dealing {damage} damage!",
            f"The spell backfires! Energy crackles through your body for {damage} damage.",
            f"Uncontrolled magic lashes out, striking you for {damage} damage!",
        ]
        conditions = ["dazed"] if random.random() < 0.3 else []
        return WildMagicSurge(
            description=random.choice(descriptions),
            damage_to_caster=damage,
            conditions_applied=conditions,
            slot_wasted=True,
        )

    # Severe: margin 11+
    damage = random.randint(2, 8) * 2 * max(1, spell_level)
    descriptions = [
        f"The spell explodes catastrophically! You take {damage} damage as raw magic tears through you!",
        f"Reality shudders and snaps back violently, dealing {damage} damage!",
        f"A wild magic detonation engulfs you for {damage} damage!",
    ]
    return WildMagicSurge(
        description=random.choice(descriptions),
        damage_to_caster=damage,
        conditions_applied=["dazed"],
        slot_wasted=True,
    )


def _dice_within_limit(dice_str: str, max_dice_str: str) -> bool:
    """Check if a dice expression is within the allowed maximum.

    Compares by max possible damage (num_dice * die_size).
    """
    try:
        actual_max = _max_dice_value(dice_str)
        limit_max = _max_dice_value(max_dice_str)
        return actual_max <= limit_max
    except (ValueError, IndexError):
        return True  # Can't parse, allow it


def _max_dice_value(dice_str: str) -> int:
    """Calculate the maximum possible value of a dice expression like '3d8' or '2d6+4'."""
    parts = dice_str.lower().split("+")
    dice_part = parts[0].strip()
    bonus = int(parts[1].strip()) if len(parts) > 1 else 0

    num, size = dice_part.split("d")
    return int(num) * int(size) + bonus
