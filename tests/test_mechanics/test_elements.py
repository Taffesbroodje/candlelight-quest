"""Tests for text_rpg.mechanics.elements module.

Tests damage type enum, effective damage calculation, elemental compatibility,
and combination affinity scoring.
"""
import pytest

from text_rpg.mechanics.elements import (
    DamageType,
    ELEMENTAL_AFFINITIES,
    ELEMENTAL_OPPOSITIONS,
    are_elements_compatible,
    get_combination_affinity,
    get_effective_damage,
)


class TestDamageType:
    """Test the DamageType enum."""

    def test_all_damage_types_exist(self):
        """All 16 damage types are defined."""
        expected = {
            "fire", "cold", "lightning", "thunder", "acid", "poison",
            "radiant", "necrotic", "force", "psychic", "water", "earth",
            "wind", "bludgeoning", "piercing", "slashing"
        }
        actual = {dt.value for dt in DamageType}
        assert actual == expected

    def test_damage_type_string_equality(self):
        """DamageType enum members compare equal to their string values."""
        assert DamageType.FIRE == "fire"
        assert DamageType.COLD == "cold"
        assert DamageType.LIGHTNING == "lightning"

    def test_damage_type_case_sensitive(self):
        """DamageType values are lowercase strings."""
        assert DamageType.FIRE.value == "fire"
        assert DamageType.BLUDGEONING.value == "bludgeoning"


