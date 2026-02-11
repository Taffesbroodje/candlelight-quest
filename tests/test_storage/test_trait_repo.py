"""Tests for TraitRepo — CRUD operations for traits and behavior events."""
from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from text_rpg.storage.database import Database
from text_rpg.storage.repos.trait_repo import TraitRepo


@pytest.fixture
def db(tmp_path):
    """Create an in-memory database with the traits schema."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    database.initialize()
    return database


@pytest.fixture
def repo(db):
    """Create trait repo with prerequisite game rows for FK constraints."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        for gid in ("g1", "g2"):
            conn.execute(
                "INSERT INTO games (id, name, created_at, turn_number, "
                "current_location_id, character_id, is_active) "
                "VALUES (?, ?, ?, 0, 'loc1', 'c1', 1)",
                (gid, f"Test Game {gid}", now),
            )
    return TraitRepo(db)


class TestTraitCRUD:
    """Test trait save and retrieval."""

    def test_save_and_get_traits(self, repo):
        trait = {
            "id": str(uuid.uuid4()),
            "game_id": "g1",
            "character_id": "c1",
            "tier": 1,
            "name": "Flame-Touched",
            "description": "Fire awakens within.",
            "effects": [{"type": "damage_bonus_d4", "params": {"element": "fire"}}],
            "behavior_source": "fire_affinity",
            "acquired_turn": 15,
        }
        repo.save_trait(trait)

        traits = repo.get_traits("g1", "c1")
        assert len(traits) == 1
        assert traits[0]["name"] == "Flame-Touched"
        assert traits[0]["tier"] == 1
        assert isinstance(traits[0]["effects"], list)
        assert traits[0]["effects"][0]["type"] == "damage_bonus_d4"

    def test_get_trait_by_tier(self, repo):
        for tier in (1, 2):
            repo.save_trait({
                "id": str(uuid.uuid4()),
                "game_id": "g1",
                "character_id": "c1",
                "tier": tier,
                "name": f"Trait {tier}",
                "description": "Test",
                "effects": [{"type": "speed_bonus", "params": {}}],
                "behavior_source": "explorer",
                "acquired_turn": tier * 10,
            })

        t1 = repo.get_trait_by_tier("g1", "c1", 1)
        t2 = repo.get_trait_by_tier("g1", "c1", 2)
        t3 = repo.get_trait_by_tier("g1", "c1", 3)

        assert t1 is not None
        assert t1["name"] == "Trait 1"
        assert t2 is not None
        assert t2["name"] == "Trait 2"
        assert t3 is None

    def test_empty_traits(self, repo):
        traits = repo.get_traits("g1", "c1")
        assert traits == []

    def test_different_games_isolated(self, repo):
        for gid in ("g1", "g2"):
            repo.save_trait({
                "id": str(uuid.uuid4()),
                "game_id": gid,
                "character_id": "c1",
                "tier": 1,
                "name": f"Trait for {gid}",
                "description": "Test",
                "effects": [],
                "behavior_source": "explorer",
                "acquired_turn": 10,
            })

        assert len(repo.get_traits("g1", "c1")) == 1
        assert len(repo.get_traits("g2", "c1")) == 1


class TestBehaviorCounts:
    """Test behavior event counting."""

    def test_update_and_get(self, repo):
        repo.update_behavior_count("g1", "c1", "fire_affinity", 5, 10)
        repo.update_behavior_count("g1", "c1", "explorer", 12, 10)

        counts = repo.get_behavior_counts("g1", "c1")
        assert counts["fire_affinity"] == 5
        assert counts["explorer"] == 12

    def test_upsert_overwrites(self, repo):
        repo.update_behavior_count("g1", "c1", "fire_affinity", 5, 10)
        repo.update_behavior_count("g1", "c1", "fire_affinity", 15, 20)

        counts = repo.get_behavior_counts("g1", "c1")
        assert counts["fire_affinity"] == 15

    def test_empty_counts(self, repo):
        counts = repo.get_behavior_counts("g1", "c1")
        assert counts == {}

    def test_different_characters_isolated(self, repo):
        repo.update_behavior_count("g1", "c1", "explorer", 10, 5)
        repo.update_behavior_count("g1", "c2", "explorer", 20, 5)

        assert repo.get_behavior_counts("g1", "c1")["explorer"] == 10
        assert repo.get_behavior_counts("g1", "c2")["explorer"] == 20


class TestCountTraitsByCategory:
    """Test counting traits per behavior_source category."""

    def test_empty(self, repo):
        assert repo.count_traits_by_category("g1", "c1") == {}

    def test_counts_per_category(self, repo):
        for i, src in enumerate(["explorer", "explorer", "fire_affinity"]):
            repo.save_trait({
                "id": str(uuid.uuid4()),
                "game_id": "g1",
                "character_id": "c1",
                "tier": i + 1,
                "name": f"Trait {i}",
                "description": "Test",
                "effects": [],
                "behavior_source": src,
                "acquired_turn": i * 10,
            })
        counts = repo.count_traits_by_category("g1", "c1")
        assert counts["explorer"] == 2
        assert counts["fire_affinity"] == 1

    def test_different_games_isolated(self, repo):
        for gid in ("g1", "g2"):
            repo.save_trait({
                "id": str(uuid.uuid4()),
                "game_id": gid,
                "character_id": "c1",
                "tier": 1,
                "name": "Test",
                "description": "Test",
                "effects": [],
                "behavior_source": "explorer",
                "acquired_turn": 10,
            })
        assert repo.count_traits_by_category("g1", "c1")["explorer"] == 1
        assert repo.count_traits_by_category("g2", "c1")["explorer"] == 1


class TestDeleteAll:
    """Test cascade delete."""

    def test_delete_all_removes_traits_and_counts(self, repo):
        repo.save_trait({
            "id": str(uuid.uuid4()),
            "game_id": "g1",
            "character_id": "c1",
            "tier": 1,
            "name": "Test",
            "description": "Test",
            "effects": [],
            "behavior_source": "explorer",
            "acquired_turn": 10,
        })
        repo.update_behavior_count("g1", "c1", "explorer", 10, 5)

        repo.delete_all("g1")

        assert repo.get_traits("g1", "c1") == []
        assert repo.get_behavior_counts("g1", "c1") == {}

    def test_delete_only_affects_target_game(self, repo):
        for gid in ("g1", "g2"):
            repo.save_trait({
                "id": str(uuid.uuid4()),
                "game_id": gid,
                "character_id": "c1",
                "tier": 1,
                "name": f"Trait {gid}",
                "description": "Test",
                "effects": [],
                "behavior_source": "explorer",
                "acquired_turn": 10,
            })

        repo.delete_all("g1")
        assert repo.get_traits("g1", "c1") == []
        assert len(repo.get_traits("g2", "c1")) == 1
