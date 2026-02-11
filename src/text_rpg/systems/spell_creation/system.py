"""Spell creation system — combine elements and invent new spells."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from text_rpg.content.loader import load_all_spells
from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.elements import get_combination_affinity
from text_rpg.mechanics.skills import skill_check
from text_rpg.mechanics.spell_combinations import (
    SPELL_COMBINATIONS,
    can_attempt_combination,
    calculate_combination_dc,
    find_combination,
)
from text_rpg.mechanics.spell_invention import (
    LOCATION_BONUSES,
    SpellProposal,
    calculate_invention_dc,
    generate_wild_magic_surge,
    validate_spell_proposal,
)
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)


class SpellCreationSystem(GameSystem):
    """Handles spell combination (combine_spell) and invention (invent_spell)."""

    def __init__(self) -> None:
        self._repos: dict[str, Any] | None = None
        self._llm: Any = None
        self._all_spells: dict[str, dict] | None = None

    def inject(self, *, repos: dict | None = None, llm: Any = None, **kwargs: Any) -> None:
        if repos is not None:
            self._repos = repos
        if llm is not None:
            self._llm = llm
        self._all_spells = None  # Reset cache on re-inject

    @property
    def system_id(self) -> str:
        return "spell_creation"

    @property
    def handled_action_types(self) -> set[str]:
        return {"combine_spell", "invent_spell"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        at = action.action_type.lower()
        if at == "combine_spell":
            return self._resolve_combination(action, context)
        return self._resolve_invention(action, context)

    def get_available_actions(self, context: GameContext) -> list[dict]:
        if context.character.get("spellcasting_ability"):
            return [
                {"action_type": "combine_spell", "description": "Combine two elements into a new spell"},
                {"action_type": "invent_spell", "description": "Invent a completely new spell"},
            ]
        return []

    def _get_spells(self) -> dict[str, dict]:
        if self._all_spells is None:
            self._all_spells = load_all_spells()
        return self._all_spells

    def _get_all_spells_for_context(self, context: GameContext) -> dict[str, dict]:
        """Merge TOML spells with any player-created custom spells."""
        base = dict(self._get_spells())
        repos = self._repos or {}
        spell_creation_repo = repos.get("spell_creation")
        if spell_creation_repo:
            customs = spell_creation_repo.get_custom_spells(context.game_id, context.character["id"])
            for cs in customs:
                spell_dict = {
                    "id": cs["id"],
                    "name": cs["name"],
                    "level": cs["level"],
                    "school": cs.get("school", "evocation"),
                    "description": cs["description"],
                    "mechanics": cs.get("mechanics", {}),
                    "elements": cs.get("elements", []),
                    "classes": [],  # Custom spells are class-agnostic for creator
                    "is_custom": True,
                }
                base[cs["id"]] = spell_dict
        return base

    # -- Combination --

    def _resolve_combination(self, action: Action, context: GameContext) -> ActionResult:
        char = context.character
        char_id = char["id"]
        game_id = context.game_id

        # Check spellcaster
        casting_ability = char.get("spellcasting_ability")
        if not casting_ability:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You don't know how to cast spells, let alone combine them.",
            )

        # Parse elements from action
        element_a = (action.parameters.get("element_a") or action.target_id or "").lower().strip()
        element_b = (action.parameters.get("element_b") or "").lower().strip()

        if not element_a or not element_b:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="Combine what? Use 'combine fire and wind' to merge two elements.",
            )

        # Check player knows spells of both elements
        repos = self._repos or {}
        spell_repo = repos.get("spell")
        known_spells = []
        if spell_repo:
            known_spells = spell_repo.get_known_spells(game_id, char_id)

        all_spells = self._get_all_spells_for_context(context)
        can_combine, reason = can_attempt_combination(known_spells, all_spells, element_a, element_b)
        if not can_combine:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=reason,
            )

        # Find matching combination recipe
        combo = find_combination(element_a, element_b)
        if not combo:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You attempt to merge {element_a} and {element_b}, but the elements resist each other. No combination exists for these elements.",
            )

        # Check if already discovered
        spell_creation_repo = repos.get("spell_creation")
        if spell_creation_repo and spell_creation_repo.has_discovered(game_id, char_id, combo.id):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You've already discovered {combo.name}! It's in your spellbook.",
            )

        # Calculate DC
        scores = safe_json(char.get("ability_scores"), {})
        int_score = scores.get("intelligence", 10)
        prof_bonus = char.get("proficiency_bonus", 2)
        skill_profs = safe_json(char.get("skill_proficiencies"), [])
        is_arcana_prof = "arcana" in skill_profs
        arcana_mod = modifier(int_score) + (prof_bonus if is_arcana_prof else 0)

        affinity = get_combination_affinity(element_a, element_b)
        loc_type = context.location.get("location_type", "")
        location_bonus = LOCATION_BONUSES.get(loc_type, 0)

        dc = calculate_combination_dc(combo.discovery_dc, arcana_mod, affinity, location_bonus)

        # Arcana check
        success, roll_result = skill_check(int_score, prof_bonus, is_arcana_prof, dc)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=roll_result.individual_rolls,
            modifier=roll_result.modifier, total=roll_result.total,
            purpose=f"arcana check (DC {dc})",
        )]

        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []

        if success:
            # Learn the combination spell
            if spell_repo:
                spell_repo.learn_spell(game_id, char_id, combo.result_spell_id)
            if spell_creation_repo:
                spell_creation_repo.discover_combination(game_id, char_id, combo.id, context.turn_number)

            events.append({
                "event_type": "SPELL_COMBINED",
                "description": f"Discovered {combo.name} by combining {element_a} and {element_b}!",
                "actor_id": char_id,
                "mechanical_details": {
                    "combination_id": combo.id,
                    "element_a": element_a,
                    "element_b": element_b,
                    "spell_id": combo.result_spell_id,
                },
            })

            desc = (
                f"The energies of {element_a} and {element_b} swirl together and stabilize! "
                f"You've discovered {combo.name}! (Roll: {roll_result.total} vs DC {dc})"
            )
            xp = 50

            return ActionResult(
                action_id=action.id, success=True,
                outcome_description=desc,
                dice_rolls=dice_rolls,
                state_mutations=mutations,
                events=events,
                xp_gained=xp,
            )
        else:
            # Failure — waste a spell slot, possible surge
            margin = dc - roll_result.total
            surge = generate_wild_magic_surge(2, margin)

            surge_mutations: list[StateMutation] = []
            if surge.damage_to_caster > 0:
                old_hp = char.get("hp_current", 10)
                new_hp = max(0, old_hp - surge.damage_to_caster)
                surge_mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="hp_current", old_value=old_hp, new_value=new_hp,
                ))

            events.append({
                "event_type": "SPELL_CREATION_FAIL",
                "description": f"Failed to combine {element_a} and {element_b}.",
                "actor_id": char_id,
                "mechanical_details": {
                    "element_a": element_a,
                    "element_b": element_b,
                    "dc": dc,
                    "roll": roll_result.total,
                },
            })
            if surge.damage_to_caster > 0 or surge.conditions_applied:
                events.append({
                    "event_type": "WILD_MAGIC_SURGE",
                    "description": surge.description,
                    "actor_id": char_id,
                    "mechanical_details": {
                        "damage": surge.damage_to_caster,
                        "conditions": surge.conditions_applied,
                    },
                })

            desc = (
                f"The elements resist your control! (Roll: {roll_result.total} vs DC {dc}) "
                f"{surge.description}"
            )

            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=desc,
                dice_rolls=dice_rolls,
                state_mutations=surge_mutations,
                events=events,
            )

    # -- Invention --

    def _resolve_invention(self, action: Action, context: GameContext) -> ActionResult:
        char = context.character
        char_id = char["id"]
        game_id = context.game_id

        # Check spellcaster
        casting_ability = char.get("spellcasting_ability")
        if not casting_ability:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You don't have the magical knowledge to invent spells.",
            )

        # Extract spell concept
        spell_concept = (action.parameters.get("spell_concept") or action.target_id or "").strip()
        if not spell_concept:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="Invent what? Describe a spell concept, e.g. 'invent spell that creates a wall of thorns'.",
            )

        # LLM evaluates the concept
        if not self._llm:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="The arcane energies are unstable. Try again later.",
            )

        from text_rpg.systems.director.generators import evaluate_spell_invention
        proposal_dict = evaluate_spell_invention(self._llm, spell_concept, context)

        proposal = SpellProposal(
            name=proposal_dict.get("name", spell_concept[:30]),
            description=proposal_dict.get("description", spell_concept),
            level=proposal_dict.get("level", 1),
            school=proposal_dict.get("school", "evocation"),
            elements=proposal_dict.get("elements", []),
            mechanics=proposal_dict.get("mechanics", {"type": "utility"}),
            plausibility=proposal_dict.get("plausibility", 0.5),
            reasoning=proposal_dict.get("reasoning", ""),
        )

        # Validate proposal
        caster_level = char.get("level", 1)
        is_valid, validation_reason = validate_spell_proposal(proposal, caster_level)
        if not is_valid:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"The concept is beyond your ability: {validation_reason}",
            )

        # Calculate DC
        scores = safe_json(char.get("ability_scores"), {})
        int_score = scores.get("intelligence", 10)
        prof_bonus = char.get("proficiency_bonus", 2)
        skill_profs = safe_json(char.get("skill_proficiencies"), [])
        is_arcana_prof = "arcana" in skill_profs

        loc_type = context.location.get("location_type", "")

        # Count element affinities the player has (from behavior tracking)
        repos = self._repos or {}
        trait_repo = repos.get("trait")
        affinity_count = 0
        if trait_repo:
            traits = trait_repo.get_character_traits(game_id, char_id)
            for t in traits:
                if t.get("category", "").endswith("_affinity"):
                    affinity_count += 1

        dc = calculate_invention_dc(
            proposal.plausibility, proposal.level, loc_type,
            is_arcana_prof, affinity_count,
        )

        # Arcana check
        success, roll_result = skill_check(int_score, prof_bonus, is_arcana_prof, dc)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=roll_result.individual_rolls,
            modifier=roll_result.modifier, total=roll_result.total,
            purpose=f"arcana check (DC {dc})",
        )]

        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []

        if success:
            # Create the custom spell
            spell_id = str(uuid.uuid4()).replace("-", "_")[:16]
            spell_creation_repo = repos.get("spell_creation")
            if spell_creation_repo:
                spell_creation_repo.save_custom_spell({
                    "id": spell_id,
                    "game_id": game_id,
                    "character_id": char_id,
                    "name": proposal.name,
                    "level": proposal.level,
                    "school": proposal.school,
                    "description": proposal.description,
                    "mechanics": proposal.mechanics,
                    "elements": proposal.elements,
                    "plausibility": proposal.plausibility,
                    "creation_dc": dc,
                    "created_turn": context.turn_number,
                    "location_id": context.location.get("id"),
                })

            # Learn the spell
            spell_repo = repos.get("spell")
            if spell_repo:
                spell_repo.learn_spell(game_id, char_id, spell_id)

            xp = proposal.level * 25 + 10

            events.append({
                "event_type": "SPELL_CREATED",
                "description": f"Invented {proposal.name}! A level {proposal.level} {proposal.school} spell.",
                "actor_id": char_id,
                "mechanical_details": {
                    "spell_id": spell_id,
                    "spell_name": proposal.name,
                    "spell_level": proposal.level,
                    "elements": proposal.elements,
                    "plausibility": proposal.plausibility,
                },
            })

            loc_note = ""
            if loc_type in LOCATION_BONUSES:
                loc_note = f" The {loc_type.replace('_', ' ')} empowers your research."

            desc = (
                f"Arcane energy crystallizes into a new spell! "
                f"You've invented '{proposal.name}' — a level {proposal.level} {proposal.school} spell. "
                f"(Roll: {roll_result.total} vs DC {dc}){loc_note}"
            )

            return ActionResult(
                action_id=action.id, success=True,
                outcome_description=desc,
                dice_rolls=dice_rolls,
                state_mutations=mutations,
                events=events,
                xp_gained=xp,
            )
        else:
            # Failure — wild magic surge
            margin = dc - roll_result.total
            surge = generate_wild_magic_surge(proposal.level, margin)

            if surge.damage_to_caster > 0:
                old_hp = char.get("hp_current", 10)
                new_hp = max(0, old_hp - surge.damage_to_caster)
                mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="hp_current", old_value=old_hp, new_value=new_hp,
                ))

            events.append({
                "event_type": "SPELL_CREATION_FAIL",
                "description": f"Failed to invent '{proposal.name}' (plausibility: {proposal.plausibility:.2f}).",
                "actor_id": char_id,
                "mechanical_details": {
                    "spell_concept": spell_concept,
                    "plausibility": proposal.plausibility,
                    "dc": dc,
                    "roll": roll_result.total,
                },
            })
            if surge.damage_to_caster > 0 or surge.conditions_applied:
                events.append({
                    "event_type": "WILD_MAGIC_SURGE",
                    "description": surge.description,
                    "actor_id": char_id,
                    "mechanical_details": {
                        "damage": surge.damage_to_caster,
                        "conditions": surge.conditions_applied,
                    },
                })

            desc = (
                f"Your attempt to weave '{proposal.name}' unravels! "
                f"(Roll: {roll_result.total} vs DC {dc}) {surge.description}"
            )

            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=desc,
                dice_rolls=dice_rolls,
                state_mutations=mutations,
                events=events,
            )