class TestGetEffectiveDamage:
    """Test effective damage calculation with resistances/vulnerabilities/immunities."""

    # Normal damage (no modifiers)
    @pytest.mark.parametrize("base_damage,damage_type", [
        (20, "fire"),
        (10, "cold"),
        (100, "lightning"),
        (5, "bludgeoning"),
        (0, "fire"),
    ])
    def test_normal_damage_no_modifiers(self, base_damage, damage_type):
        """Base damage returned when no modifiers apply."""
        damage, label = get_effective_damage(base_damage, damage_type, [], [], [])
        assert damage == base_damage
        assert label == "normal"

    # Resistance
    @pytest.mark.parametrize("base_damage,expected_damage", [
        (20, 10),
        (21, 10),  # 21 // 2 = 10 (floor division)
        (1, 0),    # 1 // 2 = 0
        (0, 0),
        (100, 50),
        (99, 49),
    ])
    def test_resistance_halves_damage(self, base_damage, expected_damage):
        """Resistance applies floor division by 2."""
        damage, label = get_effective_damage(base_damage, "fire", ["fire"], [], [])
        assert damage == expected_damage
        assert label == "resistant"

    # Vulnerability
    @pytest.mark.parametrize("base_damage,expected_damage", [
        (20, 40),
        (10, 20),
        (1, 2),
        (0, 0),
        (100, 200),
        (50, 100),
    ])
    def test_vulnerability_doubles_damage(self, base_damage, expected_damage):
        """Vulnerability doubles damage."""
        damage, label = get_effective_damage(base_damage, "fire", [], ["fire"], [])
        assert damage == expected_damage
        assert label == "vulnerable"

    # Immunity
    @pytest.mark.parametrize("base_damage", [0, 1, 20, 100, 9999])
    def test_immunity_negates_all_damage(self, base_damage):
        """Immunity always results in 0 damage."""
        damage, label = get_effective_damage(base_damage, "fire", [], [], ["fire"])
        assert damage == 0
        assert label == "immune"

    # Resistance + Vulnerability cancel
    @pytest.mark.parametrize("base_damage", [20, 10, 100, 0])
    def test_resistance_and_vulnerability_cancel(self, base_damage):
        """Resistance and vulnerability cancel each other out."""
        damage, label = get_effective_damage(base_damage, "fire", ["fire"], ["fire"], [])
        assert damage == base_damage
        assert label == "normal"

    # Immunity overrides all
    def test_immunity_overrides_resistance_and_vulnerability(self):
        """Immunity takes precedence over resistance and vulnerability."""
        damage, label = get_effective_damage(20, "fire", ["fire"], ["fire"], ["fire"])
        assert damage == 0
        assert label == "immune"

    def test_immunity_overrides_resistance(self):
        """Immunity takes precedence over resistance."""
        damage, label = get_effective_damage(20, "fire", ["fire"], [], ["fire"])
        assert damage == 0
        assert label == "immune"

    def test_immunity_overrides_vulnerability(self):
        """Immunity takes precedence over vulnerability."""
        damage, label = get_effective_damage(20, "fire", [], ["fire"], ["fire"])
        assert damage == 0
        assert label == "immune"

    # Case insensitivity
    @pytest.mark.parametrize("damage_type,modifiers", [
        ("Fire", ["fire"]),
        ("FIRE", ["fire"]),
        ("fire", ["FIRE"]),
        ("FiRe", ["FiRe"]),
    ])
    def test_case_insensitive_damage_type(self, damage_type, modifiers):
        """Damage type and modifier lists are case insensitive."""
        damage, label = get_effective_damage(20, damage_type, modifiers, [], [])
        assert damage == 10
        assert label == "resistant"

    # Different damage type not in lists
    def test_different_damage_type_not_affected(self):
        """Modifiers for other damage types don't affect calculation."""
        damage, label = get_effective_damage(20, "fire", ["cold"], [], [])
        assert damage == 20
        assert label == "normal"

    def test_fire_not_affected_by_cold_vulnerability(self):
        """Fire damage not affected by cold vulnerability."""
        damage, label = get_effective_damage(20, "fire", [], ["cold"], [])
        assert damage == 20
        assert label == "normal"

    def test_fire_not_affected_by_cold_immunity(self):
        """Fire damage not affected by cold immunity."""
        damage, label = get_effective_damage(20, "fire", [], [], ["cold"])
        assert damage == 20
        assert label == "normal"

    # Physical damage types
    @pytest.mark.parametrize("damage_type", ["bludgeoning", "piercing", "slashing"])
    def test_physical_damage_types(self, damage_type):
        """Physical damage types work correctly with resistance."""
        damage, label = get_effective_damage(20, damage_type, [damage_type], [], [])
        assert damage == 10
        assert label == "resistant"

    # Multiple resistances (only matching one matters)
    def test_multiple_resistances_one_matches(self):
        """Multiple resistances work when one matches."""
        damage, label = get_effective_damage(20, "fire", ["cold", "fire", "lightning"], [], [])
        assert damage == 10
        assert label == "resistant"

    def test_multiple_resistances_none_match(self):
        """Multiple resistances that don't match have no effect."""
        damage, label = get_effective_damage(20, "fire", ["cold", "lightning", "thunder"], [], [])
        assert damage == 20
        assert label == "normal"

    # Multiple vulnerabilities
    def test_multiple_vulnerabilities_one_matches(self):
        """Multiple vulnerabilities work when one matches."""
        damage, label = get_effective_damage(20, "fire", [], ["cold", "fire", "lightning"], [])
        assert damage == 40
        assert label == "vulnerable"

    # Multiple immunities
    def test_multiple_immunities_one_matches(self):
        """Multiple immunities work when one matches."""
        damage, label = get_effective_damage(20, "fire", [], [], ["cold", "fire", "lightning"])
        assert damage == 0
        assert label == "immune"

    # All damage types
    @pytest.mark.parametrize("damage_type", [
        "fire", "cold", "lightning", "thunder", "acid", "poison",
        "radiant", "necrotic", "force", "psychic", "water", "earth",
        "wind", "bludgeoning", "piercing", "slashing"
    ])
    def test_all_damage_types_with_resistance(self, damage_type):
        """All 16 damage types work with resistance."""
        damage, label = get_effective_damage(20, damage_type, [damage_type], [], [])
        assert damage == 10
        assert label == "resistant"

    # Edge cases
    def test_empty_lists(self):
        """Empty modifier lists result in normal damage."""
        damage, label = get_effective_damage(20, "fire", [], [], [])
        assert damage == 20
        assert label == "normal"

    def test_zero_damage_with_vulnerability(self):
        """Zero damage remains zero even with vulnerability."""
        damage, label = get_effective_damage(0, "fire", [], ["fire"], [])
        assert damage == 0
        assert label == "vulnerable"

    def test_odd_damage_with_resistance(self):
        """Odd damage floors correctly with resistance."""
        damage, label = get_effective_damage(15, "fire", ["fire"], [], [])
        assert damage == 7
        assert label == "resistant"


