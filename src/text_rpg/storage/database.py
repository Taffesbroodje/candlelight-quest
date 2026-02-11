from __future__ import annotations

import contextlib
import importlib
import pathlib
import sqlite3
from typing import Generator


_MIGRATIONS = [
    "001_initial",
    "002_director",
    "003_gold_equipment",
    "004_survival_needs",
    "005_trade_skills",
    "006_spellcasting",
    "007_reputation",
    "008_world_clock",
    "009_shops",
    "010_death_wounds",
    "011_companions",
    "012_multiclass_housing",
    "013_connections",
    "014_snapshots",
    "015_class_resources",
    "016_traits",
    "017_elements_spells",
    "018_guilds_professions",
    "019_origin_id",
    "020_size",
]


class Database:
    """Main database manager for the Text RPG storage layer."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        """Run migrations to create all tables, skipping already-applied ones."""
        conn = self._get_raw_connection()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY)"
        )
        applied = {
            r[0] for r in conn.execute("SELECT version FROM schema_version").fetchall()
        }
        for i, name in enumerate(_MIGRATIONS, 1):
            if i not in applied:
                mod = importlib.import_module(f"text_rpg.storage.migrations.{name}")
                mod.upgrade(conn)
                conn.execute("INSERT INTO schema_version VALUES (?)", (i,))
        conn.commit()

    def _get_raw_connection(self) -> sqlite3.Connection:
        """Return the shared connection, creating it if needed."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    @contextlib.contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields a database connection.

        Commits on success, rolls back on exception.
        """
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
