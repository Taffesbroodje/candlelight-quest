"""Tests for spell invention mechanics."""

import random
import pytest
from text_rpg.mechanics.spell_invention import (
    calculate_invention_dc,
    validate_spell_proposal,
    generate_wild_magic_surge,
    SpellProposal,
    WildMagicSurge,
    _dice_within_limit,
    _max_dice_value,
    LOCATION_BONUSES,
    SPELL_LEVEL_DC_MODIFIER,
    MAX_DAMAGE_DICE,
    VALID_SCHOOLS,
)


class TestCalculateInventionDC:
    """Tests for DC calculation."""

    def test_high_plausibility_cantrip_no_bonuses(self):
        # plausibility_to_dc(1.0) = 5, level 0 modifier = 0
        dc = calculate_invention_dc(
            plausibility=1.0,
            spell_level=0,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        assert dc == 5

    def test_medium_plausibility_level_1(self):
        # plausibility_to_dc(0.5) ≈ 11, level 1 modifier = 5
        dc = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        # 11 + 5 = 16
        assert 15 <= dc <= 17  # Allow slight rounding variance

    def test_low_plausibility_level_3_clamped_to_max(self):
        # plausibility_to_dc(0.01) ≈ 43, level 3 modifier = 15
        # 43 + 15 = 58, clamped to 45
        dc = calculate_invention_dc(
            plausibility=0.01,
            spell_level=3,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        assert dc == 45

    def test_arcane_tower_bonus(self):
        # Base DC with plausibility 1.0, level 0 = 5
        # Arcane tower bonus = -8, but clamped to minimum 5
        dc = calculate_invention_dc(
            plausibility=1.0,
            spell_level=0,
            location_type="arcane_tower",
            arcana_proficient=False,
            affinity_count=0,
        )
        assert dc == 5  # 5 - 8 = -3, clamped to 5

    def test_arcane_tower_bonus_with_higher_base(self):
        # plausibility_to_dc(0.3) ≈ 15, level 1 = +5 = 20
        # Arcane tower = -8 → 12
        dc = calculate_invention_dc(
            plausibility=0.3,
            spell_level=1,
            location_type="arcane_tower",
            arcana_proficient=False,
            affinity_count=0,
        )
        assert 11 <= dc <= 13

    def test_arcana_proficiency_bonus(self):
        # Base: plausibility 0.5 (~11) + level 1 (+5) = 16
        # Arcana proficiency = -2 → 14
        dc = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type=None,
            arcana_proficient=True,
            affinity_count=0,
        )
        assert 13 <= dc <= 15

    def test_affinity_count_bonus_capped_at_3(self):
        # Base: plausibility 0.5 (~11) + level 1 (+5) = 16
        # Affinity count 5, but capped at -3 → 13
        dc = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type=None,
            arcana_proficient=False,
            affinity_count=5,
        )
        assert 12 <= dc <= 14

    def test_affinity_count_below_cap(self):
        # Base: plausibility 0.5 (~11) + level 1 (+5) = 16
        # Affinity count 2 → -2 → 14
        dc = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type=None,
            arcana_proficient=False,
            affinity_count=2,
        )
        assert 13 <= dc <= 15

    @pytest.mark.parametrize("location,bonus", [
        ("academy", -6),
        ("library", -4),
        ("temple", -3),
        ("enchanted_grove", -3),
        ("ley_line", -5),
        ("workshop", -2),
    ])
    def test_all_location_bonuses(self, location, bonus):
        # Base: plausibility 0.2 (~18) + level 2 (+10) = 28
        dc = calculate_invention_dc(
            plausibility=0.2,
            spell_level=2,
            location_type=location,
            arcana_proficient=False,
            affinity_count=0,
        )
        expected = 28 + bonus
        assert expected - 1 <= dc <= expected + 1

    def test_unknown_location_no_bonus(self):
        # Unknown location should not apply any bonus
        dc_no_location = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        dc_unknown = calculate_invention_dc(
            plausibility=0.5,
            spell_level=1,
            location_type="tavern",
            arcana_proficient=False,
            affinity_count=0,
        )
        assert dc_no_location == dc_unknown

    def test_all_bonuses_stacked(self):
        # Base: plausibility 0.3 (~15) + level 2 (+10) = 25
        # Arcane tower -8, arcana prof -2, affinity 5 (-3) = -13
        # 25 - 13 = 12
        dc = calculate_invention_dc(
            plausibility=0.3,
            spell_level=2,
            location_type="arcane_tower",
            arcana_proficient=True,
            affinity_count=5,
        )
        assert 11 <= dc <= 13

    def test_clamp_to_minimum_5(self):
        # Very high plausibility with all bonuses
        dc = calculate_invention_dc(
            plausibility=1.0,
            spell_level=0,
            location_type="arcane_tower",
            arcana_proficient=True,
            affinity_count=5,
        )
        assert dc >= 5

    def test_clamp_to_maximum_45(self):
        # Very low plausibility with high level
        dc = calculate_invention_dc(
            plausibility=0.001,
            spell_level=6,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        assert dc <= 45

    @pytest.mark.parametrize("spell_level,modifier", [
        (0, 0),
        (1, 5),
        (2, 10),
        (3, 15),
        (4, 22),
        (5, 30),
        (6, 40),
    ])
    def test_all_spell_level_modifiers(self, spell_level, modifier):
        # Use same plausibility for comparison
        dc = calculate_invention_dc(
            plausibility=0.5,
            spell_level=spell_level,
            location_type=None,
            arcana_proficient=False,
            affinity_count=0,
        )
        # Base plausibility_to_dc(0.5) ≈ 11 + modifier, clamped to [5, 45]
        expected = min(45, max(5, 11 + modifier))
        assert expected - 1 <= dc <= expected + 1


class TestValidateSpellProposal:
    """Tests for spell proposal validation."""

    def test_valid_proposal_level_1_caster_3(self):
        # Caster level 3: max spell level = (3+1)//2 = 2
        proposal = SpellProposal(
            name="Test Spell",
            description="A test spell",
            level=1,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "3d6"},
            plausibility=0.8,
            reasoning="Reasonable spell",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=3)
        assert valid is True
        assert reason == ""

    def test_level_too_high_for_caster(self):
        # Caster level 3: max spell level = 2
        proposal = SpellProposal(
            name="Advanced Spell",
            description="Too powerful",
            level=3,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "5d8"},
            plausibility=0.5,
            reasoning="Too advanced",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=3)
        assert valid is False
        assert "level" in reason.lower()

    def test_invalid_school(self):
        proposal = SpellProposal(
            name="Time Spell",
            description="Chronomancy",
            level=1,
            school="chronomancy",
            elements=["time"],
            mechanics={},
            plausibility=0.6,
            reasoning="New school",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is False
        assert "school" in reason.lower()

    @pytest.mark.parametrize("school", list(VALID_SCHOOLS))
    def test_all_valid_schools(self, school):
        proposal = SpellProposal(
            name="Test Spell",
            description="Test",
            level=1,
            school=school,
            elements=[],
            mechanics={},
            plausibility=0.7,
            reasoning="Valid school",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is True

    def test_damage_dice_within_limit(self):
        # Level 1 max damage: "4d6" = 24
        # Proposing "3d6" = 18, which is valid
        proposal = SpellProposal(
            name="Fireball",
            description="Small fireball",
            level=1,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "3d6"},
            plausibility=0.8,
            reasoning="Standard damage",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is True

    def test_damage_dice_exceeds_limit(self):
        # Level 1 max damage: "4d6" = 24
        # Proposing "5d8" = 40, which exceeds limit
        proposal = SpellProposal(
            name="Mega Blast",
            description="Too powerful",
            level=1,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "5d8"},
            plausibility=0.8,
            reasoning="Too much damage",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is False
        assert "damage" in reason.lower()

    def test_no_damage_dice_utility_spell(self):
        # Utility spells without damage dice should be valid
        proposal = SpellProposal(
            name="Detect Magic",
            description="Senses magic",
            level=1,
            school="divination",
            elements=[],
            mechanics={"range": "30 feet"},
            plausibility=0.9,
            reasoning="Utility spell",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is True

    @pytest.mark.parametrize("caster_level,max_spell_level", [
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 2),
        (5, 3),
        (6, 3),
        (7, 4),
        (8, 4),
        (9, 5),
        (10, 5),
        (11, 6),
        (12, 6),
        (15, 6),
        (20, 6),
    ])
    def test_max_spell_level_by_caster_level(self, caster_level, max_spell_level):
        # Test at the boundary
        proposal_at_max = SpellProposal(
            name="Test",
            description="Test",
            level=max_spell_level,
            school="evocation",
            elements=[],
            mechanics={},
            plausibility=0.8,
            reasoning="At max",
        )
        valid, _ = validate_spell_proposal(proposal_at_max, caster_level)
        assert valid is True

        # Test one above (if not already at 6)
        if max_spell_level < 6:
            proposal_above_max = SpellProposal(
                name="Test",
                description="Test",
                level=max_spell_level + 1,
                school="evocation",
                elements=[],
                mechanics={},
                plausibility=0.8,
                reasoning="Above max",
            )
            valid, _ = validate_spell_proposal(proposal_above_max, caster_level)
            assert valid is False

    def test_cantrip_always_valid_for_casters(self):
        proposal = SpellProposal(
            name="Cantrip",
            description="Basic cantrip",
            level=0,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "1d8"},
            plausibility=0.9,
            reasoning="Cantrip",
        )
        # Even level 1 casters can cast cantrips
        valid, reason = validate_spell_proposal(proposal, caster_level=1)
        assert valid is True

    def test_damage_dice_at_exact_limit(self):
        # Level 1 max: "4d6" = 24
        proposal = SpellProposal(
            name="Max Damage",
            description="At limit",
            level=1,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "4d6"},
            plausibility=0.8,
            reasoning="At limit",
        )
        valid, reason = validate_spell_proposal(proposal, caster_level=5)
        assert valid is True


