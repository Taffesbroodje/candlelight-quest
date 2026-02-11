"""
Tests for mechanics/spell_combinations.py
"""

import pytest
from src.text_rpg.mechanics.spell_combinations import (
    SpellCombination,
    SPELL_COMBINATIONS,
    find_combination,
    can_attempt_combination,
    calculate_combination_dc,
)


class TestSpellCombinationDataclass:
    """Tests for SpellCombination dataclass."""

    def test_frozen_dataclass(self):
        """SpellCombination should be frozen (immutable)."""
        combo = SPELL_COMBINATIONS["firestorm"]
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            combo.name = "Modified"

    def test_all_combinations_have_unique_ids(self):
        """All 15 spell combinations should have unique IDs."""
        ids = [combo.id for combo in SPELL_COMBINATIONS.values()]
        assert len(ids) == 15
        assert len(set(ids)) == 15, "Duplicate IDs found"

    def test_all_combinations_have_valid_fields(self):
        """All combinations should have non-empty required fields."""
        for combo_id, combo in SPELL_COMBINATIONS.items():
            assert combo.id == combo_id
            assert combo.name
            assert combo.element_a
            assert combo.element_b
            assert combo.result_element
            assert combo.result_spell_id
            assert combo.discovery_dc >= 5


class TestFindCombination:
    """Tests for find_combination() function."""

    def test_forward_order_firestorm(self):
        """Should find firestorm with fire+wind."""
        result = find_combination("fire", "wind")
        assert result is not None
        assert result.id == "firestorm"
        assert result.name == "Firestorm"
        assert result.result_element == "fire"

    def test_reverse_order_firestorm(self):
        """Should find firestorm with wind+fire (order-independent)."""
        result = find_combination("wind", "fire")
        assert result is not None
        assert result.id == "firestorm"
        assert result.name == "Firestorm"

    @pytest.mark.parametrize("element_a,element_b,expected_id", [
        ("fire", "wind", "firestorm"),
        ("water", "cold", "ice_lance"),
        ("water", "earth", "mud_pit"),
        ("lightning", "water", "chain_storm"),
        ("earth", "wind", "sandstorm"),
        ("acid", "water", "acid_rain"),
        ("fire", "cold", "frozen_flame"),
        ("thunder", "earth", "thunder_quake"),
        ("lightning", "wind", "blinding_storm"),
        ("poison", "wind", "poison_mist"),
        ("radiant", "fire", "radiant_blaze"),
        ("necrotic", "cold", "shadow_frost"),
        ("psychic", "earth", "psychic_quake"),
        ("force", "wind", "force_gale"),
        ("fire", "water", "steam_blast"),
    ])
    def test_all_combinations_found(self, element_a, element_b, expected_id):
        """Should find all 15 defined combinations."""
        result = find_combination(element_a, element_b)
        assert result is not None
        assert result.id == expected_id

    @pytest.mark.parametrize("element_a,element_b,expected_id", [
        ("wind", "fire", "firestorm"),
        ("cold", "water", "ice_lance"),
        ("earth", "water", "mud_pit"),
        ("water", "lightning", "chain_storm"),
        ("wind", "earth", "sandstorm"),
    ])
    def test_all_combinations_reverse_order(self, element_a, element_b, expected_id):
        """Should find combinations in reverse order (order-independent)."""
        result = find_combination(element_a, element_b)
        assert result is not None
        assert result.id == expected_id

    def test_no_match_fire_psychic(self):
        """Should return None for non-existent combination."""
        result = find_combination("fire", "psychic")
        assert result is None

    def test_no_match_same_element(self):
        """Should return None when both elements are the same."""
        result = find_combination("fire", "fire")
        assert result is None

    def test_no_match_invalid_elements(self):
        """Should return None for invalid element names."""
        result = find_combination("invalid", "also_invalid")
        assert result is None

    def test_no_match_empty_strings(self):
        """Should return None for empty element strings."""
        result = find_combination("", "")
        assert result is None


