from __future__ import annotations

import sqlite3

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    turn_number           INTEGER NOT NULL DEFAULT 0,
    current_location_id   TEXT,
    character_id          TEXT,
    is_active             BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS characters (
    id                          TEXT PRIMARY KEY,
    game_id                     TEXT NOT NULL REFERENCES games(id),
    name                        TEXT NOT NULL,
    race                        TEXT,
    char_class                  TEXT,
    level                       INTEGER NOT NULL DEFAULT 1,
    xp                          INTEGER NOT NULL DEFAULT 0,
    ability_scores              TEXT,
    hp_current                  INTEGER,
    hp_max                      INTEGER,
    hp_temp                     INTEGER NOT NULL DEFAULT 0,
    ac                          INTEGER,
    proficiency_bonus           INTEGER NOT NULL DEFAULT 2,
    skill_proficiencies         TEXT,
    saving_throw_proficiencies  TEXT,
    class_features              TEXT,
    equipped_weapon_id          TEXT,
    equipped_armor_id           TEXT,
    conditions                  TEXT,
    hit_dice_remaining          INTEGER,
    speed                       INTEGER NOT NULL DEFAULT 30
);

CREATE TABLE IF NOT EXISTS entities (
    id                TEXT PRIMARY KEY,
    game_id           TEXT NOT NULL REFERENCES games(id),
    name              TEXT NOT NULL,
    entity_type       TEXT,
    description       TEXT,
    ability_scores    TEXT,
    hp_current        INTEGER,
    hp_max            INTEGER,
    hp_temp           INTEGER NOT NULL DEFAULT 0,
    ac                INTEGER,
    speed             INTEGER,
    level             INTEGER,
    challenge_rating  REAL,
    attacks           TEXT,
    behaviors         TEXT,
    dialogue_tags     TEXT,
    location_id       TEXT,
    loot_table        TEXT,
    is_hostile        BOOLEAN NOT NULL DEFAULT 0,
    is_alive          BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS locations (
    id              TEXT PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(id),
    name            TEXT NOT NULL,
    region_id       TEXT,
    description     TEXT,
    location_type   TEXT,
    connections     TEXT,
    entities        TEXT,
    items           TEXT,
    visited         BOOLEAN NOT NULL DEFAULT 0,
    properties      TEXT
);

CREATE TABLE IF NOT EXISTS regions (
    id              TEXT PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(id),
    name            TEXT NOT NULL,
    description     TEXT,
    locations       TEXT,
    level_range_min INTEGER,
    level_range_max INTEGER,
    climate         TEXT,
    faction         TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id        TEXT PRIMARY KEY,
    game_id   TEXT NOT NULL REFERENCES games(id),
    owner_id  TEXT NOT NULL,
    items     TEXT
);

CREATE TABLE IF NOT EXISTS quests (
    id                TEXT PRIMARY KEY,
    game_id           TEXT NOT NULL REFERENCES games(id),
    name              TEXT NOT NULL,
    description       TEXT,
    quest_giver_id    TEXT,
    status            TEXT NOT NULL DEFAULT "active",
    objectives        TEXT,
    xp_reward         INTEGER NOT NULL DEFAULT 0,
    item_rewards      TEXT,
    gold_reward       INTEGER NOT NULL DEFAULT 0,
    level_requirement INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS combat_instances (
    id                  TEXT PRIMARY KEY,
    game_id             TEXT NOT NULL REFERENCES games(id),
    is_active           BOOLEAN NOT NULL DEFAULT 1,
    round_number        INTEGER NOT NULL DEFAULT 1,
    current_turn_index  INTEGER NOT NULL DEFAULT 0,
    combatants          TEXT,
    turn_order          TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id                  TEXT PRIMARY KEY,
    game_id             TEXT NOT NULL REFERENCES games(id),
    event_type          TEXT NOT NULL,
    turn_number         INTEGER NOT NULL,
    timestamp           TEXT NOT NULL,
    actor_id            TEXT,
    target_id           TEXT,
    location_id         TEXT,
    description         TEXT,
    mechanical_details  TEXT,
    is_canonical        BOOLEAN NOT NULL DEFAULT 1
);

CREATE TRIGGER IF NOT EXISTS prevent_event_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, "Events are immutable");
END;

CREATE TRIGGER IF NOT EXISTS prevent_event_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, "Events are immutable");
END;

CREATE TABLE IF NOT EXISTS canon_entries (
    id              TEXT PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(id),
    timestamp       TEXT NOT NULL,
    description     TEXT,
    changes         TEXT,
    previous_hash   TEXT,
    entry_hash      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intents (
    id          TEXT PRIMARY KEY,
    game_id     TEXT NOT NULL REFERENCES games(id),
    intent_type TEXT NOT NULL,
    description TEXT,
    data        TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Execute the initial schema migration."""
    conn.executescript(_SCHEMA_SQL)
