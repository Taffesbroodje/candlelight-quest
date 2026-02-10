"""Tests for src/text_rpg/storage/database.py."""
from __future__ import annotations

import sqlite3

import pytest

from text_rpg.storage.database import Database, _MIGRATIONS


class TestDatabaseInitialize:
    def test_schema_version_table_exists(self, in_memory_db):
        with in_memory_db.get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchall()
            assert len(rows) == 1

    def test_all_migrations_applied(self, in_memory_db):
        with in_memory_db.get_connection() as conn:
            versions = {
                r[0] for r in conn.execute("SELECT version FROM schema_version").fetchall()
            }
        assert versions == set(range(1, len(_MIGRATIONS) + 1))

    def test_idempotent_rerun(self, in_memory_db):
        # Running initialize again should not fail
        in_memory_db.initialize()
        with in_memory_db.get_connection() as conn:
            versions = conn.execute("SELECT count(*) FROM schema_version").fetchone()[0]
        assert versions == len(_MIGRATIONS)

    def test_key_tables_exist(self, in_memory_db):
        expected_tables = [
            "games", "characters", "locations", "entities",
            "events", "canon_entries", "snapshots",
        ]
        with in_memory_db.get_connection() as conn:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"


class TestGetConnection:
    def test_commits_on_success(self, in_memory_db):
        with in_memory_db.get_connection() as conn:
            conn.execute(
                "INSERT INTO games (id, name, created_at) VALUES ('g1', 'Test', '2024-01-01')"
            )
        with in_memory_db.get_connection() as conn:
            row = conn.execute("SELECT id FROM games WHERE id='g1'").fetchone()
        assert row is not None

    def test_rollback_on_error(self, in_memory_db):
        try:
            with in_memory_db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO games (id, name, created_at) VALUES ('g2', 'Rollback', '2024-01-01')"
                )
                raise ValueError("Intentional error")
        except ValueError:
            pass
        with in_memory_db.get_connection() as conn:
            row = conn.execute("SELECT id FROM games WHERE id='g2'").fetchone()
        assert row is None
