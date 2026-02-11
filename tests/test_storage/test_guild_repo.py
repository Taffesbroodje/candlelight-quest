"""Tests for storage/repos/guild_repo.py."""
from __future__ import annotations

import pytest

from text_rpg.storage.repos.guild_repo import GuildRepo


@pytest.fixture
def setup_game(in_memory_db):
    """Insert required game row for foreign key constraints."""
    with in_memory_db.get_connection() as conn:
        conn.execute(
            "INSERT INTO games (id, name, created_at) VALUES (?, ?, ?)",
            ("test-game", "Test Game", "2024-01-01T00:00:00Z"),
        )
    return in_memory_db


@pytest.fixture
def repo(setup_game):
    return GuildRepo(setup_game)


GAME_ID = "test-game"
CHAR_ID = "char-1"


class TestGuildMembership:
    """Tests for guild membership CRUD."""

    def test_join_guild(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        memberships = repo.get_memberships(GAME_ID, CHAR_ID)
        assert len(memberships) == 1
        assert memberships[0]["guild_id"] == "smiths_guild"
        assert memberships[0]["rank"] == "initiate"

    def test_join_multiple_guilds(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        repo.join_guild(GAME_ID, CHAR_ID, "cooks_guild", 10)
        memberships = repo.get_memberships(GAME_ID, CHAR_ID)
        assert len(memberships) == 2

    def test_join_same_guild_is_idempotent(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 10)
        memberships = repo.get_memberships(GAME_ID, CHAR_ID)
        assert len(memberships) == 1

    def test_get_specific_membership(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        m = repo.get_membership(GAME_ID, CHAR_ID, "smiths_guild")
        assert m is not None
        assert m["rank"] == "initiate"

    def test_get_nonexistent_membership_returns_none(self, repo):
        m = repo.get_membership(GAME_ID, CHAR_ID, "no_guild")
        assert m is None

    def test_update_rank(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        repo.update_rank(GAME_ID, CHAR_ID, "smiths_guild", "journeyman")
        m = repo.get_membership(GAME_ID, CHAR_ID, "smiths_guild")
        assert m["rank"] == "journeyman"

    def test_set_primary(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5, is_primary=True)
        repo.join_guild(GAME_ID, CHAR_ID, "cooks_guild", 10)
        repo.set_primary(GAME_ID, CHAR_ID, "cooks_guild")

        smiths = repo.get_membership(GAME_ID, CHAR_ID, "smiths_guild")
        cooks = repo.get_membership(GAME_ID, CHAR_ID, "cooks_guild")
        assert smiths["is_primary"] == 0
        assert cooks["is_primary"] == 1

    def test_leave_guild(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        repo.leave_guild(GAME_ID, CHAR_ID, "smiths_guild")
        memberships = repo.get_memberships(GAME_ID, CHAR_ID)
        assert len(memberships) == 0

    def test_memberships_scoped_by_game(self, repo):
        """Memberships from different games don't bleed through."""
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        memberships = repo.get_memberships("other-game", CHAR_ID)
        assert len(memberships) == 0


class TestWorkOrders:
    """Tests for work order CRUD."""

    def _make_order(self, order_id="order-1", guild_id="smiths_guild", **overrides):
        base = {
            "id": order_id,
            "game_id": GAME_ID,
            "character_id": CHAR_ID,
            "guild_id": guild_id,
            "template_id": "craft_daggers",
            "order_type": "craft",
            "description": "Forge 3 daggers",
            "requirements": {"forge_dagger": 3},
            "progress": {},
            "reward_gold": 40,
            "reward_xp": 60,
            "reward_rep": 5,
            "accepted_turn": 10,
            "expires_turn": 110,
        }
        base.update(overrides)
        return base

    def test_accept_and_get_active_orders(self, repo):
        repo.accept_work_order(self._make_order())
        orders = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert len(orders) == 1
        assert orders[0]["template_id"] == "craft_daggers"
        assert orders[0]["requirements"] == {"forge_dagger": 3}
        assert orders[0]["progress"] == {}

    def test_get_active_orders_for_guild(self, repo):
        repo.accept_work_order(self._make_order("o1", "smiths_guild"))
        repo.accept_work_order(self._make_order("o2", "cooks_guild", template_id="cook_rations"))
        smiths = repo.get_active_orders_for_guild(GAME_ID, CHAR_ID, "smiths_guild")
        cooks = repo.get_active_orders_for_guild(GAME_ID, CHAR_ID, "cooks_guild")
        assert len(smiths) == 1
        assert len(cooks) == 1

    def test_update_order_progress(self, repo):
        repo.accept_work_order(self._make_order())
        orders = repo.get_active_orders(GAME_ID, CHAR_ID)
        order_id = orders[0]["id"]

        repo.update_order_progress(order_id, {"forge_dagger": 2})
        updated = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert updated[0]["progress"] == {"forge_dagger": 2}

    def test_complete_order(self, repo):
        repo.accept_work_order(self._make_order())
        orders = repo.get_active_orders(GAME_ID, CHAR_ID)
        order_id = orders[0]["id"]

        completed = repo.complete_order(order_id, GAME_ID, CHAR_ID, turn=20)
        assert completed is not None
        assert completed["reward_gold"] == 40

        # Should no longer be in active orders
        active = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert len(active) == 0

        # Should be in history
        count = repo.get_completed_count(GAME_ID, CHAR_ID, "smiths_guild")
        assert count == 1

    def test_complete_nonexistent_order_returns_none(self, repo):
        result = repo.complete_order("fake-id", GAME_ID, CHAR_ID, turn=20)
        assert result is None

    def test_abandon_order(self, repo):
        repo.accept_work_order(self._make_order())
        orders = repo.get_active_orders(GAME_ID, CHAR_ID)
        order_id = orders[0]["id"]

        success = repo.abandon_order(order_id)
        assert success is True

        # Should no longer be in active orders
        active = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert len(active) == 0

        # Should NOT be in completed history
        count = repo.get_completed_count(GAME_ID, CHAR_ID, "smiths_guild")
        assert count == 0

    def test_abandon_nonexistent_order(self, repo):
        success = repo.abandon_order("fake-id")
        assert success is False

    def test_delete_all(self, repo):
        repo.join_guild(GAME_ID, CHAR_ID, "smiths_guild", 5)
        repo.accept_work_order(self._make_order())

        repo.delete_all(GAME_ID)

        assert len(repo.get_memberships(GAME_ID, CHAR_ID)) == 0
        assert len(repo.get_active_orders(GAME_ID, CHAR_ID)) == 0

    def test_multiple_orders_tracking(self, repo):
        repo.accept_work_order(self._make_order("o1"))
        repo.accept_work_order(self._make_order("o2", template_id="gather_iron"))

        active = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert len(active) == 2

        repo.complete_order("o1", GAME_ID, CHAR_ID, turn=20)
        active = repo.get_active_orders(GAME_ID, CHAR_ID)
        assert len(active) == 1
        assert active[0]["id"] == "o2"