class TestCanAttemptCombination:
    """Tests for can_attempt_combination() function."""

    def test_both_elements_known(self):
        """Should return True when player knows spells of both elements."""
        known_spells = ["fire_bolt", "gust_slash"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is True
        assert message == ""

    def test_missing_element_a(self):
        """Should return False when player doesn't know element_a spell."""
        known_spells = ["gust_slash"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is False
        assert "fire" in message.lower()
        assert "don't know" in message.lower()

    def test_missing_element_b(self):
        """Should return False when player doesn't know element_b spell."""
        known_spells = ["fire_bolt"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is False
        assert "wind" in message.lower()
        assert "don't know" in message.lower()

    def test_neither_element_known(self):
        """Should return False when player knows neither element."""
        known_spells = []
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is False
        assert message != ""

    def test_multiple_spells_of_same_element(self):
        """Should work when player knows multiple spells of the same element."""
        known_spells = ["fire_bolt", "fireball", "gust_slash"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "fireball": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is True
        assert message == ""

    def test_known_spell_not_in_all_spells(self):
        """Should handle case where known spell isn't in all_spells dict."""
        known_spells = ["fire_bolt", "mysterious_spell"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "gust_slash": {"mechanics": {"damage_type": "wind"}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is False
        assert "wind" in message.lower()

    def test_spell_without_damage_type(self):
        """Should handle spells that don't have damage_type in mechanics."""
        known_spells = ["fire_bolt", "utility_spell"]
        all_spells = {
            "fire_bolt": {"mechanics": {"damage_type": "fire"}},
            "utility_spell": {"mechanics": {}},
        }
        can_attempt, message = can_attempt_combination(
            known_spells, all_spells, "fire", "wind"
        )
        assert can_attempt is False
        assert "wind" in message.lower()


class TestCalculateCombinationDC:
    """Tests for calculate_combination_dc() function."""

    def test_base_case_no_modifiers(self):
        """Base DC with no modifiers should return base_dc."""
        dc = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=0.0, location_bonus=0
        )
        assert dc == 14

    def test_with_affinity_one(self):
        """Affinity of 1.0 should reduce DC by 4."""
        dc = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=1.0, location_bonus=0
        )
        assert dc == 10  # 14 - int(1.0 * 4)

    def test_with_location_bonus_negative(self):
        """Negative location bonus should reduce DC (make it easier)."""
        dc = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=0.0, location_bonus=-8
        )
        assert dc == 6  # 14 + (-8)

    def test_with_location_bonus_positive(self):
        """Positive location bonus should increase DC (make it harder)."""
        dc = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=0.0, location_bonus=5
        )
        assert dc == 19  # 14 + 5

    def test_clamp_minimum(self):
        """DC should not go below 5."""
        dc = calculate_combination_dc(
            base_dc=5, arcana_modifier=0, affinity_score=1.0, location_bonus=-8
        )
        assert dc == 5  # Would be 1 without clamp

    def test_clamp_maximum(self):
        """DC should not exceed 40."""
        dc = calculate_combination_dc(
            base_dc=40, arcana_modifier=0, affinity_score=0.0, location_bonus=10
        )
        assert dc == 40  # Would be 50 without clamp

    @pytest.mark.parametrize("base_dc,affinity,location,expected", [
        (14, 0.5, 0, 12),   # 14 - int(0.5 * 4) = 14 - 2 = 12
        (14, 2.0, 0, 6),    # 14 - int(2.0 * 4) = 14 - 8 = 6
        (20, 1.5, -5, 9),   # 20 - int(1.5 * 4) + (-5) = 20 - 6 - 5 = 9
        (10, 0.25, 3, 12),  # 10 - int(0.25 * 4) + 3 = 10 - 1 + 3 = 12
        (15, 3.0, 10, 13),  # 15 - int(3.0 * 4) + 10 = 15 - 12 + 10 = 13
    ])
    def test_combined_modifiers(self, base_dc, affinity, location, expected):
        """Test various combinations of modifiers."""
        dc = calculate_combination_dc(
            base_dc=base_dc,
            arcana_modifier=0,
            affinity_score=affinity,
            location_bonus=location,
        )
        assert dc == expected

    def test_arcana_modifier_not_used(self):
        """Arcana modifier should not affect DC calculation (used in skill check)."""
        dc_low = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=0.0, location_bonus=0
        )
        dc_high = calculate_combination_dc(
            base_dc=14, arcana_modifier=10, affinity_score=0.0, location_bonus=0
        )
        assert dc_low == dc_high == 14

    def test_negative_affinity(self):
        """Negative affinity should increase DC."""
        dc = calculate_combination_dc(
            base_dc=14, arcana_modifier=0, affinity_score=-1.0, location_bonus=0
        )
        assert dc == 18  # 14 - int(-1.0 * 4) = 14 + 4

    def test_extreme_clamp_low(self):
        """Extreme negative modifiers should clamp to 5."""
        dc = calculate_combination_dc(
            base_dc=10, arcana_modifier=0, affinity_score=5.0, location_bonus=-50
        )
        assert dc == 5

    def test_extreme_clamp_high(self):
        """Extreme positive modifiers should clamp to 40."""
        dc = calculate_combination_dc(
            base_dc=30, arcana_modifier=0, affinity_score=-10.0, location_bonus=100
        )
        assert dc == 40
