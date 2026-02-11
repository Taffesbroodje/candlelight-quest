"""LLM-powered trait generator — creates dynamic traits from player behavior."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from text_rpg.llm.provider import LLMProvider
from text_rpg.mechanics.behavior_tracker import BEHAVIOR_CATEGORIES
from text_rpg.mechanics.trait_effects import (
    FALLBACK_TRAITS,
    TIER_BUDGETS,
    TRAIT_EFFECTS,
    validate_trait,
)
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "llm" / "prompts"
_jinja_env: Environment | None = None


def _get_jinja() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=False,
        )
    return _jinja_env


def _format_character(char: dict) -> str:
    scores = safe_json(char.get("ability_scores"), {})
    return (
        f"{char.get('name', 'Unknown')} — Level {char.get('level', 1)} "
        f"{char.get('race', '?')} {char.get('char_class', '?')}"
    )


def generate_trait(
    llm: LLMProvider,
    behavior_scores: dict[str, int],
    dominant_patterns: list[str],
    tier: int,
    character: dict,
    existing_traits: list[dict],
) -> dict | None:
    """Ask LLM to create a trait based on player behavior.

    Returns a validated trait dict or None on failure.
    Falls back to curated traits if LLM output is invalid.
    """
    budget = TIER_BUDGETS.get(tier, 2)
    primary_pattern = dominant_patterns[0] if dominant_patterns else "explorer"

    # Build pattern descriptions for the prompt
    pattern_descriptions = {
        cat: BEHAVIOR_CATEGORIES[cat]["description"]
        for cat in dominant_patterns
        if cat in BEHAVIOR_CATEGORIES
    }

    env = _get_jinja()
    template = env.get_template("trait_generation.j2")

    prompt = template.render(
        character_summary=_format_character(character),
        dominant_patterns=dominant_patterns,
        pattern_descriptions=pattern_descriptions,
        tier=tier,
        budget=budget,
        effects_menu=TRAIT_EFFECTS,
        existing_traits=existing_traits,
    )

    try:
        raw = llm.generate_structured(prompt, temperature=0.8, max_tokens=512)
    except Exception as e:
        logger.warning(f"Trait generation LLM call failed: {e}")
        return _fallback_trait(primary_pattern, tier)

    # Validate the LLM output
    name = raw.get("name", "").strip()
    description = raw.get("description", "").strip()
    effects = raw.get("effects", [])

    if not name or not description or not effects:
        logger.warning("Trait generation returned empty fields, using fallback")
        return _fallback_trait(primary_pattern, tier)

    is_valid, error = validate_trait(effects, tier)
    if not is_valid:
        logger.warning(f"Trait validation failed: {error}, using fallback")
        return _fallback_trait(primary_pattern, tier)

    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "effects": effects,
        "tier": tier,
        "behavior_source": primary_pattern,
    }


def _fallback_trait(pattern: str, tier: int) -> dict | None:
    """Return a curated fallback trait for a given behavior pattern."""
    fallback = FALLBACK_TRAITS.get(pattern)
    if not fallback:
        # Try the first available pattern
        fallback = next(iter(FALLBACK_TRAITS.values()), None)
    if not fallback:
        return None

    budget = TIER_BUDGETS.get(tier, 2)

    # The fallback may exceed budget for higher tiers — trim effects if needed
    effects = list(fallback.get("effects", []))
    is_valid, _ = validate_trait(effects, tier)
    if not is_valid:
        # Keep only effects that fit within budget
        trimmed = []
        remaining = budget
        for effect in effects:
            cost = TRAIT_EFFECTS.get(effect.get("type", ""), {}).get("cost", 99)
            if cost <= remaining:
                trimmed.append(effect)
                remaining -= cost
        effects = trimmed if trimmed else effects[:1]

    return {
        "id": str(uuid.uuid4()),
        "name": fallback["name"],
        "description": fallback.get("description", "A trait awakens within you."),
        "effects": effects,
        "tier": tier,
        "behavior_source": pattern,
    }
