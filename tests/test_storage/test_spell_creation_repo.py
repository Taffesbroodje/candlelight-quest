"""Tests for src/text_rpg/storage/repos/spell_creation_repo.py."""
from __future__ import annotations

import pytest

from text_rpg.storage.repos.spell_creation_repo import SpellCreationRepo


@pytest.fixture
def setup_game(in_memory_db):
    """Insert required game row for foreign key constraints."""
    with in_memory_db.get_connection() as conn:
        conn.execute(
            "INSERT INTO games (id, name, created_at) VALUES (?, ?, ?)",
            ("test-game", "Test Game", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO games (id, name, created_at) VALUES (?, ?, ?)",
            ("other-game", "Other Game", "2024-01-01T00:00:00Z"),
        )
    return in_memory_db


@pytest.fixture
def repo(setup_game):
    """Create SpellCreationRepo with initialized database."""
    return SpellCreationRepo(setup_game)


def _make_spell_data(
    spell_id: str = "test_spell_1",
    game_id: str = "test-game",
    char_id: str = "char-1",
    turn: int = 10,
    **overrides,
) -> dict:
    """Helper to create spell data dict with sane defaults."""
    base = {
        "id": spell_id,
        "game_id": game_id,
        "character_id": char_id,
        "name": "Frost Nova",
        "level": 2,
        "school": "evocation",
        "description": "A burst of freezing energy",
        "mechanics": {"type": "save", "damage_dice": "3d6", "damage_type": "cold"},
        "elements": ["cold", "wind"],
        "plausibility": 0.7,
        "creation_dc": 15,
        "created_turn": turn,
        "location_id": "library_01",
    }
    base.update(overrides)
    return base


class TestDiscoveredCombinations:
    """Tests for discovered combinations tracking."""

    def test_discover_then_get_returns_it(self, repo):
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        discovered = repo.get_discovered_combinations("test-game", "char-1")
        assert discovered == ["fire+ice"]

    def test_has_discovered_returns_true_after_discovering(self, repo):
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        assert repo.has_discovered("test-game", "char-1", "fire+ice") is True

    def test_has_discovered_returns_false_for_unknown(self, repo):
        assert repo.has_discovered("test-game", "char-1", "unknown") is False

    def test_multiple_discoveries_same_character(self, repo):
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        repo.discover_combination("test-game", "char-1", "lightning+water", 10)
        repo.discover_combination("test-game", "char-1", "earth+air", 15)
        discovered = repo.get_discovered_combinations("test-game", "char-1")
        assert len(discovered) == 3
        assert "fire+ice" in discovered
        assert "lightning+water" in discovered
        assert "earth+air" in discovered

    def test_duplicate_discovery_no_error(self, repo):
        """INSERT OR IGNORE prevents duplicate errors."""
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        repo.discover_combination("test-game", "char-1", "fire+ice", 10)
        discovered = repo.get_discovered_combinations("test-game", "char-1")
        assert discovered == ["fire+ice"]

    def test_different_characters_separate_discoveries(self, repo):
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        repo.discover_combination("test-game", "char-2", "lightning+water", 8)

        char1_discoveries = repo.get_discovered_combinations("test-game", "char-1")
        char2_discoveries = repo.get_discovered_combinations("test-game", "char-2")

        assert char1_discoveries == ["fire+ice"]
        assert char2_discoveries == ["lightning+water"]

    def test_get_discovered_empty_for_new_character(self, repo):
        discovered = repo.get_discovered_combinations("test-game", "new-char")
        assert discovered == []


class TestCustomSpells:
    """Tests for custom spell storage and retrieval."""

    def test_save_and_get_custom_spells(self, repo):
        spell = _make_spell_data()
        repo.save_custom_spell(spell)

        spells = repo.get_custom_spells("test-game", "char-1")
        assert len(spells) == 1
        assert spells[0]["name"] == "Frost Nova"

    def test_get_custom_spell_by_id_deserializes_json(self, repo):
        spell = _make_spell_data()
        repo.save_custom_spell(spell)

        retrieved = repo.get_custom_spell("test_spell_1")
        assert retrieved is not None
        assert retrieved["name"] == "Frost Nova"
        # Check JSON fields are deserialized
        assert isinstance(retrieved["mechanics"], dict)
        assert retrieved["mechanics"]["damage_type"] == "cold"
        assert isinstance(retrieved["elements"], list)
        assert "cold" in retrieved["elements"]

    def test_get_custom_spell_nonexistent_returns_none(self, repo):
        result = repo.get_custom_spell("nonexistent_id")
        assert result is None

    def test_multiple_spells_returned_in_turn_order(self, repo):
        spell1 = _make_spell_data(spell_id="spell1", turn=20)
        spell2 = _make_spell_data(spell_id="spell2", turn=10, name="Lightning Bolt")
        spell3 = _make_spell_data(spell_id="spell3", turn=15, name="Ice Lance")

        repo.save_custom_spell(spell1)
        repo.save_custom_spell(spell2)
        repo.save_custom_spell(spell3)

        spells = repo.get_custom_spells("test-game", "char-1")
        assert len(spells) == 3
        # Should be ordered by created_turn
        assert spells[0]["name"] == "Lightning Bolt"  # turn 10
        assert spells[1]["name"] == "Ice Lance"       # turn 15
        assert spells[2]["name"] == "Frost Nova"      # turn 20

    def test_custom_spell_all_fields_round_trip(self, repo):
        """Verify all fields survive save/load cycle."""
        spell = _make_spell_data(
            spell_id="complete_spell",
            name="Arcane Tempest",
            level=3,
            school="conjuration",
            description="A whirling storm of arcane energy",
            mechanics={"type": "attack", "hit_bonus": 5, "damage": "4d8"},
            elements=["arcane", "wind", "lightning"],
            plausibility=0.85,
            creation_dc=18,
            created_turn=25,
            location_id="tower_lab",
        )
        repo.save_custom_spell(spell)

        retrieved = repo.get_custom_spell("complete_spell")
        assert retrieved["id"] == "complete_spell"
        assert retrieved["game_id"] == "test-game"
        assert retrieved["character_id"] == "char-1"
        assert retrieved["name"] == "Arcane Tempest"
        assert retrieved["level"] == 3
        assert retrieved["school"] == "conjuration"
        assert retrieved["description"] == "A whirling storm of arcane energy"
        assert retrieved["mechanics"]["hit_bonus"] == 5
        assert len(retrieved["elements"]) == 3
        assert retrieved["plausibility"] == 0.85
        assert retrieved["creation_dc"] == 18
        assert retrieved["created_turn"] == 25
        assert retrieved["location_id"] == "tower_lab"


class TestDeleteAll:
    """Tests for cascade deletion."""

    def test_delete_all_removes_combinations_and_spells(self, repo):
        # Create combinations
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        repo.discover_combination("test-game", "char-1", "lightning+water", 10)

        # Create spells
        repo.save_custom_spell(_make_spell_data(spell_id="spell1"))
        repo.save_custom_spell(_make_spell_data(spell_id="spell2"))

        # Verify they exist
        assert len(repo.get_discovered_combinations("test-game", "char-1")) == 2
        assert len(repo.get_custom_spells("test-game", "char-1")) == 2

        # Delete all
        repo.delete_all("test-game")

        # Verify removed
        assert repo.get_discovered_combinations("test-game", "char-1") == []
        assert repo.get_custom_spells("test-game", "char-1") == []

    def test_delete_all_wrong_game_preserves_other_games(self, repo):
        # Create data in test-game
        repo.discover_combination("test-game", "char-1", "fire+ice", 5)
        repo.save_custom_spell(_make_spell_data(game_id="test-game", spell_id="spell1"))

        # Create data in other-game
        repo.discover_combination("other-game", "char-2", "lightning+water", 8)
        repo.save_custom_spell(_make_spell_data(
            game_id="other-game",
            char_id="char-2",
            spell_id="spell2",
        ))

        # Delete only test-game
        repo.delete_all("test-game")

        # test-game should be empty
        assert repo.get_discovered_combinations("test-game", "char-1") == []
        assert repo.get_custom_spells("test-game", "char-1") == []

        # other-game should still have data
        assert len(repo.get_discovered_combinations("other-game", "char-2")) == 1
        assert len(repo.get_custom_spells("other-game", "char-2")) == 1
