"""Trait effects — mechanical building blocks the LLM can combine.

Defines the menu of effects available for dynamic traits, their costs,
and validation/application logic. Pure functions, no I/O.
"""
from __future__ import annotations

from typing import Any


# The effect menu: each entry has a cost and required parameters.
TRAIT_EFFECTS: dict[str, dict[str, Any]] = {
    "damage_bonus_d4": {
        "cost": 2,
        "description": "+1d4 {element} damage on weapon attacks",
        "requires": ["element"],
    },
    "damage_bonus_d6": {
        "cost": 3,
        "description": "+1d6 {element} damage on weapon attacks",
        "requires": ["element"],
    },
    "damage_resistance": {
        "cost": 3,
        "description": "Resistance to {element} damage",
        "requires": ["element"],
    },
    "skill_bonus": {
        "cost": 1,
        "description": "+1 to {skill} checks",
        "requires": ["skill"],
    },
    "skill_advantage": {
        "cost": 2,
        "description": "Advantage on {skill} checks when {condition}",
        "requires": ["skill", "condition"],
    },
    "ac_bonus": {
        "cost": 2,
        "description": "+1 AC when {condition}",
        "requires": ["condition"],
    },
    "temp_hp_on_trigger": {
        "cost": 2,
        "description": "Gain 1d6 temp HP when {trigger}",
        "requires": ["trigger"],
    },
    "speed_bonus": {
        "cost": 1,
        "description": "+5 movement speed",
        "requires": [],
    },
    "ability_per_rest": {
        "cost": 3,
        "description": "Once per {rest_type} rest: {ability_description}",
        "requires": ["rest_type", "ability_description"],
    },
    "extra_spell_slot_1": {
        "cost": 3,
        "description": "1 extra level 1 spell slot",
        "requires": [],
    },
    "skill_proficiency": {
        "cost": 2,
        "description": "Gain proficiency in {skill}",
        "requires": ["skill"],
    },
    "condition_immunity": {
        "cost": 2,
        "description": "Immunity to {condition}",
        "requires": ["condition"],
    },
    "darkvision": {
        "cost": 1,
        "description": "Gain darkvision 30ft",
        "requires": [],
    },
    "save_bonus": {
        "cost": 2,
        "description": "+1 to {ability} saving throws",
        "requires": ["ability"],
    },
}

# Point budgets per trait tier.
TIER_BUDGETS: dict[int, int] = {1: 2, 2: 4, 3: 6}


def validate_trait(effects: list[dict], tier: int) -> tuple[bool, str]:
    """Validate that selected effects are real and within budget.

    Each effect dict should have:
      {"type": "damage_bonus_d4", "params": {"element": "fire"}}

    Returns (is_valid, error_message).
    """
    budget = TIER_BUDGETS.get(tier, 2)
    total_cost = 0

    if not effects:
        return False, "Trait must have at least one effect."

    for i, effect in enumerate(effects):
        effect_type = effect.get("type", "")
        if effect_type not in TRAIT_EFFECTS:
            return False, f"Unknown effect type: '{effect_type}'."

        template = TRAIT_EFFECTS[effect_type]
        total_cost += template["cost"]

        # Check required parameters
        params = effect.get("params", {})
        for req in template["requires"]:
            if req not in params or not params[req]:
                return False, f"Effect '{effect_type}' requires parameter '{req}'."

    if total_cost > budget:
        return False, f"Total cost {total_cost} exceeds tier {tier} budget of {budget}."

    return True, ""


def get_effect_cost(effect_type: str) -> int:
    """Return the point cost of an effect type, or 0 if unknown."""
    return TRAIT_EFFECTS.get(effect_type, {}).get("cost", 0)


def total_effect_cost(effects: list[dict]) -> int:
    """Calculate the total point cost of a list of effects."""
    return sum(get_effect_cost(e.get("type", "")) for e in effects)


def format_effect_description(effect: dict) -> str:
    """Render an effect's description with its parameters filled in."""
    effect_type = effect.get("type", "")
    template = TRAIT_EFFECTS.get(effect_type)
    if not template:
        return f"Unknown effect: {effect_type}"

    desc = template["description"]
    params = effect.get("params", {})
    for key, value in params.items():
        desc = desc.replace(f"{{{key}}}", str(value))
    return desc


def apply_trait_effects(character: dict, traits: list[dict]) -> dict:
    """Return a copy of character dict with passive trait effects applied.

    Applies: AC bonuses, speed bonuses, skill proficiencies.
    Active effects (damage bonuses, triggered abilities) are checked
    at resolution time in combat/skill systems.
    """
    char = dict(character)

    for trait in traits:
        effects = trait.get("effects", [])
        for effect in effects:
            etype = effect.get("type", "")
            params = effect.get("params", {})

            if etype == "speed_bonus":
                char["speed"] = char.get("speed", 30) + 5

            elif etype == "darkvision":
                props = char.get("properties", {}) or {}
                props["darkvision"] = max(props.get("darkvision", 0), 30)
                char["properties"] = props

            elif etype == "skill_proficiency":
                skill = params.get("skill", "")
                if skill:
                    profs = char.get("skill_proficiencies", [])
                    if isinstance(profs, str):
                        import json
                        profs = json.loads(profs) if profs else []
                    if skill not in profs:
                        profs = list(profs) + [skill]
                        char["skill_proficiencies"] = profs

            elif etype == "extra_spell_slot_1":
                slots_max = char.get("spell_slots_max", {}) or {}
                if isinstance(slots_max, str):
                    import json
                    slots_max = json.loads(slots_max) if slots_max else {}
                slots_max = dict(slots_max)
                slots_max["1"] = int(slots_max.get("1", 0)) + 1
                char["spell_slots_max"] = slots_max

    return char


