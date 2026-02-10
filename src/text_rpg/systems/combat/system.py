"""Combat game system — turn-based combat with initiative, NPC AI, and combat menu."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from text_rpg.content.loader import load_all_items
from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.combat_math import (
    attack_roll,
    calculate_flee_dc,
    damage_roll,
    determine_turn_order,
    initiative_roll,
    npc_choose_action,
)
from text_rpg.mechanics.conditions import (
    can_take_actions,
    grants_advantage_to_attackers,
    has_attack_advantage,
    has_attack_disadvantage,
)
from text_rpg.mechanics.skills import skill_check
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "llm" / "prompts"
_jinja_env: Environment | None = None


def _get_jinja() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)
    return _jinja_env


class CombatSystem(GameSystem):
    def __init__(self, repos: dict[str, Any] | None = None):
        self._repos = repos or {}
        self._llm = None

    def inject(self, *, repos: dict | None = None, llm: Any = None, **kwargs: Any) -> None:
        if repos is not None:
            self._repos = repos
        if llm is not None:
            self._llm = llm

    @property
    def system_id(self) -> str:
        return "combat"

    @property
    def handled_action_types(self) -> set[str]:
        return {"attack", "dodge", "dash", "disengage", "help", "hide", "flee", "combat_item", "combat_spell", "puzzle"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        # Check for puzzle encounter
        if action.action_type.lower() == "puzzle":
            encounter = action.parameters.get("encounter")
            if encounter:
                return self._resolve_puzzle(action, context, encounter)

        combat = context.combat_state
        if not combat or not combat.get("is_active"):
            # Check if the encounter is a puzzle type before initiating combat
            encounter = self._find_encounter_for_combat(context)
            if encounter and encounter.get("fight_type") == "puzzle":
                return self._resolve_puzzle(action, context, encounter)
            # First attack → initiate combat
            return self._initiate_combat(action, context)
        # Already in combat → resolve player turn, then NPC turns
        return self._resolve_combat_turn(action, context)

    def get_available_actions(self, context: GameContext) -> list[dict]:
        if not context.combat_state or not context.combat_state.get("is_active"):
            hostiles = [e for e in context.entities if e.get("is_hostile") and e.get("is_alive", True)]
            if hostiles:
                return [{"action_type": "attack", "targets": [e["name"] for e in hostiles]}]
            return []
        return [
            {"action_type": "attack", "description": "[1] Attack an enemy"},
            {"action_type": "combat_spell", "description": "[2] Cast a spell"},
            {"action_type": "combat_item", "description": "[3] Use an item"},
            {"action_type": "flee", "description": "[4] Flee"},
            {"action_type": "dodge", "description": "[5] Dodge"},
        ]

    # -- Combat Initiation --

    def _initiate_combat(self, action: Action, context: GameContext) -> ActionResult:
        """Roll initiative for all combatants, create combat state, resolve first exchange."""
        target = self._find_target(action.target_id, context)
        if not target:
            # If attacking a non-hostile NPC, still allow it
            target = self._find_any_target(action.target_id, context)
            if not target:
                return ActionResult(action_id=action.id, success=False, outcome_description="No valid target found.")

        # Collect all hostile + the targeted entity for combat
        enemy_ids = set()
        enemy_ids.add(target["id"])
        for e in context.entities:
            if e.get("is_hostile") and e.get("is_alive", True):
                enemy_ids.add(e["id"])

        # Build combat state via start_combat
        combat = self.start_combat(context, list(enemy_ids))

        # Save combat state to DB
        if self._repos and self._repos.get("world_state"):
            try:
                self._repos["world_state"].save_combat(combat)
            except Exception as e:
                logger.error(f"Failed to save combat state: {e}")

        # Build initiative report
        dice_rolls: list[DiceRoll] = []
        init_report = []
        for c in combat["combatants"]:
            init_report.append(f"{c['name']}: {c['initiative']}")
            dice_rolls.append(DiceRoll(
                dice_expression="1d20",
                rolls=[c["initiative"] - c.get("initiative_bonus", 0)],
                modifier=c.get("initiative_bonus", 0),
                total=c["initiative"],
                purpose=f"initiative ({c['name']})",
            ))

        events: list[dict[str, Any]] = [{
            "event_type": "COMBAT_START",
            "description": f"Combat begins! Initiative: {', '.join(init_report)}",
            "actor_id": context.character["id"],
        }]

        # Determine who goes first
        first_id = combat["turn_order"][0] if combat["turn_order"] else None
        player_id = context.character["id"]

        # If player goes first, resolve their attack action
        if first_id == player_id:
            player_result = self._resolve_player_attack(action, target, context, combat)
            mutations = player_result["mutations"]
            dice_rolls.extend(player_result["dice_rolls"])
            events.extend(player_result["events"])
            outcome = f"Combat begins! You act first.\n{player_result['description']}"
            xp = player_result["xp"]

            # Then resolve NPC turns
            npc_results = self._resolve_all_npc_turns(combat, context)
            mutations.extend(npc_results["mutations"])
            dice_rolls.extend(npc_results["dice_rolls"])
            events.extend(npc_results["events"])
            if npc_results["description"]:
                outcome += f"\n{npc_results['description']}"
        else:
            # NPC goes first — resolve NPC turns until player's turn
            outcome = "Combat begins! The enemy acts first.\n"
            mutations: list[StateMutation] = []
            xp = 0

            npc_results = self._resolve_all_npc_turns(combat, context)
            mutations.extend(npc_results["mutations"])
            dice_rolls.extend(npc_results["dice_rolls"])
            events.extend(npc_results["events"])
            if npc_results["description"]:
                outcome += npc_results["description"]
            outcome += "\nYour turn — choose your action."

        # Check combat end
        end_result = self._check_combat_end(combat, context)
        if end_result:
            outcome += f"\n{end_result['description']}"
            xp += end_result.get("xp", 0)
            events.extend(end_result.get("events", []))
            mutations.extend(end_result.get("mutations", []))
            # End combat in DB
            self._end_combat(combat)
        else:
            # Update combat state
            self._save_combat_state(combat)

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=outcome,
            dice_rolls=dice_rolls,
            state_mutations=mutations,
            events=events,
            xp_gained=xp,
        )

    # -- Turn Resolution --

    def _resolve_combat_turn(self, action: Action, context: GameContext) -> ActionResult:
        """Resolve the player's chosen action, then all NPC turns."""
        combat = context.combat_state
        action_type = action.action_type.lower()
        dice_rolls: list[DiceRoll] = []
        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []
        xp = 0
        outcome_parts: list[str] = []

        # Map numbered choices to actions
        if action_type in ("1", "attack"):
            target = self._find_combat_target(action.target_id, context, combat)
            if not target:
                return ActionResult(action_id=action.id, success=False, outcome_description="No valid target in combat.")
            result = self._resolve_player_attack(action, target, context, combat)
            mutations.extend(result["mutations"])
            dice_rolls.extend(result["dice_rolls"])
            events.extend(result["events"])
            outcome_parts.append(result["description"])
            xp += result["xp"]

        elif action_type in ("5", "dodge"):
            outcome_parts.append("You take the Dodge action. Attacks against you have disadvantage until your next turn.")
            # Set dodging condition on player combatant
            self._set_player_condition(combat, "dodging")

        elif action_type in ("4", "flee"):
            flee_result = self._resolve_flee(action, context, combat)
            dice_rolls.extend(flee_result["dice_rolls"])
            events.extend(flee_result["events"])
            outcome_parts.append(flee_result["description"])
            if flee_result["escaped"]:
                self._end_combat(combat)
                return ActionResult(
                    action_id=action.id, success=True,
                    outcome_description="\n".join(outcome_parts),
                    dice_rolls=dice_rolls, events=events,
                )

        elif action_type in ("3", "combat_item"):
            # Delegate to inventory system but consume combat turn
            outcome_parts.append(f"You use an item during combat.")

        elif action_type in ("2", "combat_spell"):
            # Delegate to spellcasting but consume combat turn
            outcome_parts.append(f"You cast a spell during combat.")

        elif action_type in ("dash",):
            outcome_parts.append("You take the Dash action, doubling your movement.")

        elif action_type in ("disengage",):
            outcome_parts.append("You disengage, moving without provoking opportunity attacks.")

        else:
            outcome_parts.append(f"You take the {action_type} action.")

        # Advance round
        combat["round_number"] = combat.get("round_number", 1) + 1

        # Check combat end after player turn
        end_result = self._check_combat_end(combat, context)
        if end_result:
            outcome_parts.append(end_result["description"])
            xp += end_result.get("xp", 0)
            events.extend(end_result.get("events", []))
            mutations.extend(end_result.get("mutations", []))
            self._end_combat(combat)
            return ActionResult(
                action_id=action.id, success=True,
                outcome_description="\n".join(outcome_parts),
                dice_rolls=dice_rolls, state_mutations=mutations,
                events=events, xp_gained=xp,
            )

        # Resolve NPC turns
        npc_results = self._resolve_all_npc_turns(combat, context)
        mutations.extend(npc_results["mutations"])
        dice_rolls.extend(npc_results["dice_rolls"])
        events.extend(npc_results["events"])
        if npc_results["description"]:
            outcome_parts.append(npc_results["description"])

        # Check combat end after NPC turns
        end_result = self._check_combat_end(combat, context)
        if end_result:
            outcome_parts.append(end_result["description"])
            xp += end_result.get("xp", 0)
            events.extend(end_result.get("events", []))
            mutations.extend(end_result.get("mutations", []))
            self._end_combat(combat)
        else:
            self._save_combat_state(combat)

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description="\n".join(outcome_parts),
            dice_rolls=dice_rolls, state_mutations=mutations,
            events=events, xp_gained=xp,
        )

    # -- Player Action Resolution --

    def _resolve_player_attack(
        self, action: Action, target: dict, context: GameContext, combat: dict,
    ) -> dict:
        """Resolve a player attack. Returns dict with mutations, dice_rolls, events, description, xp."""
        char = context.character
        atk_bonus = self._get_attack_bonus(char)
        target_ac = target.get("ac", 10)

        attacker_conditions = safe_json(char.get("conditions"), [])
        target_conditions = safe_json(target.get("conditions"), [])

        advantage = has_attack_advantage(attacker_conditions) or grants_advantage_to_attackers(target_conditions)
        disadvantage = has_attack_disadvantage(attacker_conditions)

        # Check if target has dodging condition in combat state
        target_combatant = self._get_combatant(combat, target.get("id", ""))
        if target_combatant and "dodging" in target_combatant.get("conditions", []):
            disadvantage = True

        hit, is_critical, atk_result = attack_roll(atk_bonus, target_ac, advantage, disadvantage)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=atk_result.individual_rolls,
            modifier=atk_bonus, total=atk_result.total,
            purpose="attack_roll", advantage=advantage, disadvantage=disadvantage,
        )]
        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []
        xp = 0

        if hit:
            dmg_dice, dmg_mod = self._get_damage_dice(char)
            dmg_result = damage_roll(dmg_dice, dmg_mod, is_critical)
            dice_rolls.append(DiceRoll(
                dice_expression=dmg_dice, rolls=dmg_result.individual_rolls,
                modifier=dmg_mod, total=dmg_result.total, purpose="damage_roll",
            ))

            # Update HP in combat state
            old_hp = self._get_combatant_hp(combat, target["id"])
            new_hp = max(0, old_hp - dmg_result.total)
            self._set_combatant_hp(combat, target["id"], new_hp)

            mutations.append(StateMutation(
                target_type="entity", target_id=target["id"],
                field="hp_current", old_value=old_hp, new_value=new_hp,
            ))

            defeated = new_hp <= 0
            crit_text = " CRITICAL HIT!" if is_critical else ""
            desc = f"Hit!{crit_text} {dmg_result.total} damage to {target['name']}."

            # Narrative prose from LLM
            weapon = self._get_weapon_data(char)
            attack_name = weapon.get("name", "weapon strike") if weapon else "weapon strike"
            narration = self._narrate_attack(
                attacker_name=char["name"], attacker_type="player",
                defender_name=target["name"], hit=True, critical=is_critical,
                damage=dmg_result.total, damage_type=weapon.get("damage_type", "") if weapon else "",
                defeated=defeated, attack_name=attack_name,
            )
            if narration:
                desc = narration

            events.append({
                "event_type": "ATTACK",
                "description": f"{char['name']} attacks {target['name']} and hits for {dmg_result.total} damage.",
                "actor_id": char["id"], "target_id": target["id"],
                "mechanical_details": {"damage": dmg_result.total, "critical": is_critical},
            })

            if defeated:
                self._mark_combatant_defeated(combat, target["id"])
                mutations.append(StateMutation(
                    target_type="entity", target_id=target["id"],
                    field="is_alive", old_value=True, new_value=False,
                ))
                events.append({
                    "event_type": "DEATH",
                    "description": f"{target['name']} has been defeated!",
                    "target_id": target["id"],
                })
                cr = target.get("challenge_rating", target.get("level", 1))
                xp = int((cr or 1) * 100)
                if not narration:
                    desc += f" {target['name']} is defeated!"
        else:
            desc = f"Miss! Attack roll {atk_result.total} vs AC {target_ac}."
            narration = self._narrate_attack(
                attacker_name=char["name"], attacker_type="player",
                defender_name=target["name"], hit=False, critical=False,
                damage=0, damage_type="", defeated=False,
            )
            if narration:
                desc = narration
            events.append({
                "event_type": "ATTACK",
                "description": f"{char['name']} attacks {target['name']} and misses.",
                "actor_id": char["id"], "target_id": target["id"],
                "mechanical_details": {"hit": False},
            })

        return {"mutations": mutations, "dice_rolls": dice_rolls, "events": events, "description": desc, "xp": xp}

    def _resolve_flee(self, action: Action, context: GameContext, combat: dict) -> dict:
        """Attempt to flee combat. DEX check vs DC based on enemy count."""
        char = context.character
        scores = safe_json(char.get("ability_scores"), {})
        dex_score = scores.get("dexterity", 10)
        prof_bonus = char.get("proficiency_bonus", 2)

        skill_profs = safe_json(char.get("skill_proficiencies"), [])
        is_prof = "athletics" in skill_profs or "acrobatics" in skill_profs

        active_enemies = [c for c in combat.get("combatants", [])
                         if c.get("combatant_type") == "enemy" and c.get("is_active", True)]
        dc = calculate_flee_dc(len(active_enemies))
        success, roll_result = skill_check(dex_score, prof_bonus, is_prof, dc)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=roll_result.individual_rolls,
            modifier=roll_result.modifier, total=roll_result.total,
            purpose=f"flee_check (DC {dc})",
        )]
        events: list[dict[str, Any]] = []

        if success:
            desc = f"You successfully flee from combat! (Roll: {roll_result.total} vs DC {dc})"
            events.append({"event_type": "COMBAT_FLEE", "description": "Successfully fled from combat."})
        else:
            desc = f"You fail to escape! (Roll: {roll_result.total} vs DC {dc}) The enemies block your retreat."
            events.append({"event_type": "COMBAT_FLEE_FAIL", "description": "Failed to flee from combat."})

        return {"dice_rolls": dice_rolls, "events": events, "description": desc, "escaped": success}

    # -- NPC Turn Resolution --

    def _resolve_all_npc_turns(self, combat: dict, context: GameContext) -> dict:
        """Resolve all non-player turns (enemies and companions). Returns combined results."""
        mutations: list[StateMutation] = []
        dice_rolls: list[DiceRoll] = []
        events: list[dict[str, Any]] = []
        descriptions: list[str] = []

        player_id = context.character["id"]
        player_combatant = self._get_combatant(combat, player_id)

        for eid in combat.get("turn_order", []):
            combatant = self._get_combatant(combat, eid)
            if not combatant or combatant.get("combatant_type") == "player":
                continue
            if not combatant.get("is_active", True):
                continue

            hp = combatant.get("hp", {})
            if isinstance(hp, dict) and hp.get("current", 0) <= 0:
                continue

            c_type = combatant.get("combatant_type")

            if c_type == "companion":
                # Companion AI targets enemies
                enemy_targets = [c for c in combat["combatants"]
                                 if c.get("combatant_type") == "enemy" and c.get("is_active", True)]
                if enemy_targets:
                    ai_action = npc_choose_action(combatant, enemy_targets)
                    if ai_action["action"] == "attack":
                        # Simple companion attack (reuses NPC attack logic but targeting enemy)
                        target = enemy_targets[0]
                        comp_result = self._resolve_companion_attack(combatant, target, context, combat)
                        mutations.extend(comp_result["mutations"])
                        dice_rolls.extend(comp_result["dice_rolls"])
                        events.extend(comp_result["events"])
                        descriptions.append(comp_result["description"])
                continue

            # Enemy NPC AI
            # Enemies target player and companions
            targets = [c for c in combat["combatants"]
                       if c.get("combatant_type") in ("player", "companion") and c.get("is_active", True)]
            ai_action = npc_choose_action(combatant, targets)

            if ai_action["action"] == "flee":
                descriptions.append(f"{combatant['name']} attempts to flee!")
                self._mark_combatant_defeated(combat, eid)
                events.append({"event_type": "NPC_FLEE", "description": f"{combatant['name']} fled from combat."})
                continue

            if ai_action["action"] == "attack" and player_combatant:
                result = self._resolve_npc_attack(combatant, player_combatant, context, combat)
                mutations.extend(result["mutations"])
                dice_rolls.extend(result["dice_rolls"])
                events.extend(result["events"])
                descriptions.append(result["description"])

            elif ai_action["action"] == "dodge":
                descriptions.append(f"{combatant['name']} takes a defensive stance.")
                combatant.setdefault("conditions", []).append("dodging")

        return {
            "mutations": mutations, "dice_rolls": dice_rolls,
            "events": events, "description": "\n".join(descriptions),
        }

    def _resolve_npc_attack(
        self, npc: dict, target: dict, context: GameContext, combat: dict,
    ) -> dict:
        """Resolve an NPC attacking the player."""
        npc_name = npc.get("name", "Enemy")

        # Get NPC attack bonus from entity data
        npc_entity = self._find_entity_for_combatant(npc, context)
        if npc_entity:
            e_scores = safe_json(npc_entity.get("ability_scores"), {})
            str_mod = modifier(e_scores.get("strength", 10))
            dex_mod = modifier(e_scores.get("dexterity", 10))
            atk_bonus = max(str_mod, dex_mod) + 2  # Assume +2 proficiency

            # Check for attacks array for damage dice
            attacks = safe_json(npc_entity.get("attacks"), [])
            if attacks and isinstance(attacks[0], dict):
                dmg_dice = attacks[0].get("damage_dice", "1d6")
                dmg_mod = attacks[0].get("damage_bonus", max(str_mod, dex_mod))
            else:
                dmg_dice = "1d6"
                dmg_mod = max(str_mod, dex_mod)
        else:
            atk_bonus = 3
            dmg_dice = "1d6"
            dmg_mod = 1

        # Target AC
        target_hp = target.get("hp", {})
        if isinstance(target_hp, dict):
            target_ac = context.character.get("ac", 10)
        else:
            target_ac = target.get("ac", 10)

        # Check for advantage/disadvantage
        advantage = False
        disadvantage = False
        player_conditions = target.get("conditions", [])
        if "dodging" in player_conditions:
            disadvantage = True

        hit, is_critical, atk_result = attack_roll(atk_bonus, target_ac, advantage, disadvantage)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=atk_result.individual_rolls,
            modifier=atk_bonus, total=atk_result.total,
            purpose=f"attack_roll ({npc_name})",
        )]
        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []

        char_id = context.character["id"]

        if hit:
            dmg_result = damage_roll(dmg_dice, dmg_mod, is_critical)
            dice_rolls.append(DiceRoll(
                dice_expression=dmg_dice, rolls=dmg_result.individual_rolls,
                modifier=dmg_mod, total=dmg_result.total,
                purpose=f"damage_roll ({npc_name})",
            ))

            old_hp = self._get_combatant_hp(combat, char_id)
            new_hp = max(0, old_hp - dmg_result.total)
            self._set_combatant_hp(combat, char_id, new_hp)

            mutations.append(StateMutation(
                target_type="character", target_id=char_id,
                field="hp_current",
                old_value=context.character.get("hp_current", old_hp),
                new_value=new_hp,
            ))

            crit = " CRITICAL HIT!" if is_critical else ""
            desc = f"{npc_name} attacks you and hits!{crit} {dmg_result.total} damage."
            events.append({
                "event_type": "ATTACK",
                "description": f"{npc_name} attacks {context.character['name']} for {dmg_result.total} damage.",
                "actor_id": npc.get("entity_id", ""), "target_id": char_id,
                "mechanical_details": {"damage": dmg_result.total, "critical": is_critical, "npc_attack": True},
            })

            # Check for wounds from heavy hits
            from text_rpg.mechanics.wounds import check_for_wound
            hp_max = context.character.get("hp_max", 10)
            wound = check_for_wound(dmg_result.total, hp_max)
            wound_text = None
            if wound and new_hp > 0:
                # Add wound to character
                wounds = safe_json(context.character.get("wounds"), [])
                wounds.append(wound)
                mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="wounds", old_value=None, new_value=json.dumps(wounds),
                ))
                wound_text = wound['type'].replace('_', ' ')
                desc += f" You suffer a {wound_text}! ({wound['description']})"
                events.append({
                    "event_type": "WOUND",
                    "description": f"Suffered {wound_text} from {npc_name}'s attack.",
                    "target_id": char_id,
                    "mechanical_details": wound,
                })

            # Narrative prose from LLM
            npc_attack_name = "attack"
            npc_dmg_type = ""
            if npc_entity:
                npc_attacks = safe_json(npc_entity.get("attacks"), [])
                if npc_attacks and isinstance(npc_attacks[0], dict):
                    npc_attack_name = npc_attacks[0].get("name", "attack")
                    npc_dmg_type = npc_attacks[0].get("damage_type", "")
            narration = self._narrate_attack(
                attacker_name=npc_name, attacker_type="enemy",
                defender_name=context.character["name"], hit=True, critical=is_critical,
                damage=dmg_result.total, damage_type=npc_dmg_type,
                defeated=new_hp <= 0, attack_name=npc_attack_name, wound=wound_text,
            )
            if narration:
                desc = narration

            if new_hp <= 0:
                if not narration:
                    desc += " You have been defeated!"
                events.append({
                    "event_type": "PLAYER_DEFEAT",
                    "description": f"{context.character['name']} has been defeated!",
                    "target_id": char_id,
                })
        else:
            desc = f"{npc_name} attacks you and misses! (Roll: {atk_result.total} vs AC {target_ac})"
            narration = self._narrate_attack(
                attacker_name=npc_name, attacker_type="enemy",
                defender_name=context.character["name"], hit=False, critical=False,
                damage=0, damage_type="", defeated=False,
            )
            if narration:
                desc = narration
            events.append({
                "event_type": "ATTACK",
                "description": f"{npc_name} attacks {context.character['name']} and misses.",
                "actor_id": npc.get("entity_id", ""), "target_id": char_id,
                "mechanical_details": {"hit": False, "npc_attack": True},
            })

        # Clear dodging after being attacked
        if "dodging" in target.get("conditions", []):
            target["conditions"].remove("dodging")

        return {"mutations": mutations, "dice_rolls": dice_rolls, "events": events, "description": desc}

    def _resolve_companion_attack(
        self, companion: dict, target: dict, context: GameContext, combat: dict,
    ) -> dict:
        """Resolve a companion attacking an enemy. Simplified version of NPC attack."""
        comp_name = companion.get("name", "Companion")
        target_name = target.get("name", "Enemy")

        # Get companion entity for attack data
        comp_entity = self._find_entity_for_combatant(companion, context)
        if comp_entity:
            e_scores = safe_json(comp_entity.get("ability_scores"), {})
            str_mod = modifier(e_scores.get("strength", 10))
            dex_mod = modifier(e_scores.get("dexterity", 10))
            atk_bonus = max(str_mod, dex_mod) + 2

            attacks = safe_json(comp_entity.get("attacks"), [])
            if attacks and isinstance(attacks[0], dict):
                dmg_dice = attacks[0].get("damage_dice", "1d6")
                dmg_mod = attacks[0].get("damage_bonus", max(str_mod, dex_mod))
            else:
                dmg_dice = "1d6"
                dmg_mod = max(str_mod, dex_mod)
        else:
            atk_bonus = 3
            dmg_dice = "1d6"
            dmg_mod = 1

        target_ac = target.get("ac", 10)
        hit, is_critical, atk_result = attack_roll(atk_bonus, target_ac, False, False)

        dice_rolls = [DiceRoll(
            dice_expression="1d20", rolls=atk_result.individual_rolls,
            modifier=atk_bonus, total=atk_result.total,
            purpose=f"attack_roll ({comp_name})",
        )]
        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []

        if hit:
            dmg_result = damage_roll(dmg_dice, dmg_mod, is_critical)
            dice_rolls.append(DiceRoll(
                dice_expression=dmg_dice, rolls=dmg_result.individual_rolls,
                modifier=dmg_mod, total=dmg_result.total,
                purpose=f"damage_roll ({comp_name})",
            ))

            old_hp = self._get_combatant_hp(combat, target.get("entity_id", ""))
            new_hp = max(0, old_hp - dmg_result.total)
            self._set_combatant_hp(combat, target.get("entity_id", ""), new_hp)

            mutations.append(StateMutation(
                target_type="entity", target_id=target.get("entity_id", ""),
                field="hp_current", old_value=old_hp, new_value=new_hp,
            ))

            crit_text = " Critical!" if is_critical else ""
            desc = f"{comp_name} hits {target_name} for {dmg_result.total} damage!{crit_text}"

            events.append({
                "event_type": "ATTACK",
                "description": f"{comp_name} attacks {target_name} for {dmg_result.total} damage.",
                "actor_id": companion.get("entity_id", ""), "target_id": target.get("entity_id", ""),
            })

            if new_hp <= 0:
                self._mark_combatant_defeated(combat, target.get("entity_id", ""))
                mutations.append(StateMutation(
                    target_type="entity", target_id=target.get("entity_id", ""),
                    field="is_alive", old_value=True, new_value=False,
                ))
                desc += f" {target_name} is defeated!"
                events.append({
                    "event_type": "DEATH",
                    "description": f"{target_name} defeated by {comp_name}!",
                    "target_id": target.get("entity_id", ""),
                })
        else:
            desc = f"{comp_name} attacks {target_name} and misses."
            events.append({
                "event_type": "ATTACK",
                "description": f"{comp_name} attacks {target_name} and misses.",
                "actor_id": companion.get("entity_id", ""), "target_id": target.get("entity_id", ""),
            })

        return {"mutations": mutations, "dice_rolls": dice_rolls, "events": events, "description": desc}

    # -- Combat State Helpers --

    def _check_combat_end(self, combat: dict, context: GameContext) -> dict | None:
        """Check if combat has ended. Returns result dict or None."""
        import random
        from text_rpg.mechanics.death import calculate_death_penalty, get_weakened_condition, find_safe_location

        player_id = context.character["id"]
        player = self._get_combatant(combat, player_id)
        player_hp = 0
        if player:
            hp = player.get("hp", {})
            player_hp = hp.get("current", 0) if isinstance(hp, dict) else 0

        active_enemies = [
            c for c in combat.get("combatants", [])
            if c.get("combatant_type") == "enemy" and c.get("is_active", True)
            and (c.get("hp", {}).get("current", 0) if isinstance(c.get("hp"), dict) else 0) > 0
        ]

        if not active_enemies:
            total_xp = 0
            for c in combat.get("combatants", []):
                if c.get("combatant_type") == "enemy" and not c.get("is_active", True):
                    cr = c.get("challenge_rating", c.get("level", 1)) or 1
                    total_xp += int(cr * 100)

            # Generate loot drops
            loot_mutations, loot_desc = self._generate_loot(combat, context)

            desc = "Victory! All enemies have been defeated!"
            if loot_desc:
                desc += f"\n{loot_desc}"

            return {
                "description": desc,
                "result": "victory",
                "xp": total_xp,
                "mutations": loot_mutations,
                "events": [{"event_type": "COMBAT_END", "description": "Combat ended in victory."}],
            }

        if player_hp <= 0:
            # Death penalty: lose gold, respawn at safe location, gain weakened condition
            char = context.character
            gold = char.get("gold", 0)
            penalty = calculate_death_penalty(gold)
            gold_lost = penalty["gold_lost"]
            weakened = get_weakened_condition()

            death_mutations: list[StateMutation] = []

            # Gold loss
            if gold_lost > 0:
                death_mutations.append(StateMutation(
                    target_type="character", target_id=player_id,
                    field="gold", old_value=gold, new_value=max(0, gold - gold_lost),
                ))

            # Revive with 1 HP
            death_mutations.append(StateMutation(
                target_type="character", target_id=player_id,
                field="hp_current", old_value=0, new_value=1,
            ))

            # Add weakened condition
            conditions = safe_json(char.get("conditions"), [])
            new_conditions = [c for c in conditions if c != "weakened"]
            new_conditions.append("weakened")
            death_mutations.append(StateMutation(
                target_type="character", target_id=player_id,
                field="conditions", old_value=conditions, new_value=new_conditions,
            ))

            # Store weakened duration on character (JSON wounds field)
            wounds = safe_json(char.get("wounds"), [])
            # Add weakened tracker
            wounds = [w for w in wounds if w.get("type") != "_weakened"]
            wounds.append({"type": "_weakened", "turns_remaining": weakened["turns_remaining"]})
            death_mutations.append(StateMutation(
                target_type="character", target_id=player_id,
                field="wounds", old_value=None, new_value=json.dumps(wounds),
            ))

            # Teleport to safe location
            if self._repos:
                locations = self._repos.get("location")
                if locations:
                    all_locs = locations.get_all(context.game_id)
                    safe_id = find_safe_location(all_locs)
                    if safe_id:
                        death_mutations.append(StateMutation(
                            target_type="game", target_id=context.game_id,
                            field="current_location_id", old_value=None, new_value=safe_id,
                        ))

            desc_parts = ["You have been defeated... darkness claims you."]
            if gold_lost > 0:
                desc_parts.append(f"You lost {gold_lost} gold.")
            desc_parts.append("You awaken weakened (-2 to all checks for 5 turns).")

            return {
                "description": "\n".join(desc_parts),
                "result": "defeat",
                "xp": 0,
                "mutations": death_mutations,
                "events": [{"event_type": "COMBAT_END", "description": "Combat ended in defeat."}],
            }

        return None

    def _generate_loot(self, combat: dict, context: GameContext) -> tuple[list[StateMutation], str]:
        """Generate loot drops from defeated enemies. Returns (mutations, description)."""
        import random

        mutations: list[StateMutation] = []
        loot_items: list[str] = []
        gold_total = 0
        char_id = context.character["id"]

        # Look up encounter loot tables by matching enemy names against known encounters
        loot_table = self._find_encounter_loot(combat, context)
        if not loot_table:
            return mutations, ""

        # Roll for item drops
        items = loot_table.get("items", [])
        for item_entry in items:
            if isinstance(item_entry, dict):
                item_id = item_entry.get("id", "")
                chance = item_entry.get("chance", 0.5)
                if item_id and random.random() < chance:
                    loot_items.append(item_id)
                    mutations.append(StateMutation(
                        target_type="inventory", target_id=char_id,
                        field="items_add", old_value=None,
                        new_value=json.dumps({"item_id": item_id, "quantity": 1}),
                    ))

        # Roll gold
        gold_min = loot_table.get("gold_min", 0)
        gold_max = loot_table.get("gold_max", 0)
        if gold_max > 0:
            gold_total = random.randint(gold_min, gold_max)
            if gold_total > 0:
                old_gold = context.character.get("gold", 0)
                mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="gold", old_value=old_gold, new_value=old_gold + gold_total,
                ))

        # Build description
        desc_parts = []
        if loot_items:
            from text_rpg.content.loader import load_all_items
            all_items = load_all_items()
            item_names = [all_items.get(iid, {}).get("name", iid.replace("_", " ").title()) for iid in loot_items]
            desc_parts.append(f"Loot: {', '.join(item_names)}")
        if gold_total > 0:
            desc_parts.append(f"Gold: {gold_total} gp")

        return mutations, " | ".join(desc_parts) if desc_parts else ""

    def _find_encounter_loot(self, combat: dict, context: GameContext) -> dict:
        """Find the loot table for this combat by matching enemy entity IDs."""
        try:
            from text_rpg.content.loader import load_region

            # Collect enemy entity base IDs (without UUID suffix)
            enemy_names = set()
            for c in combat.get("combatants", []):
                if c.get("combatant_type") == "enemy":
                    # Entity IDs in combat are UUIDs, but we stored original entity_id
                    eid = c.get("entity_id", "")
                    name = c.get("name", "").lower()
                    enemy_names.add(name)

            # Load encounters from region
            region_data = load_region("verdant_reach")
            encounters = region_data.get("encounters", [])

            for enc in encounters:
                enc_entities = enc.get("entities", [])
                for ent in enc_entities:
                    if ent.get("name", "").lower() in enemy_names:
                        return enc.get("loot", {})
        except Exception as e:
            logger.warning(f"Failed to find encounter loot: {e}")
        return {}

    def _end_combat(self, combat: dict) -> None:
        """Mark combat as ended and update DB."""
        combat["is_active"] = False
        self._save_combat_state(combat)

    def _save_combat_state(self, combat: dict) -> None:
        """Persist combat state to DB."""
        if self._repos and self._repos.get("world_state"):
            try:
                self._repos["world_state"].update_combat(combat["id"], {
                    "is_active": combat.get("is_active", True),
                    "round_number": combat.get("round_number", 1),
                    "current_turn_index": combat.get("current_turn_index", 0),
                    "combatants": combat.get("combatants", []),
                    "turn_order": combat.get("turn_order", []),
                })
            except Exception as e:
                logger.error(f"Failed to update combat state: {e}")

    def _get_combatant(self, combat: dict, entity_id: str) -> dict | None:
        for c in combat.get("combatants", []):
            if c.get("entity_id") == entity_id:
                return c
        return None

    def _get_combatant_hp(self, combat: dict, entity_id: str) -> int:
        c = self._get_combatant(combat, entity_id)
        if not c:
            return 0
        hp = c.get("hp", {})
        return hp.get("current", 0) if isinstance(hp, dict) else 0

    def _set_combatant_hp(self, combat: dict, entity_id: str, new_hp: int) -> None:
        c = self._get_combatant(combat, entity_id)
        if c:
            hp = c.get("hp", {})
            if isinstance(hp, dict):
                hp["current"] = new_hp
            else:
                c["hp"] = {"current": new_hp, "max": 10, "temp": 0}

    def _mark_combatant_defeated(self, combat: dict, entity_id: str) -> None:
        c = self._get_combatant(combat, entity_id)
        if c:
            c["is_active"] = False

    def _set_player_condition(self, combat: dict, condition: str) -> None:
        for c in combat.get("combatants", []):
            if c.get("combatant_type") == "player":
                c.setdefault("conditions", []).append(condition)
                break

    def _find_entity_for_combatant(self, combatant: dict, context: GameContext) -> dict | None:
        """Find the full entity data for a combat combatant."""
        eid = combatant.get("entity_id", "")
        for e in context.entities:
            if e["id"] == eid:
                return e
        return None

    # -- Target Finding --

    def _find_target(self, target_id: str | None, context: GameContext) -> dict | None:
        """Find a hostile target by name or id (supports partial name matching)."""
        if not target_id:
            for e in context.entities:
                if e.get("is_hostile") and e.get("is_alive", True):
                    return e
            return None
        target_lower = target_id.lower()
        # Exact match first
        for e in context.entities:
            if e.get("is_alive", True) and e.get("is_hostile"):
                if e["id"] == target_id or e["name"].lower() == target_lower:
                    return e
        # Partial match fallback
        for e in context.entities:
            if e.get("is_alive", True) and e.get("is_hostile"):
                if target_lower in e["name"].lower() or e["name"].lower() in target_lower:
                    return e
        return None

    def _find_any_target(self, target_id: str | None, context: GameContext) -> dict | None:
        """Find any alive entity by name or id (including non-hostile, supports partial matching)."""
        if not target_id:
            return None
        target_lower = target_id.lower()
        # Exact match first
        for e in context.entities:
            if e.get("is_alive", True) and (e["id"] == target_id or e["name"].lower() == target_lower):
                return e
        # Partial match fallback
        for e in context.entities:
            if e.get("is_alive", True):
                if target_lower in e["name"].lower() or e["name"].lower() in target_lower:
                    return e
        return None

    def _find_combat_target(self, target_id: str | None, context: GameContext, combat: dict) -> dict | None:
        """Find a valid combat target — must be in combat and alive."""
        active_enemies = [
            c for c in combat.get("combatants", [])
            if c.get("combatant_type") == "enemy" and c.get("is_active", True)
        ]
        if not active_enemies:
            return None

        if target_id:
            # Try to match by name
            for c in active_enemies:
                if c.get("name", "").lower() == target_id.lower() or c.get("entity_id") == target_id:
                    # Return entity data
                    for e in context.entities:
                        if e["id"] == c["entity_id"]:
                            return e
            # Fuzzy match
            for c in active_enemies:
                if target_id.lower() in c.get("name", "").lower():
                    for e in context.entities:
                        if e["id"] == c["entity_id"]:
                            return e

        # Default to first active enemy
        first = active_enemies[0]
        for e in context.entities:
            if e["id"] == first["entity_id"]:
                return e
        return None

    # -- Weapon/Attack Helpers (unchanged) --

    def _get_weapon_data(self, char: dict) -> dict | None:
        weapon_id = char.get("equipped_weapon_id")
        if not weapon_id:
            return None
        all_items = load_all_items()
        return all_items.get(weapon_id)

    def _get_attack_bonus(self, char: dict) -> int:
        scores = safe_json(char.get("ability_scores"), {})
        str_mod = modifier(scores.get("strength", 10))
        dex_mod = modifier(scores.get("dexterity", 10))
        prof = char.get("proficiency_bonus", 2)

        weapon = self._get_weapon_data(char)
        if weapon:
            properties = weapon.get("properties", [])
            weapon_type = weapon.get("weapon_type", "")
            if "finesse" in properties:
                return max(str_mod, dex_mod) + prof
            elif "ranged" in weapon_type:
                return dex_mod + prof
            else:
                return str_mod + prof

        return max(str_mod, dex_mod) + prof

    def _get_damage_dice(self, char: dict) -> tuple[str, int]:
        scores = safe_json(char.get("ability_scores"), {})
        str_mod = modifier(scores.get("strength", 10))
        dex_mod = modifier(scores.get("dexterity", 10))

        weapon = self._get_weapon_data(char)
        if weapon:
            damage_dice = weapon.get("damage_dice", "1d8")
            properties = weapon.get("properties", [])
            weapon_type = weapon.get("weapon_type", "")
            if "finesse" in properties:
                return damage_dice, max(str_mod, dex_mod)
            elif "ranged" in weapon_type:
                return damage_dice, dex_mod
            else:
                return damage_dice, str_mod

        return "1d8", max(str_mod, dex_mod)

    def start_combat(self, context: GameContext, enemy_ids: list[str]) -> dict:
        """Create a new combat state with initiative rolls."""
        combatants = []
        char = context.character
        scores = safe_json(char.get("ability_scores"), {})
        dex_mod = modifier(scores.get("dexterity", 10))
        init = initiative_roll(dex_mod)
        combatants.append({
            "entity_id": char["id"], "name": char["name"], "combatant_type": "player",
            "initiative": init.total, "initiative_bonus": dex_mod,
            "hp": {"current": char.get("hp_current", 10), "max": char.get("hp_max", 10), "temp": 0},
            "ac": char.get("ac", 10), "is_active": True, "conditions": [], "has_acted": False,
        })
        # Add companions as allies
        for comp in context.companions:
            if comp.get("status") != "active":
                continue
            comp_entity = None
            for e in context.entities:
                if e["id"] == comp["entity_id"]:
                    comp_entity = e
                    break
            if comp_entity:
                c_scores = safe_json(comp_entity.get("ability_scores"), {})
                c_dex = modifier(c_scores.get("dexterity", 10))
                c_init = initiative_roll(c_dex)
                combatants.append({
                    "entity_id": comp_entity["id"], "name": comp_entity["name"],
                    "combatant_type": "companion",
                    "initiative": c_init.total, "initiative_bonus": c_dex,
                    "hp": {"current": comp_entity.get("hp_current", 10), "max": comp_entity.get("hp_max", 10), "temp": 0},
                    "ac": comp_entity.get("ac", 10), "is_active": True, "conditions": [], "has_acted": False,
                })

        for eid in enemy_ids:
            for e in context.entities:
                if e["id"] == eid:
                    e_scores = safe_json(e.get("ability_scores"), {})
                    e_dex = modifier(e_scores.get("dexterity", 10))
                    e_init = initiative_roll(e_dex)
                    combatants.append({
                        "entity_id": e["id"], "name": e["name"], "combatant_type": "enemy",
                        "initiative": e_init.total, "initiative_bonus": e_dex,
                        "hp": {"current": e.get("hp_current", 10), "max": e.get("hp_max", 10), "temp": 0},
                        "ac": e.get("ac", 10), "is_active": True, "conditions": [], "has_acted": False,
                        "challenge_rating": e.get("challenge_rating", e.get("level", 1)),
                    })
        init_pairs = [(c["entity_id"], c["initiative"]) for c in combatants]
        turn_order = determine_turn_order(init_pairs)
        return {
            "id": str(uuid.uuid4()), "game_id": context.game_id, "is_active": True,
            "round_number": 1, "current_turn_index": 0,
            "combatants": combatants, "turn_order": turn_order,
        }

    # -- Narrative Combat Prose --

    def _narrate_attack(
        self, attacker_name: str, attacker_type: str, defender_name: str,
        hit: bool, critical: bool, damage: int, damage_type: str,
        defeated: bool, attack_name: str = "weapon strike",
        wound: str | None = None, location_desc: str | None = None,
    ) -> str | None:
        """Generate narrative prose for a combat attack via LLM. Returns None on failure."""
        if not self._llm:
            return None
        try:
            env = _get_jinja()
            template = env.get_template("combat_narration.j2")
            prompt = template.render(
                attacker_name=attacker_name,
                attacker_type=attacker_type,
                defender_name=defender_name,
                attack_name=attack_name,
                hit=hit,
                critical=critical,
                damage=damage,
                damage_type=damage_type,
                defeated=defeated,
                wound=wound,
                location_desc=location_desc,
            )
            return self._llm.generate(prompt, temperature=0.9, max_tokens=128).strip()
        except Exception as e:
            logger.warning(f"Combat narration failed: {e}")
            return None

    # -- Puzzle Encounter Resolution --

    def _resolve_puzzle(self, action: Action, context: GameContext, encounter: dict) -> ActionResult:
        """Resolve a puzzle encounter instead of normal combat."""
        from text_rpg.mechanics.puzzles import evaluate_puzzle_attempt, get_puzzle_reward

        puzzle = encounter.get("puzzle", {})
        puzzle_type = puzzle.get("puzzle_type", "lock")
        enc_desc = encounter.get("description", "You face a puzzle.")

        # For riddle type with LLM, check if player gave the right answer
        if puzzle_type == "riddle" and self._llm:
            riddle_answer = puzzle.get("riddle_answer", "")
            player_answer = action.parameters.get("answer", action.raw_input or "")
            if riddle_answer and player_answer:
                answer_lower = player_answer.lower().strip()
                correct_lower = riddle_answer.lower().strip()
                # Direct match or LLM evaluation
                if correct_lower in answer_lower or answer_lower in correct_lower:
                    reward = get_puzzle_reward(encounter)
                    mutations, loot_desc = self._generate_puzzle_loot(encounter, context)
                    desc = f"{enc_desc}\n\nYou speak the answer: \"{player_answer}\".\nThe door groans open, revealing treasure beyond!"
                    if loot_desc:
                        desc += f"\n{loot_desc}"
                    return ActionResult(
                        action_id=action.id, success=True,
                        outcome_description=desc,
                        state_mutations=mutations,
                        xp_gained=reward["xp"],
                        events=[{"event_type": "PUZZLE_SOLVED", "description": f"Solved: {encounter.get('name', 'puzzle')}"}],
                    )

        result = evaluate_puzzle_attempt(
            puzzle=puzzle,
            action_description=action.raw_input or "",
            character=context.character,
            inventory=context.inventory,
        )

        dice_rolls = []
        if result.get("roll_result"):
            roll_res = result["roll_result"]
            dice_rolls.append(DiceRoll(
                dice_expression="1d20",
                rolls=roll_res.individual_rolls,
                modifier=roll_res.modifier,
                total=roll_res.total,
                purpose=f"{result.get('skill_used', 'check')} (DC {result['dc']})",
            ))

        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []
        xp = 0
        desc = f"{enc_desc}\n\n{result['description']}"

        if result["success"]:
            reward = get_puzzle_reward(encounter)
            xp = reward["xp"]
            loot_mutations, loot_desc = self._generate_puzzle_loot(encounter, context)
            mutations.extend(loot_mutations)
            if loot_desc:
                desc += f"\n{loot_desc}"
            events.append({"event_type": "PUZZLE_SOLVED", "description": f"Solved: {encounter.get('name', 'puzzle')}"})
        else:
            # Trap damage on failure
            if puzzle_type == "trap" and not result.get("detected", True):
                trap_dmg_expr = puzzle.get("trap_damage", "2d6")
                from text_rpg.mechanics.dice import roll
                trap_roll = roll(trap_dmg_expr)
                trap_dmg = trap_roll.total
                char_id = context.character["id"]
                old_hp = context.character.get("hp_current", 10)
                new_hp = max(0, old_hp - trap_dmg)
                mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="hp_current", old_value=old_hp, new_value=new_hp,
                ))
                dice_rolls.append(DiceRoll(
                    dice_expression=trap_dmg_expr, rolls=trap_roll.individual_rolls,
                    modifier=0, total=trap_dmg, purpose="trap_damage",
                ))
                desc += f" You take {trap_dmg} damage from the trap!"
                events.append({"event_type": "TRAP_DAMAGE", "description": f"Took {trap_dmg} trap damage."})
            events.append({"event_type": "PUZZLE_FAILED", "description": f"Failed: {encounter.get('name', 'puzzle')}"})

        return ActionResult(
            action_id=action.id, success=result["success"],
            outcome_description=desc,
            dice_rolls=dice_rolls,
            state_mutations=mutations,
            events=events,
            xp_gained=xp,
        )

    def _generate_puzzle_loot(self, encounter: dict, context: GameContext) -> tuple[list[StateMutation], str]:
        """Generate loot for solved puzzles. Reuses loot table format."""
        import random

        loot_table = encounter.get("loot", {})
        if not loot_table:
            return [], ""

        mutations: list[StateMutation] = []
        loot_items: list[str] = []
        gold_total = 0
        char_id = context.character["id"]

        for item_entry in loot_table.get("items", []):
            if isinstance(item_entry, dict):
                item_id = item_entry.get("id", "")
                chance = item_entry.get("chance", 0.5)
                if item_id and random.random() < chance:
                    loot_items.append(item_id)
                    mutations.append(StateMutation(
                        target_type="inventory", target_id=char_id,
                        field="items_add", old_value=None,
                        new_value=json.dumps({"item_id": item_id, "quantity": 1}),
                    ))

        gold_min = loot_table.get("gold_min", 0)
        gold_max = loot_table.get("gold_max", 0)
        if gold_max > 0:
            gold_total = random.randint(gold_min, gold_max)
            if gold_total > 0:
                old_gold = context.character.get("gold", 0)
                mutations.append(StateMutation(
                    target_type="character", target_id=char_id,
                    field="gold", old_value=old_gold, new_value=old_gold + gold_total,
                ))

        desc_parts = []
        if loot_items:
            all_items = load_all_items()
            item_names = [all_items.get(iid, {}).get("name", iid.replace("_", " ").title()) for iid in loot_items]
            desc_parts.append(f"Loot: {', '.join(item_names)}")
        if gold_total > 0:
            desc_parts.append(f"Gold: {gold_total} gp")

        return mutations, " | ".join(desc_parts) if desc_parts else ""

    def _find_encounter_for_combat(self, context: GameContext) -> dict | None:
        """Find the encounter definition matching the current combat."""
        try:
            from text_rpg.content.loader import load_region
            region_data = load_region("verdant_reach")
            location_id = context.location.get("id", "")
            for enc in region_data.get("encounters", []):
                locs = enc.get("location_ids", [])
                if location_id in locs:
                    return enc
        except Exception:
            pass
        return None