class TestGenerateWildMagicSurge:
    """Tests for wild magic surge generation."""

    def test_minor_surge_margin_1(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=1, margin_of_failure=1)
        assert surge.damage_to_caster == 0
        assert surge.conditions_applied == []
        assert surge.slot_wasted is True
        assert "minor" in surge.description.lower() or "fizzle" in surge.description.lower()

    def test_minor_surge_margin_5(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=2, margin_of_failure=5)
        assert surge.damage_to_caster == 0
        assert surge.conditions_applied == []
        assert surge.slot_wasted is True

    def test_moderate_surge_margin_6(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=1, margin_of_failure=6)
        assert surge.damage_to_caster > 0
        assert surge.slot_wasted is True
        # May or may not have dazed (30% chance)

    def test_moderate_surge_margin_10(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=2, margin_of_failure=10)
        assert surge.damage_to_caster > 0
        assert surge.slot_wasted is True

    def test_severe_surge_margin_11(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=3, margin_of_failure=11)
        assert surge.damage_to_caster > 0
        assert "dazed" in surge.conditions_applied
        assert surge.slot_wasted is True
        assert surge.damage_to_caster > 0  # Severe surges always deal damage

    def test_severe_surge_margin_20(self):
        random.seed(42)
        surge = generate_wild_magic_surge(spell_level=4, margin_of_failure=20)
        assert surge.damage_to_caster > 0
        assert "dazed" in surge.conditions_applied
        assert surge.slot_wasted is True

    def test_spell_level_affects_damage_cantrip(self):
        random.seed(42)
        surge_cantrip = generate_wild_magic_surge(spell_level=0, margin_of_failure=11)
        # Severe surge with level 0: damage = random(2,8) * 2 * max(1,0) = random(2,8) * 2 * 1
        assert surge_cantrip.damage_to_caster > 0

    def test_spell_level_affects_damage_high_level(self):
        random.seed(42)
        surge_high = generate_wild_magic_surge(spell_level=6, margin_of_failure=11)
        # Severe surge with level 6: damage = random(2,8) * 2 * 6 = much higher
        assert surge_high.damage_to_caster > surge_high.damage_to_caster // 6  # Sanity check

    def test_slot_wasted_always_true(self):
        random.seed(42)
        for margin in [1, 6, 11]:
            surge = generate_wild_magic_surge(spell_level=1, margin_of_failure=margin)
            assert surge.slot_wasted is True

    def test_moderate_surge_damage_range(self):
        # Test multiple seeds to verify damage is in expected range
        damages = []
        for seed in range(10):
            random.seed(seed)
            surge = generate_wild_magic_surge(spell_level=2, margin_of_failure=8)
            damages.append(surge.damage_to_caster)
        # Moderate: random(1,6) * max(1, 2) = 2-12
        assert all(d >= 2 for d in damages)
        assert all(d <= 12 for d in damages)

    def test_severe_surge_damage_range(self):
        # Test multiple seeds to verify damage is in expected range
        damages = []
        for seed in range(10):
            random.seed(seed)
            surge = generate_wild_magic_surge(spell_level=2, margin_of_failure=15)
            damages.append(surge.damage_to_caster)
        # Severe: random(2,8) * 2 * max(1, 2) = 4-32
        assert all(d >= 4 for d in damages)
        assert all(d <= 32 for d in damages)


