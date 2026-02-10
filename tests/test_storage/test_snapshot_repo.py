"""Tests for src/text_rpg/storage/repos/snapshot_repo.py."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from text_rpg.storage.repos.snapshot_repo import SnapshotRepo


def _make_snapshot(game_id: str, turn: int, **overrides) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "game_id": game_id,
        "turn_number": turn,
        "world_time": turn * 10,
        "timestamp": datetime.now().isoformat(),
        "trigger": "manual",
        "location_id": "loc1",
        "player_state": json.dumps({"hp": 10}),
        "inventory_state": json.dumps({"items": []}),
        "world_state": json.dumps({}),
        "quest_state": json.dumps([]),
        "social_state": json.dumps({}),
    }
    base.update(overrides)
    return base


class TestSnapshotRepo:
    @pytest.fixture
    def repo(self, in_memory_db):
        return SnapshotRepo(in_memory_db)

    def test_create_and_get_latest(self, repo):
        snap = _make_snapshot("g1", 5)
        repo.create_snapshot(snap)
        latest = repo.get_latest("g1")
        assert latest is not None
        assert latest["turn_number"] == 5

    def test_highest_turn_returned(self, repo):
        repo.create_snapshot(_make_snapshot("g1", 3))
        repo.create_snapshot(_make_snapshot("g1", 7))
        repo.create_snapshot(_make_snapshot("g1", 5))
        latest = repo.get_latest("g1")
        assert latest["turn_number"] == 7

    def test_get_by_turn_exact(self, repo):
        repo.create_snapshot(_make_snapshot("g1", 5))
        repo.create_snapshot(_make_snapshot("g1", 10))
        snap = repo.get_by_turn("g1", 10)
        assert snap["turn_number"] == 10

    def test_get_by_turn_closest_before(self, repo):
        repo.create_snapshot(_make_snapshot("g1", 5))
        repo.create_snapshot(_make_snapshot("g1", 10))
        snap = repo.get_by_turn("g1", 8)
        assert snap["turn_number"] == 5

    def test_get_by_turn_none(self, repo):
        repo.create_snapshot(_make_snapshot("g1", 5))
        snap = repo.get_by_turn("g1", 2)
        assert snap is None

    def test_list_with_limit(self, repo):
        for i in range(5):
            repo.create_snapshot(_make_snapshot("g1", i))
        result = repo.list_snapshots("g1", limit=3)
        assert len(result) == 3

    def test_delete_old_keeps_recent(self, repo):
        for i in range(5):
            repo.create_snapshot(_make_snapshot("g1", i))
        repo.delete_old("g1", keep_count=2)
        remaining = repo.list_snapshots("g1", limit=10)
        assert len(remaining) == 2

    def test_delete_old_noop_under_limit(self, repo):
        repo.create_snapshot(_make_snapshot("g1", 1))
        repo.delete_old("g1", keep_count=5)
        remaining = repo.list_snapshots("g1", limit=10)
        assert len(remaining) == 1
