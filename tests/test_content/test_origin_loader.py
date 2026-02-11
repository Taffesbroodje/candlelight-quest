"""Tests for origin loading and filtering."""
from __future__ import annotations

import pytest

from text_rpg.content.loader import filter_origins, load_all_origins


class TestLoadAllOrigins:
    def test_returns_list(self):
        origins = load_all_origins()
        assert isinstance(origins, list)

    def test_origins_have_required_fields(self):
        origins = load_all_origins()
        assert len(origins) > 0, "Should load at least one origin"
        required_fields = [
            "id", "name", "category", "summary", "prologue",
            "ability_choices", "skill_proficiencies", "starting_equipment",
            "bonus_gold", "starting_region", "starting_location",
            "feature_name", "feature_description",
        ]
        for origin in origins:
            for field in required_fields:
                assert field in origin, f"Origin '{origin.get('id', '?')}' missing field '{field}'"

    def test_ability_choices_are_valid(self):
        valid_abilities = {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
        origins = load_all_origins()
        for origin in origins:
            choices = origin.get("ability_choices", [])
            assert len(choices) >= 2, f"Origin '{origin['id']}' has fewer than 2 ability choices"
            for choice in choices:
                assert choice in valid_abilities, f"Origin '{origin['id']}' has invalid ability choice '{choice}'"

    def test_skill_proficiencies_count(self):
        origins = load_all_origins()
        for origin in origins:
            skills = origin.get("skill_proficiencies", [])
            assert len(skills) == 2, f"Origin '{origin['id']}' should have exactly 2 skill proficiencies, got {len(skills)}"

    def test_unique_ids(self):
        origins = load_all_origins()
        ids = [o["id"] for o in origins]
        assert len(ids) == len(set(ids)), f"Duplicate origin IDs found: {[i for i in ids if ids.count(i) > 1]}"

    def test_category_set_from_filename(self):
        origins = load_all_origins()
        for origin in origins:
            assert "category" in origin
            assert origin["category"] != ""


class TestFilterOrigins:
    @pytest.fixture
    def sample_origins(self):
        return [
            {"id": "noble", "name": "Noble", "required_races": [], "excluded_races": [], "required_classes": [], "excluded_classes": []},
            {"id": "deep_miner", "name": "Deep Miner", "required_races": ["dwarf"], "excluded_races": [], "required_classes": [], "excluded_classes": []},
            {"id": "exiled_courtling", "name": "Exiled Courtling", "required_races": ["elf"], "excluded_races": [], "required_classes": [], "excluded_classes": []},
            {"id": "tournament_champion", "name": "Tournament Champion", "required_races": [], "excluded_races": [], "required_classes": ["fighter"], "excluded_classes": []},
            {"id": "academy_dropout", "name": "Academy Dropout", "required_races": [], "excluded_races": [], "required_classes": ["wizard"], "excluded_classes": []},
            {"id": "restricted", "name": "Restricted", "required_races": [], "excluded_races": ["human"], "required_classes": [], "excluded_classes": []},
        ]

    def test_universal_origins_available_to_all(self, sample_origins):
        result = filter_origins(sample_origins, "human", "fighter")
        ids = [o["id"] for o in result]
        assert "noble" in ids

    def test_race_specific_only_for_matching_race(self, sample_origins):
        dwarf_result = filter_origins(sample_origins, "dwarf", "fighter")
        human_result = filter_origins(sample_origins, "human", "fighter")
        dwarf_ids = [o["id"] for o in dwarf_result]
        human_ids = [o["id"] for o in human_result]
        assert "deep_miner" in dwarf_ids
        assert "deep_miner" not in human_ids

    def test_class_specific_only_for_matching_class(self, sample_origins):
        fighter_result = filter_origins(sample_origins, "human", "fighter")
        wizard_result = filter_origins(sample_origins, "human", "wizard")
        fighter_ids = [o["id"] for o in fighter_result]
        wizard_ids = [o["id"] for o in wizard_result]
        assert "tournament_champion" in fighter_ids
        assert "tournament_champion" not in wizard_ids
        assert "academy_dropout" in wizard_ids
        assert "academy_dropout" not in fighter_ids

    def test_excluded_race_filtered_out(self, sample_origins):
        human_result = filter_origins(sample_origins, "human", "fighter")
        elf_result = filter_origins(sample_origins, "elf", "fighter")
        human_ids = [o["id"] for o in human_result]
        elf_ids = [o["id"] for o in elf_result]
        assert "restricted" not in human_ids
        assert "restricted" in elf_ids

    def test_combined_race_and_class_filter(self, sample_origins):
        # Dwarf fighter should get: noble, deep_miner, tournament_champion, restricted
        result = filter_origins(sample_origins, "dwarf", "fighter")
        ids = [o["id"] for o in result]
        assert "noble" in ids
        assert "deep_miner" in ids
        assert "tournament_champion" in ids
        assert "exiled_courtling" not in ids
        assert "academy_dropout" not in ids