class TestAreElementsCompatible:
    """Test elemental compatibility checks."""

    # Same element
    @pytest.mark.parametrize("element", [
        "fire", "cold", "lightning", "water", "earth", "wind",
        "acid", "thunder", "poison", "radiant", "necrotic", "psychic", "force"
    ])
    def test_same_element_always_compatible(self, element):
        """Same element is always compatible with itself."""
        assert are_elements_compatible(element, element) is True

    # Mutual affinity (both list each other)
    @pytest.mark.parametrize("element_a,element_b", [
        ("fire", "wind"),
        ("wind", "fire"),
        ("cold", "water"),
        ("water", "cold"),
        ("lightning", "water"),
        ("water", "lightning"),
        ("wind", "lightning"),
        ("lightning", "wind"),
        ("wind", "cold"),
        ("cold", "wind"),
        ("earth", "thunder"),
        ("thunder", "earth"),
        ("water", "acid"),
        ("acid", "water"),
        ("acid", "poison"),
        ("poison", "acid"),
        ("psychic", "force"),
        ("force", "psychic"),
    ])
    def test_mutual_affinity_compatible(self, element_a, element_b):
        """Elements with mutual affinity are compatible."""
        assert are_elements_compatible(element_a, element_b) is True

    # One-way affinity
    def test_one_way_affinity_fire_lightning(self):
        """Fire lists lightning, lightning lists wind (one-way from fire to lightning)."""
        # fire -> [wind, lightning], lightning -> [water, wind]
        # So fire->lightning is one-way
        assert are_elements_compatible("fire", "lightning") is True

    def test_one_way_affinity_water_earth(self):
        """Water lists earth, but earth doesn't list water."""
        # water -> [cold, earth, acid], earth -> [fire, thunder]
        assert are_elements_compatible("water", "earth") is True
        assert are_elements_compatible("earth", "water") is True  # Still compatible via water listing earth

    def test_one_way_affinity_earth_fire(self):
        """Earth lists fire, but fire doesn't list earth."""
        # earth -> [fire, thunder], fire -> [wind, lightning]
        assert are_elements_compatible("earth", "fire") is True
        assert are_elements_compatible("fire", "earth") is True

    def test_one_way_affinity_radiant_fire(self):
        """Radiant lists fire, but fire doesn't list radiant."""
        # radiant -> [fire], fire -> [wind, lightning]
        assert are_elements_compatible("radiant", "fire") is True
        assert are_elements_compatible("fire", "radiant") is True

    def test_one_way_affinity_necrotic_cold(self):
        """Necrotic lists cold, but cold doesn't list necrotic."""
        # necrotic -> [cold], cold -> [water, wind]
        assert are_elements_compatible("necrotic", "cold") is True
        assert are_elements_compatible("cold", "necrotic") is True

    def test_one_way_affinity_poison_wind(self):
        """Poison lists wind, wind doesn't list poison."""
        # poison -> [acid, wind], wind -> [fire, lightning, cold]
        assert are_elements_compatible("poison", "wind") is True
        assert are_elements_compatible("wind", "poison") is True

    def test_one_way_affinity_force_wind(self):
        """Force lists wind, wind doesn't list force."""
        # force -> [wind, psychic], wind -> [fire, lightning, cold]
        assert are_elements_compatible("force", "wind") is True
        assert are_elements_compatible("wind", "force") is True

    # No affinity
    def test_no_affinity_fire_psychic(self):
        """Fire and psychic have no affinity."""
        # fire -> [wind, lightning], psychic -> [force]
        assert are_elements_compatible("fire", "psychic") is False

    def test_no_affinity_radiant_thunder(self):
        """Radiant and thunder have no affinity."""
        # radiant -> [fire], thunder -> [earth, lightning]
        assert are_elements_compatible("radiant", "thunder") is False

    def test_no_affinity_bludgeoning_fire(self):
        """Physical damage types not in affinity tables."""
        # bludgeoning not in ELEMENTAL_AFFINITIES
        assert are_elements_compatible("bludgeoning", "fire") is False

    def test_no_affinity_slashing_piercing(self):
        """Physical damage types have no affinities."""
        assert are_elements_compatible("slashing", "piercing") is False

    # Opposed elements can still be incompatible if not in affinity list
    def test_opposed_elements_not_compatible(self):
        """Fire and cold are opposed and not compatible."""
        # fire -> [wind, lightning], cold -> [water, wind]
        # Neither lists the other
        assert are_elements_compatible("fire", "cold") is False

    def test_opposed_elements_lightning_earth(self):
        """Lightning and earth are opposed and not compatible."""
        # lightning -> [water, wind], earth -> [fire, thunder]
        assert are_elements_compatible("lightning", "earth") is False

    # Case insensitivity
    def test_case_insensitive_same(self):
        """Case insensitive comparison for same element."""
        assert are_elements_compatible("Fire", "fire") is True
        assert are_elements_compatible("FIRE", "fire") is True

    def test_case_insensitive_affinity(self):
        """Case insensitive comparison for affinity."""
        assert are_elements_compatible("Fire", "Wind") is True
        assert are_elements_compatible("COLD", "water") is True