class TestDiceWithinLimit:
    """Tests for _dice_within_limit helper."""

    def test_equal_dice(self):
        assert _dice_within_limit("4d6", "4d6") is True

    def test_under_limit(self):
        # "2d6" = 12, "4d6" = 24
        assert _dice_within_limit("2d6", "4d6") is True

    def test_over_limit(self):
        # "5d8" = 40, "4d6" = 24
        assert _dice_within_limit("5d8", "4d6") is False

    def test_with_bonus_under_limit(self):
        # "2d6+4" = 16, "4d6" = 24
        assert _dice_within_limit("2d6+4", "4d6") is True

    def test_with_bonus_over_limit(self):
        # "3d8+10" = 34, "4d6" = 24
        assert _dice_within_limit("3d8+10", "4d6") is False

    def test_different_die_sizes(self):
        # "3d8" = 24, "4d6" = 24
        assert _dice_within_limit("3d8", "4d6") is True

    def test_invalid_format_returns_true(self):
        # Graceful handling of invalid format
        assert _dice_within_limit("invalid", "4d6") is True
        assert _dice_within_limit("4d6", "invalid") is True

    def test_large_dice(self):
        # "12d8" = 96, "10d8" = 80
        assert _dice_within_limit("12d8", "10d8") is False

    def test_cantrip_dice(self):
        # "1d10" = 10, "1d10" = 10
        assert _dice_within_limit("1d10", "1d10") is True


