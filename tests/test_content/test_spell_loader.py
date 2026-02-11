"""Tests for spell loading — validates all spell TOML files."""
from __future__ import annotations

import pytest

from text_rpg.content.loader import load_all_spells, load_all_classes


VALID_SCHOOLS = {
    "abjuration", "conjuration", "divination", "enchantment",
    "evocation", "illusion", "necromancy", "transmutation",
}

VALID_MECHANIC_TYPES = {
    "attack", "save", "auto_hit", "healing", "buff", "utility",
}

VALID_CASTING_TIMES = {
    "action", "bonus_action", "reaction",
}

VALID_COMPONENTS = {"V", "S", "M"}

VALID_DAMAGE_TYPES = {
    "fire", "cold", "lightning", "thunder", "acid", "poison",
    "necrotic", "radiant", "force", "psychic",
    "water", "earth", "wind",
    "bludgeoning", "piercing", "slashing",
}

VALID_SAVE_ABILITIES = {
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
}


@pytest.fixture(scope="module")
def all_spells():
    return load_all_spells()


@pytest.fixture(scope="module")
def all_class_ids():
    return set(load_all_classes().keys())


class TestSpellCount:
    def test_total_spell_count(self, all_spells):
        # Original 24 + ~93 new = ~117 total, allow some flexibility
        assert len(all_spells) >= 100, f"Expected 100+ spells, got {len(all_spells)}"

    def test_has_cantrips(self, all_spells):
        cantrips = [s for s in all_spells.values() if s["level"] == 0]
        assert len(cantrips) >= 15, f"Expected 15+ cantrips, got {len(cantrips)}"

    def test_has_level_4_spells(self, all_spells):
        level_4 = [s for s in all_spells.values() if s["level"] == 4]
        assert len(level_4) >= 8, f"Expected 8+ level 4 spells, got {len(level_4)}"

    def test_has_level_5_spells(self, all_spells):
        level_5 = [s for s in all_spells.values() if s["level"] == 5]
        assert len(level_5) >= 8, f"Expected 8+ level 5 spells, got {len(level_5)}"

    def test_has_level_6_spells(self, all_spells):
        level_6 = [s for s in all_spells.values() if s["level"] == 6]
        assert len(level_6) >= 8, f"Expected 8+ level 6 spells, got {len(level_6)}"


class TestSpellRequiredFields:
    def test_all_spells_have_required_fields(self, all_spells):
        required = ["id", "name", "level", "school", "classes",
                     "casting_time", "range", "duration", "components",
                     "description", "mechanics"]
        for spell_id, spell in all_spells.items():
            for field in required:
                assert field in spell, f"Spell '{spell_id}' missing field '{field}'"

    def test_mechanics_has_type(self, all_spells):
        for spell_id, spell in all_spells.items():
            mech = spell.get("mechanics", {})
            assert "type" in mech, f"Spell '{spell_id}' mechanics missing 'type'"


