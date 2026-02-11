"""Tests for behavior tracker — event pattern analysis."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.behavior_tracker import (
    BEHAVIOR_CATEGORIES,
    analyze_behavior,
    check_behavior_thresholds,
    get_dominant_patterns,
    is_eligible_for_trait,
    next_threshold,
    trait_tier_for_count,
    update_behavior_from_events,
)


class TestAnalyzeBehavior:
    """Tests for analyze_behavior function."""

    def test_empty_events(self):
        scores = analyze_behavior([], {})
        assert all(v == 0 for v in scores.values())
        assert len(scores) == len(BEHAVIOR_CATEGORIES)

    def test_spell_cast_increments_spell_mastery(self):
        events = [{"event_type": "SPELL_CAST", "description": "Cast fireball"}]
        scores = analyze_behavior(events, {})
        assert scores["spell_mastery"] == 1

    def test_fire_spell_increments_fire_affinity(self):
        events = [
            {"event_type": "SPELL_CAST", "description": "Cast fire bolt", "mechanical_details": {"damage_type": "fire"}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["fire_affinity"] == 1
        assert scores["spell_mastery"] == 1  # Also counts as spellcasting

    def test_attack_increments_melee(self):
        events = [
            {"event_type": "ATTACK", "description": "Melee attack", "mechanical_details": {"attack_style": "melee"}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["melee_combat"] == 1

    def test_move_increments_explorer(self):
        events = [{"event_type": "MOVE"}, {"event_type": "MOVE"}, {"event_type": "LOCATION_DISCOVER"}]
        scores = analyze_behavior(events, {})
        assert scores["explorer"] == 3

    def test_dialogue_increments_social_adept(self):
        events = [
            {"event_type": "DIALOGUE", "description": "persuasion check"},
        ]
        scores = analyze_behavior(events, {})
        assert scores["social_adept"] == 1

    def test_stealth_skill_check(self):
        events = [
            {"event_type": "SKILL_CHECK", "description": "stealth check to sneak past"},
        ]
        scores = analyze_behavior(events, {})
        assert scores["stealth_operative"] == 1

    def test_quest_complete(self):
        events = [{"event_type": "QUEST_COMPLETE"}] * 5
        scores = analyze_behavior(events, {})
        assert scores["quest_achiever"] == 5

    def test_multiple_categories(self):
        events = [
            {"event_type": "SPELL_CAST", "description": "Cast cold ray", "mechanical_details": {"damage_type": "cold"}},
            {"event_type": "HEAL", "description": "Healed 10 HP"},
            {"event_type": "CRAFT"},
        ]
        scores = analyze_behavior(events, {})
        assert scores["cold_affinity"] == 1
        assert scores["spell_mastery"] == 1
        assert scores["healer"] == 1
        assert scores["crafter"] == 1

    def test_filter_with_pipes(self):
        """Social adept has 'persuasion|deception|intimidation' filter."""
        events = [
            {"event_type": "SKILL_CHECK", "description": "intimidation check"},
        ]
        scores = analyze_behavior(events, {})
        assert scores["social_adept"] == 1

    def test_no_false_positives(self):
        """Events that don't match any filter shouldn't count."""
        events = [
            {"event_type": "ATTACK", "description": "Swings sword normally"},
        ]
        scores = analyze_behavior(events, {})
        # "fire" not in description, so fire_affinity should be 0
        assert scores["fire_affinity"] == 0
        # "melee" not in description either
        assert scores["melee_combat"] == 0

    def test_discovery_increments_explorer(self):
        """DISCOVERY events should also count for explorer."""
        events = [{"event_type": "DISCOVERY", "description": "Found a new path"}]
        scores = analyze_behavior(events, {})
        assert scores["explorer"] == 1

    def test_craft_success_increments_crafter(self):
        """CRAFT_SUCCESS is the actual event type from crafting system."""
        events = [{"event_type": "CRAFT_SUCCESS", "description": "Crafted a potion"}]
        scores = analyze_behavior(events, {})
        assert scores["crafter"] == 1

    def test_heal_needs_filter_match(self):
        """HEAL events now require 'heal' in description/details."""
        # Without heal keyword
        events = [{"event_type": "HEAL", "description": "something"}]
        scores = analyze_behavior(events, {})
        assert scores["healer"] == 0

        # With heal keyword
        events = [{"event_type": "HEAL", "description": "Healed 10 HP"}]
        scores = analyze_behavior(events, {})
        assert scores["healer"] == 1

    def test_spell_cast_healing_counts_as_healer(self):
        """Healing spells (SPELL_CAST with 'heal' in details) count for healer."""
        events = [
            {"event_type": "SPELL_CAST", "description": "Cast cure wounds", "mechanical_details": {"spell": "cure_wounds", "healed": 8}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["healer"] == 1
        assert scores["spell_mastery"] == 1  # Also counts as spellcasting

    def test_ranged_attack(self):
        events = [
            {"event_type": "ATTACK", "description": "Fires arrow", "mechanical_details": {"attack_style": "ranged"}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["ranged_combat"] == 1
        assert scores["melee_combat"] == 0

    def test_npc_attack_increments_resilience(self):
        """NPC attacks hitting the player count for resilience."""
        events = [
            {"event_type": "ATTACK", "description": "Goblin attacks", "mechanical_details": {"npc_attack": True, "damage": 5}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["resilience"] == 1

    def test_skill_check_persuasion_social_adept(self):
        events = [
            {"event_type": "SKILL_CHECK", "description": "persuasion check (DC 12)", "mechanical_details": {"skill": "persuasion"}},
        ]
        scores = analyze_behavior(events, {})
        assert scores["social_adept"] == 1


class TestGetDominantPatterns:
    """Tests for get_dominant_patterns function."""

    def test_empty_scores(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        assert get_dominant_patterns(scores) == []

    def test_one_dominant(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        scores["fire_affinity"] = 15
        result = get_dominant_patterns(scores)
        assert result == ["fire_affinity"]

    def test_sorted_by_score(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        scores["explorer"] = 20
        scores["spell_mastery"] = 15
        scores["melee_combat"] = 10
        result = get_dominant_patterns(scores)
        assert result == ["explorer", "spell_mastery", "melee_combat"]

    def test_custom_threshold(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        scores["fire_affinity"] = 7
        assert get_dominant_patterns(scores, threshold=5) == ["fire_affinity"]
        assert get_dominant_patterns(scores, threshold=10) == []

    def test_below_threshold_excluded(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        scores["explorer"] = 9
        assert get_dominant_patterns(scores) == []  # default threshold is 10

    def test_exactly_at_threshold(self):
        scores = {cat: 0 for cat in BEHAVIOR_CATEGORIES}
        scores["healer"] = 10
        assert get_dominant_patterns(scores) == ["healer"]


class TestNextThreshold:
    """Tests for next_threshold — progressive thresholds per category."""

    def test_first_threshold_is_10(self):
        assert next_threshold(0) == 10

    def test_second_threshold_is_25(self):
        assert next_threshold(1) == 25

    def test_third_threshold_is_50(self):
        assert next_threshold(2) == 50

    def test_fourth_threshold_is_100(self):
        assert next_threshold(3) == 100

    def test_fifth_threshold_is_200(self):
        assert next_threshold(4) == 200

    def test_sixth_threshold_is_400(self):
        assert next_threshold(5) == 400

    def test_thresholds_keep_doubling(self):
        assert next_threshold(6) == 800
        assert next_threshold(7) == 1600


class TestTraitTierForCount:
    """Tests for trait_tier_for_count — tier scales with traits earned."""

    def test_first_trait_tier_1(self):
        assert trait_tier_for_count(0) == 1

    def test_second_trait_tier_2(self):
        assert trait_tier_for_count(1) == 2

    def test_third_trait_tier_3(self):
        assert trait_tier_for_count(2) == 3

    def test_fourth_trait_still_tier_3(self):
        assert trait_tier_for_count(3) == 3

    def test_tenth_trait_still_tier_3(self):
        assert trait_tier_for_count(9) == 3


class TestCheckBehaviorThresholds:
    """Tests for check_behavior_thresholds — finds categories ready for traits."""

    def test_no_categories_ready(self):
        scores = {"explorer": 5, "healer": 3}
        traits_per_cat = {}
        assert check_behavior_thresholds(scores, traits_per_cat) == []

    def test_one_category_crosses_first_threshold(self):
        scores = {"explorer": 10, "healer": 3}
        traits_per_cat = {}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == [("explorer", 1)]

    def test_multiple_categories_ready(self):
        scores = {"explorer": 15, "melee_combat": 12}
        traits_per_cat = {}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert len(result) == 2
        # Sorted by score descending
        assert result[0] == ("explorer", 1)
        assert result[1] == ("melee_combat", 1)

    def test_second_trait_needs_25(self):
        scores = {"explorer": 20}
        traits_per_cat = {"explorer": 1}  # Already earned one
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == []  # 20 < 25

    def test_second_trait_at_25(self):
        scores = {"explorer": 25}
        traits_per_cat = {"explorer": 1}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == [("explorer", 2)]  # Tier 2 for second trait

    def test_third_trait_at_50(self):
        scores = {"fire_affinity": 50}
        traits_per_cat = {"fire_affinity": 2}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == [("fire_affinity", 3)]  # Tier 3

    def test_fourth_trait_needs_100(self):
        scores = {"fire_affinity": 80}
        traits_per_cat = {"fire_affinity": 3}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == []  # 80 < 100

    def test_fourth_trait_at_100_still_tier_3(self):
        scores = {"fire_affinity": 100}
        traits_per_cat = {"fire_affinity": 3}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == [("fire_affinity", 3)]  # Tier capped at 3

    def test_exactly_at_threshold(self):
        scores = {"crafter": 10}
        traits_per_cat = {}
        result = check_behavior_thresholds(scores, traits_per_cat)
        assert result == [("crafter", 1)]

    def test_below_threshold(self):
        scores = {"crafter": 9}
        traits_per_cat = {}
        assert check_behavior_thresholds(scores, traits_per_cat) == []


class TestIsEligibleForTraitLegacy:
    """Tests for legacy is_eligible_for_trait — always eligible."""

    def test_always_eligible(self):
        eligible, tier = is_eligible_for_trait(1, [])
        assert eligible
        assert tier == 1

    def test_tier_scales_with_count(self):
        existing = [{"tier": 1}]
        eligible, tier = is_eligible_for_trait(1, existing)
        assert eligible
        assert tier == 2

    def test_tier_caps_at_3(self):
        existing = [{"tier": 1}, {"tier": 2}, {"tier": 3}]
        eligible, tier = is_eligible_for_trait(1, existing)
        assert eligible
        assert tier == 3


class TestUpdateBehaviorFromEvents:
    """Tests for incremental behavior counter update."""

    def test_adds_to_existing_counts(self):
        current = {"explorer": 5, "spell_mastery": 3}
        new_events = [{"event_type": "MOVE"}, {"event_type": "SPELL_CAST"}]
        result = update_behavior_from_events(new_events, current)
        assert result["explorer"] == 6
        assert result["spell_mastery"] == 4

    def test_creates_new_categories(self):
        current = {}
        new_events = [{"event_type": "CRAFT"}]
        result = update_behavior_from_events(new_events, current)
        assert result["crafter"] == 1

    def test_empty_events_no_change(self):
        current = {"explorer": 5}
        result = update_behavior_from_events([], current)
        assert result["explorer"] == 5

    def test_preserves_unrelated_counts(self):
        current = {"healer": 10}
        new_events = [{"event_type": "MOVE"}]
        result = update_behavior_from_events(new_events, current)
        assert result["healer"] == 10

    def test_craft_success_incremental(self):
        current = {"crafter": 2}
        new_events = [{"event_type": "CRAFT_SUCCESS", "description": "Crafted potion"}]
        result = update_behavior_from_events(new_events, current)
        assert result["crafter"] == 3