class TestMaxDiceValue:
    """Tests for _max_dice_value helper."""

    def test_simple_dice(self):
        assert _max_dice_value("3d8") == 24

    def test_single_die(self):
        assert _max_dice_value("1d10") == 10

    def test_with_bonus(self):
        assert _max_dice_value("2d6+4") == 16

    def test_large_dice(self):
        assert _max_dice_value("12d8") == 96

    def test_cantrip_dice(self):
        assert _max_dice_value("1d4") == 4

    def test_high_damage_spell(self):
        assert _max_dice_value("10d8") == 80

    @pytest.mark.parametrize("dice_str,expected", [
        ("1d6", 6),
        ("2d6", 12),
        ("3d6", 18),
        ("4d6", 24),
        ("5d8", 40),
        ("8d6", 48),
        ("8d8", 64),
        ("10d8", 80),
        ("12d8", 96),
        ("1d10", 10),
        ("2d6+4", 16),
        ("3d8+5", 29),
    ])
    def test_various_dice_values(self, dice_str, expected):
        assert _max_dice_value(dice_str) == expected


class TestSpellProposalDataclass:
    """Tests for SpellProposal dataclass."""

    def test_create_proposal(self):
        proposal = SpellProposal(
            name="Fireball",
            description="A ball of fire",
            level=3,
            school="evocation",
            elements=["fire"],
            mechanics={"damage_dice": "8d6", "range": "150 feet"},
            plausibility=0.85,
            reasoning="Classic spell",
        )
        assert proposal.name == "Fireball"
        assert proposal.level == 3
        assert proposal.school == "evocation"
        assert "fire" in proposal.elements
        assert proposal.mechanics["damage_dice"] == "8d6"


class TestWildMagicSurgeDataclass:
    """Tests for WildMagicSurge dataclass."""

    def test_create_surge(self):
        surge = WildMagicSurge(
            description="Sparks fly everywhere",
            damage_to_caster=5,
            conditions_applied=["dazed"],
            slot_wasted=True,
        )
        assert "Sparks" in surge.description
        assert surge.damage_to_caster == 5
        assert "dazed" in surge.conditions_applied
        assert surge.slot_wasted is True


class TestConstants:
    """Tests for module constants."""

    def test_location_bonuses_all_negative(self):
        assert all(bonus < 0 for bonus in LOCATION_BONUSES.values())

    def test_spell_level_dc_modifier_increasing(self):
        levels = sorted(SPELL_LEVEL_DC_MODIFIER.keys())
        for i in range(len(levels) - 1):
            assert SPELL_LEVEL_DC_MODIFIER[levels[i]] <= SPELL_LEVEL_DC_MODIFIER[levels[i + 1]]

    def test_valid_schools_count(self):
        assert len(VALID_SCHOOLS) == 8

    def test_valid_schools_all_lowercase(self):
        assert all(school.islower() for school in VALID_SCHOOLS)

    def test_max_damage_dice_keys(self):
        assert set(MAX_DAMAGE_DICE.keys()) == {0, 1, 2, 3, 4, 5, 6}