class TestSpellFieldValues:
    def test_level_range(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert 0 <= spell["level"] <= 6, f"Spell '{spell_id}' has invalid level {spell['level']}"

    def test_school_valid(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert spell["school"] in VALID_SCHOOLS, (
                f"Spell '{spell_id}' has invalid school '{spell['school']}'"
            )

    def test_mechanic_type_valid(self, all_spells):
        for spell_id, spell in all_spells.items():
            mtype = spell["mechanics"]["type"]
            assert mtype in VALID_MECHANIC_TYPES, (
                f"Spell '{spell_id}' has invalid mechanic type '{mtype}'"
            )

    def test_casting_time_valid(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert spell["casting_time"] in VALID_CASTING_TIMES, (
                f"Spell '{spell_id}' has invalid casting_time '{spell['casting_time']}'"
            )

    def test_components_valid(self, all_spells):
        for spell_id, spell in all_spells.items():
            for comp in spell["components"]:
                assert comp in VALID_COMPONENTS, (
                    f"Spell '{spell_id}' has invalid component '{comp}'"
                )

    def test_classes_not_empty(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert len(spell["classes"]) > 0, f"Spell '{spell_id}' has no classes"

    def test_classes_are_valid(self, all_spells, all_class_ids):
        for spell_id, spell in all_spells.items():
            for cls in spell["classes"]:
                assert cls in all_class_ids, (
                    f"Spell '{spell_id}' lists unknown class '{cls}'"
                )

    def test_range_non_negative(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert spell["range"] >= 0, f"Spell '{spell_id}' has negative range"

    def test_description_not_empty(self, all_spells):
        for spell_id, spell in all_spells.items():
            assert len(spell["description"]) > 10, (
                f"Spell '{spell_id}' has too short description"
            )


class TestSpellMechanics:
    def test_attack_spells_have_damage(self, all_spells):
        for spell_id, spell in all_spells.items():
            mech = spell["mechanics"]
            if mech["type"] == "attack":
                assert "damage_dice" in mech, (
                    f"Attack spell '{spell_id}' missing damage_dice"
                )
                assert "damage_type" in mech, (
                    f"Attack spell '{spell_id}' missing damage_type"
                )

    def test_save_spells_have_save_ability(self, all_spells):
        for spell_id, spell in all_spells.items():
            mech = spell["mechanics"]
            if mech["type"] == "save":
                assert "save_ability" in mech, (
                    f"Save spell '{spell_id}' missing save_ability"
                )
                assert mech["save_ability"] in VALID_SAVE_ABILITIES, (
                    f"Save spell '{spell_id}' has invalid save_ability '{mech['save_ability']}'"
                )

    def test_healing_spells_have_healing_dice(self, all_spells):
        for spell_id, spell in all_spells.items():
            mech = spell["mechanics"]
            if mech["type"] == "healing":
                assert "healing_dice" in mech, (
                    f"Healing spell '{spell_id}' missing healing_dice"
                )

    def test_damage_types_valid(self, all_spells):
        for spell_id, spell in all_spells.items():
            mech = spell["mechanics"]
            if "damage_type" in mech:
                assert mech["damage_type"] in VALID_DAMAGE_TYPES, (
                    f"Spell '{spell_id}' has invalid damage_type '{mech['damage_type']}'"
                )


class TestSpellUniqueIds:
    def test_no_duplicate_ids(self, all_spells):
        # load_all_spells returns a dict keyed by id, so duplicates would overwrite
        # We need to check across all TOML files manually
        import tomllib
        from pathlib import Path
        from text_rpg.content.loader import CONTENT_DIR

        all_ids = []
        spell_dir = CONTENT_DIR / "spells"
        for f in spell_dir.glob("*.toml"):
            with open(f, "rb") as fh:
                data = tomllib.load(fh)
            for spell in data.get("spells", []):
                all_ids.append((spell["id"], f.name))

        seen = {}
        dupes = []
        for spell_id, filename in all_ids:
            if spell_id in seen:
                dupes.append(f"'{spell_id}' in both {seen[spell_id]} and {filename}")
            seen[spell_id] = filename

        assert len(dupes) == 0, f"Duplicate spell IDs found: {dupes}"


class TestSpellClassCoverage:
    """Ensure every class has at least some spells available."""

    CASTER_CLASSES = {
        "wizard", "cleric", "bard", "druid", "sorcerer",
        "warlock", "paladin", "ranger",
    }

    def test_each_caster_has_cantrips_or_level_1(self, all_spells):
        for cls in self.CASTER_CLASSES:
            # Half casters (paladin/ranger) might not have cantrips
            spells_for_class = [
                s for s in all_spells.values()
                if cls in s["classes"] and s["level"] <= 1
            ]
            assert len(spells_for_class) >= 2, (
                f"Class '{cls}' has fewer than 2 low-level spells (got {len(spells_for_class)})"
            )

    def test_each_full_caster_has_high_level_spells(self, all_spells):
        full_casters = {"wizard", "cleric", "bard", "druid", "sorcerer"}
        for cls in full_casters:
            high_spells = [
                s for s in all_spells.values()
                if cls in s["classes"] and s["level"] >= 4
            ]
            assert len(high_spells) >= 3, (
                f"Full caster '{cls}' has fewer than 3 high-level (4+) spells (got {len(high_spells)})"
            )

    def test_warlock_has_spells_across_levels(self, all_spells):
        warlock_spells = [s for s in all_spells.values() if "warlock" in s["classes"]]
        levels = {s["level"] for s in warlock_spells}
        assert 0 in levels, "Warlock should have cantrips"
        assert 1 in levels, "Warlock should have 1st level spells"
        assert 3 in levels, "Warlock should have 3rd level spells"

    def test_paladin_has_smite_spells(self, all_spells):
        paladin_spells = [s for s in all_spells.values() if "paladin" in s["classes"]]
        smite_spells = [
            s for s in paladin_spells
            if "smite" in s["id"] or "smite" in s["name"].lower()
        ]
        assert len(smite_spells) >= 2, "Paladin should have at least 2 smite spells"

    def test_ranger_has_hunters_mark(self, all_spells):
        assert "hunters_mark" in all_spells, "Ranger should have Hunter's Mark"
        assert "ranger" in all_spells["hunters_mark"]["classes"]