# Curated fallback traits — used if LLM produces invalid output.
FALLBACK_TRAITS: dict[str, dict] = {
    "fire_affinity": {
        "name": "Flame-Touched",
        "description": "Your affinity for flame has awakened something primal within you.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "fire"}}],
    },
    "cold_affinity": {
        "name": "Frost-Kissed",
        "description": "The cold has seeped into your very being, offering its protection.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "cold"}}],
    },
    "lightning_affinity": {
        "name": "Storm-Charged",
        "description": "Static crackles across your skin, a gift from the tempest.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "lightning"}}],
    },
    "radiant_affinity": {
        "name": "Light-Blessed",
        "description": "A divine radiance flickers within you, burning the unholy.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "radiant"}}],
    },
    "necrotic_affinity": {
        "name": "Death-Touched",
        "description": "The boundary between life and death thins around you.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "necrotic"}}],
    },
    "melee_combat": {
        "name": "Battle-Hardened",
        "description": "Countless clashes have forged your body into a weapon.",
        "effects": [{"type": "ac_bonus", "params": {"condition": "in melee combat"}}],
    },
    "ranged_combat": {
        "name": "Eagle-Eyed",
        "description": "Your vision sharpens unnaturally at distance.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "perception"}}, {"type": "darkvision"}],
    },
    "spell_mastery": {
        "name": "Arcane Resonance",
        "description": "Magic flows more freely through your practiced hands.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "arcana"}}, {"type": "darkvision"}],
    },
    "healer": {
        "name": "Mending Hands",
        "description": "Your touch carries a warmth that knits flesh and mends bone.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "medicine"}}, {"type": "darkvision"}],
    },
    "stealth_operative": {
        "name": "Shadow-Walker",
        "description": "Shadows gather around you like old friends.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "stealth"}}, {"type": "speed_bonus"}],
    },
    "social_adept": {
        "name": "Silver Tongue",
        "description": "Your words carry an almost supernatural persuasiveness.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "persuasion"}}, {"type": "skill_bonus", "params": {"skill": "deception"}}],
    },
    "explorer": {
        "name": "Wayfinder",
        "description": "The road calls to you, and you always find your way.",
        "effects": [{"type": "speed_bonus"}, {"type": "skill_bonus", "params": {"skill": "survival"}}],
    },
    "resilience": {
        "name": "Unbreakable",
        "description": "Pain has become an old companion that no longer slows you.",
        "effects": [{"type": "temp_hp_on_trigger", "params": {"trigger": "taking damage"}}],
    },
    "protector": {
        "name": "Guardian's Resolve",
        "description": "When your allies are threatened, your resolve hardens.",
        "effects": [{"type": "ac_bonus", "params": {"condition": "ally within 5 feet"}}],
    },
    "crafter": {
        "name": "Master Artisan",
        "description": "Your hands shape materials with supernatural precision.",
        "effects": [{"type": "skill_proficiency", "params": {"skill": "crafting"}}],
    },
    "quest_achiever": {
        "name": "Destined",
        "description": "Fate seems to bend around you, ensuring your quests succeed.",
        "effects": [{"type": "save_bonus", "params": {"ability": "wisdom"}}],
    },
    "poison_affinity": {
        "name": "Venom-Blooded",
        "description": "Toxins course through you harmlessly, lending their power to your strikes.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "poison"}}],
    },
    "psychic_affinity": {
        "name": "Mind-Sharpened",
        "description": "Your thoughts cut like blades, honed by endless psychic exertion.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "psychic"}}],
    },
    "force_affinity": {
        "name": "Arcane-Forged",
        "description": "Pure magical force bends to your will with practiced ease.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "force"}}],
    },
    "thunder_affinity": {
        "name": "Thunder-Born",
        "description": "The boom of thunder echoes in your bones, amplifying your power.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "thunder"}}],
    },
    "acid_affinity": {
        "name": "Corrosion-Touched",
        "description": "Acid no longer frightens you — it answers to your command.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "acid"}}],
    },
    "water_affinity": {
        "name": "Tide-Caller",
        "description": "Water responds to your presence, rising and falling at your whim.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "water"}}],
    },
    "earth_affinity": {
        "name": "Stone-Rooted",
        "description": "The earth steadies you, lending the patience and power of mountains.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "earth"}}],
    },
    "wind_affinity": {
        "name": "Gale-Touched",
        "description": "The wind whispers secrets to you and hastens your movements.",
        "effects": [{"type": "damage_bonus_d4", "params": {"element": "wind"}}],
    },
    "spell_inventor": {
        "name": "Spell Weaver",
        "description": "Your talent for forging new spells from raw magic is unmatched.",
        "effects": [{"type": "skill_bonus", "params": {"skill": "arcana"}}],
    },
    "guild_worker": {
        "name": "Guild Veteran",
        "description": "Years of guild service have honed your professional expertise.",
        "effects": [{"type": "skill_proficiency", "params": {"skill": "crafting"}}],
    },
}
