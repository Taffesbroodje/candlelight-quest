"""Shared fixtures for the Text RPG test suite."""
from __future__ import annotations

import random
from typing import Any

import pytest

from text_rpg.mechanics.character_creation import create_character


STANDARD_SCORES = {
    "strength": 15, "dexterity": 14, "constitution": 13,
    "intelligence": 12, "wisdom": 10, "charisma": 8,
}


@pytest.fixture
def sample_ability_scores() -> dict[str, int]:
    return dict(STANDARD_SCORES)


@pytest.fixture
def fighter_character() -> dict[str, Any]:
    return create_character(
        name="Thorin",
        race="dwarf",
        char_class="fighter",
        ability_scores=dict(STANDARD_SCORES),
        skill_choices=["athletics", "perception"],
        game_id="test-game-1",
        starting_gold=50,
    )


@pytest.fixture
def wizard_character() -> dict[str, Any]:
    return create_character(
        name="Elminster",
        race="elf",
        char_class="wizard",
        ability_scores=dict(STANDARD_SCORES),
        skill_choices=["arcana", "history"],
        game_id="test-game-1",
        starting_gold=30,
    )


@pytest.fixture
def sample_location() -> dict[str, Any]:
    return {
        "id": "thornfield_square",
        "name": "Thornfield Square",
        "description": "A bustling town square with a fountain at its center.",
        "location_type": "town",
        "connections": [
            {"direction": "north", "target_location_id": "thornfield_market", "description": "Market District"},
            {"direction": "south", "target_location_id": "thornfield_gate", "description": "South Gate"},
        ],
        "entities": ["merchant_01", "guard_01"],
        "items": [],
        "visited": True,
    }


@pytest.fixture
def sample_entities() -> list[dict[str, Any]]:
    return [
        {
            "entity_id": "merchant_01",
            "id": "merchant_01",
            "name": "Bram the Merchant",
            "description": "A portly trader with a keen eye for bargains.",
            "disposition": "friendly",
            "hp": {"current": 15, "max": 15},
        },
        {
            "entity_id": "goblin_01",
            "id": "goblin_01",
            "name": "Goblin Scout",
            "description": "A sneaky goblin with a rusty dagger.",
            "disposition": "hostile",
            "hp": {"current": 7, "max": 7},
        },
        {
            "entity_id": "guard_01",
            "id": "guard_01",
            "name": "Town Guard",
            "description": "A stoic guard keeping watch.",
            "disposition": "neutral",
            "hp": {"current": 20, "max": 20},
        },
    ]


@pytest.fixture
def game_context(fighter_character, sample_location, sample_entities):
    from text_rpg.systems.base import GameContext

    return GameContext(
        game_id="test-game-1",
        character=fighter_character,
        location=sample_location,
        entities=sample_entities,
        combat_state=None,
        inventory={"items": [{"item_id": "healing_potion", "quantity": 2}]},
        recent_events=[],
        turn_number=5,
        active_quests=[],
        world_time=480,
    )


@pytest.fixture
def in_memory_db(tmp_path):
    from text_rpg.storage.database import Database

    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def seeded_rng():
    state = random.getstate()
    random.seed(42)
    yield
    random.setstate(state)