class TestGetCombinationAffinity:
    """Test combination affinity scoring."""

    # Same element = 1.0
    @pytest.mark.parametrize("element", [
        "fire", "cold", "lightning", "water", "earth", "wind",
        "acid", "thunder", "poison", "radiant", "necrotic", "psychic", "force"
    ])
    def test_same_element_perfect_affinity(self, element):
        """Same element has perfect affinity score of 1.0."""
        assert get_combination_affinity(element, element) == 1.0

    # Opposed elements = 0.0
    @pytest.mark.parametrize("element_a,element_b", [
        ("fire", "cold"),
        ("cold", "fire"),
        ("lightning", "earth"),
        ("earth", "lightning"),
        ("water", "fire"),
        ("wind", "earth"),
        ("acid", "radiant"),
        ("radiant", "necrotic"),
        ("necrotic", "radiant"),
        ("poison", "radiant"),
        ("thunder", "psychic"),
        ("psychic", "thunder"),
    ])
    def test_opposed_elements_zero_affinity(self, element_a, element_b):
        """Opposed elements have 0.0 affinity."""
        assert get_combination_affinity(element_a, element_b) == 0.0

    def test_force_opposes_itself_but_same_returns_one(self):
        """Force opposes itself in ELEMENTAL_OPPOSITIONS, but same element check returns 1.0 first."""
        # force -> force in ELEMENTAL_OPPOSITIONS, but a == b returns 1.0
        assert get_combination_affinity("force", "force") == 1.0

    # Mutual affinity = 1.0
    @pytest.mark.parametrize("element_a,element_b", [
        ("fire", "wind"),
        ("wind", "fire"),
        ("cold", "water"),
        ("water", "cold"),
        ("wind", "lightning"),
        ("lightning", "wind"),
        ("wind", "cold"),
        ("cold", "wind"),
        ("earth", "thunder"),
        ("thunder", "earth"),
        ("water", "acid"),
        ("acid", "water"),
        ("acid", "poison"),
        ("poison", "acid"),
        ("psychic", "force"),
        ("force", "psychic"),
    ])
    def test_mutual_affinity_perfect_score(self, element_a, element_b):
        """Mutually affine elements have 1.0 score."""
        assert get_combination_affinity(element_a, element_b) == 1.0

    # One-way affinity = 0.7
    def test_one_way_affinity_fire_lightning(self):
        """Fire lists lightning (one-way) = 0.7."""
        # fire -> [wind, lightning], lightning -> [water, wind]
        assert get_combination_affinity("fire", "lightning") == 0.7
        assert get_combination_affinity("lightning", "fire") == 0.7

    def test_one_way_affinity_water_earth(self):
        """Water lists earth (one-way) = 0.7."""
        # water -> [cold, earth, acid], earth -> [fire, thunder]
        assert get_combination_affinity("water", "earth") == 0.7
        assert get_combination_affinity("earth", "water") == 0.7

    def test_one_way_affinity_earth_fire(self):
        """Earth lists fire (one-way) = 0.7."""
        # earth -> [fire, thunder], fire -> [wind, lightning]
        assert get_combination_affinity("earth", "fire") == 0.7
        assert get_combination_affinity("fire", "earth") == 0.7

    def test_one_way_affinity_thunder_lightning(self):
        """Thunder lists lightning (one-way) = 0.7."""
        # thunder -> [earth, lightning], lightning -> [water, wind]
        assert get_combination_affinity("thunder", "lightning") == 0.7
        assert get_combination_affinity("lightning", "thunder") == 0.7

    def test_one_way_affinity_lightning_water(self):
        """Lightning lists water, but water doesn't list lightning (one-way) = 0.7."""
        # lightning -> [water, wind], water -> [cold, earth, acid]
        assert get_combination_affinity("lightning", "water") == 0.7
        assert get_combination_affinity("water", "lightning") == 0.7

    def test_one_way_affinity_radiant_fire(self):
        """Radiant lists fire (one-way) = 0.7."""
        # radiant -> [fire], fire -> [wind, lightning]
        assert get_combination_affinity("radiant", "fire") == 0.7
        assert get_combination_affinity("fire", "radiant") == 0.7

    def test_one_way_affinity_necrotic_cold(self):
        """Necrotic lists cold (one-way) = 0.7."""
        # necrotic -> [cold], cold -> [water, wind]
        assert get_combination_affinity("necrotic", "cold") == 0.7
        assert get_combination_affinity("cold", "necrotic") == 0.7

    def test_one_way_affinity_poison_wind(self):
        """Poison lists wind (one-way) = 0.7."""
        # poison -> [acid, wind], wind -> [fire, lightning, cold]
        assert get_combination_affinity("poison", "wind") == 0.7
        assert get_combination_affinity("wind", "poison") == 0.7

    def test_one_way_affinity_force_wind(self):
        """Force lists wind (one-way) = 0.7."""
        # force -> [wind, psychic], wind -> [fire, lightning, cold]
        assert get_combination_affinity("force", "wind") == 0.7
        assert get_combination_affinity("wind", "force") == 0.7

    # Neutral (no affinity, no opposition) = 0.3
    def test_neutral_fire_poison(self):
        """Fire and poison are neutral = 0.3."""
        # fire -> [wind, lightning], poison -> [acid, wind]
        # Not opposed, no affinity
        assert get_combination_affinity("fire", "poison") == 0.3

    def test_neutral_cold_thunder(self):
        """Cold and thunder are neutral = 0.3."""
        # cold -> [water, wind], thunder -> [earth, lightning]
        assert get_combination_affinity("cold", "thunder") == 0.3

    def test_neutral_radiant_thunder(self):
        """Radiant and thunder are neutral = 0.3."""
        # radiant -> [fire], thunder -> [earth, lightning]
        assert get_combination_affinity("radiant", "thunder") == 0.3

    def test_neutral_water_poison(self):
        """Water and poison are neutral = 0.3."""
        # water -> [cold, earth, acid], poison -> [acid, wind]
        # Share acid in common, but neither lists the other
        assert get_combination_affinity("water", "poison") == 0.3

    # Case insensitivity
    def test_case_insensitive_same(self):
        """Case insensitive for same element."""
        assert get_combination_affinity("Fire", "fire") == 1.0
        assert get_combination_affinity("FIRE", "fire") == 1.0

    def test_case_insensitive_opposed(self):
        """Case insensitive for opposed elements."""
        assert get_combination_affinity("Fire", "Cold") == 0.0
        assert get_combination_affinity("FIRE", "cold") == 0.0

    def test_case_insensitive_mutual(self):
        """Case insensitive for mutual affinity."""
        assert get_combination_affinity("Fire", "Wind") == 1.0
        assert get_combination_affinity("COLD", "water") == 1.0

    def test_case_insensitive_one_way(self):
        """Case insensitive for one-way affinity."""
        assert get_combination_affinity("Earth", "Fire") == 0.7
        assert get_combination_affinity("THUNDER", "lightning") == 0.7

    # Edge cases with physical damage types (not in tables)
    def test_physical_type_neutral(self):
        """Physical damage types default to neutral."""
        # bludgeoning not in ELEMENTAL_OPPOSITIONS or ELEMENTAL_AFFINITIES
        assert get_combination_affinity("bludgeoning", "fire") == 0.3

    def test_two_physical_types_neutral(self):
        """Two physical types are neutral (not same)."""
        assert get_combination_affinity("slashing", "piercing") == 0.3

    def test_physical_type_same(self):
        """Same physical type = 1.0."""
        assert get_combination_affinity("bludgeoning", "bludgeoning") == 1.0
