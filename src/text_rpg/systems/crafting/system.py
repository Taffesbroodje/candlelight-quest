"""Crafting system — handles craft and train actions."""
from __future__ import annotations

import json
from typing import Any

from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.crafting import (
    RECIPES, TRADE_SKILL_ABILITY, TRADE_SKILL_DESCRIPTIONS, TRAINING_COST,
    attempt_craft, can_craft,
)
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json


class CraftingSystem(GameSystem):
    """Handles crafting and training actions."""

    def __init__(self) -> None:
        self._repos: dict[str, Any] | None = None

    def inject(self, *, repos: dict | None = None, **kwargs) -> None:
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "crafting"

    @property
    def handled_action_types(self) -> set[str]:
        return {"craft", "train"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        action_type = action.action_type.lower()
        if action_type == "craft":
            return self._resolve_craft(action, context)
        elif action_type == "train":
            return self._resolve_train(action, context)
        return ActionResult(action_id=action.id, success=False, outcome_description="Unknown crafting action.")

    def _resolve_craft(self, action: Action, context: GameContext) -> ActionResult:
        target = (action.target_id or "").lower().strip()
        if not target:
            return ActionResult(action_id=action.id, success=False, outcome_description="Craft what? Type 'recipes' to see what you can make.")

        repos = self._repos or {}
        trade_repo = repos.get("trade_skill")
        if not trade_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Crafting is not available.")

        char = context.character
        char_id = char["id"]
        game_id = context.game_id

        # Find matching recipe
        recipe = None
        for r in RECIPES.values():
            r_name = r.name.lower()
            r_id = r.id.replace("_", " ")
            result_name = r.result_item.replace("_", " ")
            if target in r_name or target in r_id or target in result_name or r_name in target:
                recipe = r
                break

        if not recipe:
            return ActionResult(action_id=action.id, success=False,
                                outcome_description=f"No recipe found for '{target}'. Type 'recipes' to see available recipes.")

        # Check skill
        skill_data = trade_repo.get_skill(game_id, char_id, recipe.skill)
        if not skill_data or not skill_data.get("is_learned"):
            return ActionResult(action_id=action.id, success=False,
                                outcome_description=f"You haven't learned {recipe.skill}. Find a trainer to learn this skill.")

        skill_level = skill_data.get("level", 1)

        # Check materials in inventory
        inv = context.inventory
        inv_items: list[dict] = []
        if inv:
            inv_items_raw = safe_json(inv.get("items"), [])
            inv_items = inv_items_raw

        material_counts: dict[str, int] = {}
        for entry in inv_items:
            item_id = entry.get("item_id", "")
            material_counts[item_id] = material_counts.get(item_id, 0) + entry.get("quantity", 1)

        can_do, reason = can_craft(recipe, skill_level, material_counts)
        if not can_do:
            return ActionResult(action_id=action.id, success=False, outcome_description=reason)

        # Pre-validate enchanting prerequisites before consuming materials
        if recipe.skill == "enchanting" and recipe.id.startswith("enchant_"):
            pre_result = self._validate_enchant_prereqs(recipe, inv_items)
            if not pre_result["ok"]:
                return ActionResult(
                    action_id=action.id, success=False,
                    outcome_description=pre_result["reason"],
                )
        elif recipe.skill == "enchanting" and recipe.id == "scribe_scroll":
            pre_result = self._validate_scribe_prereqs(action, context, char_id, game_id)
            if not pre_result["ok"]:
                return ActionResult(
                    action_id=action.id, success=False,
                    outcome_description=pre_result["reason"],
                )

        # Attempt the craft (skill check)
        scores = safe_json(char.get("ability_scores"), {})
        ability_name = TRADE_SKILL_ABILITY.get(recipe.skill, "intelligence")
        ability_mod = modifier(scores.get(ability_name, 10))

        success, roll_total = attempt_craft(recipe, skill_level, ability_mod)

        dice_rolls = [DiceRoll(
            dice_expression="1d20",
            rolls=[roll_total - ability_mod - skill_level // 2],
            modifier=ability_mod + skill_level // 2,
            total=roll_total,
            purpose=f"{recipe.skill} check (DC {recipe.dc})",
        )]

        mutations: list[StateMutation] = []
        events: list[dict[str, Any]] = []

        # Consume materials regardless of success
        for mat_id, required in recipe.materials.items():
            for _ in range(required):
                mutations.append(StateMutation(
                    target_type="inventory", target_id=char_id,
                    field="items_remove_one", old_value=None, new_value=mat_id,
                ))

        if success:
            # Enchanting: replace a base item with the enchanted variant
            if recipe.skill == "enchanting" and recipe.id.startswith("enchant_"):
                self._handle_enchant_transform(recipe, inv_items, char_id, mutations)
            elif recipe.skill == "enchanting" and recipe.id == "scribe_scroll":
                self._handle_scribe_scroll(action, context, char_id, game_id, mutations)
            else:
                # Normal crafting: add result item
                mutations.append(StateMutation(
                    target_type="inventory", target_id=char_id,
                    field="items_add", old_value=None,
                    new_value=json.dumps({"item_id": recipe.result_item, "quantity": recipe.result_quantity}),
                ))

            # Award crafting XP
            xp_result = trade_repo.add_xp(game_id, char_id, recipe.skill, recipe.xp_reward)

            desc = f"Success! You crafted {recipe.name}."
            if xp_result.get("leveled_up"):
                desc += f" Your {recipe.skill} skill increased to level {xp_result['level']}!"

            events.append({
                "event_type": "CRAFT_SUCCESS",
                "description": f"Crafted {recipe.name}",
                "actor_id": char_id,
                "mechanical_details": {
                    "recipe": recipe.id,
                    "skill_xp": recipe.xp_reward,
                    "result_item": recipe.result_item,
                },
            })

            # Update guild work order progress
            self._update_work_order_progress(
                game_id, char_id, "CRAFT_SUCCESS",
                {"recipe": recipe.id, "result_item": recipe.result_item},
            )
        else:
            desc = f"Failed! Your attempt to craft {recipe.name} didn't work out. Materials consumed."
            # Still award some XP for trying
            trade_repo.add_xp(game_id, char_id, recipe.skill, recipe.xp_reward // 3)

            events.append({
                "event_type": "CRAFT_FAIL",
                "description": f"Failed to craft {recipe.name}",
                "actor_id": char_id,
            })

        return ActionResult(
            action_id=action.id, success=success, outcome_description=desc,
            dice_rolls=dice_rolls, state_mutations=mutations, events=events,
        )

    # --- Enchanting recipe mapping: recipe_id -> required base item type ---
    _ENCHANT_BASE_TYPE: dict[str, str | None] = {
        "enchant_fire_weapon": "weapon",
        "enchant_frost_weapon": "weapon",
        "enchant_lightning_weapon": "weapon",
        "enchant_sharpness": "weapon",
        "enchant_protection_armor": "armor",
        "enchant_resistance_armor": "armor",
        "enchant_ring": None,  # No base item needed — creates from scratch
    }

    # Scroll spell mapping: spell_id -> scroll item_id
    _SCROLL_MAP: dict[str, str] = {
        "fire_bolt": "scroll_fire_bolt",
        "healing_word": "scroll_healing_word",
        "shield": "scroll_shield",
        "magic_missile": "scroll_magic_missile",
        "sleep": "scroll_sleep",
        "cure_wounds": "scroll_cure_wounds",
        "thunderwave": "scroll_thunderwave",
        "hold_person": "scroll_hold_person",
    }

    def _find_enchant_base(self, recipe_id: str, inv_items: list[dict]) -> dict | None:
        """Find a suitable base item in inventory for an enchantment recipe."""
        from text_rpg.content.loader import load_all_items

        base_type = self._ENCHANT_BASE_TYPE.get(recipe_id)
        if base_type is None:
            return None  # No base needed

        all_items = load_all_items()
        for entry in inv_items:
            item_id = entry.get("item_id", "")
            item_data = all_items.get(item_id, {})
            if item_data.get("item_type") == base_type:
                # Don't enchant already-enchanted items (rare/very_rare are enchanted)
                if item_data.get("rarity") not in ("rare", "very_rare"):
                    return entry
        return None

    def _validate_enchant_prereqs(self, recipe: "Recipe", inv_items: list[dict]) -> dict[str, Any]:
        """Check enchantment prerequisites before rolling. Returns {"ok": True} or {"ok": False, "reason": str}."""
        base_type = self._ENCHANT_BASE_TYPE.get(recipe.id)
        if base_type is None:
            return {"ok": True}
        base_entry = self._find_enchant_base(recipe.id, inv_items)
        if not base_entry:
            return {
                "ok": False,
                "reason": f"You need a {base_type} in your inventory to enchant.",
            }
        return {"ok": True}

    def _handle_enchant_transform(
        self, recipe: "Recipe", inv_items: list[dict],
        char_id: str, mutations: list[StateMutation],
    ) -> None:
        """Add mutations to transform a base item into an enchanted variant."""
        base_type = self._ENCHANT_BASE_TYPE.get(recipe.id)
        if base_type is None:
            mutations.append(StateMutation(
                target_type="inventory", target_id=char_id,
                field="items_add", old_value=None,
                new_value=json.dumps({"item_id": recipe.result_item, "quantity": 1}),
            ))
            return

        base_entry = self._find_enchant_base(recipe.id, inv_items)
        mutations.append(StateMutation(
            target_type="items_transform", target_id=char_id,
            field="transform",
            old_value=None,
            new_value=json.dumps({
                "remove_id": base_entry["item_id"],
                "add_id": recipe.result_item,
            }),
        ))

    def _resolve_scribe_spell(self, action: Action, context: GameContext, game_id: str) -> str | None:
        """Determine which spell to scribe. Returns spell_id or None."""
        repos = self._repos or {}
        spell_repo = repos.get("spell")
        if not spell_repo:
            return None

        char_id = context.character["id"]
        known_spells = spell_repo.get_known_spells(game_id, char_id)
        scribable = [s for s in known_spells if s in self._SCROLL_MAP]
        if not scribable:
            return None

        spell_target = (action.parameters.get("spell_name") or "").lower().strip()
        if spell_target:
            from text_rpg.content.loader import load_all_spells
            all_spells = load_all_spells()
            for sid in scribable:
                sdata = all_spells.get(sid, {})
                sname = sdata.get("name", sid).lower()
                if spell_target in sname or spell_target in sid.replace("_", " ") or sname in spell_target:
                    return sid
            return None
        return scribable[0]

    def _validate_scribe_prereqs(
        self, action: Action, context: GameContext, char_id: str, game_id: str,
    ) -> dict[str, Any]:
        """Check scribe_scroll prerequisites. Returns {"ok": True} or {"ok": False, "reason": str}."""
        repos = self._repos or {}
        spell_repo = repos.get("spell")
        if not spell_repo:
            return {"ok": False, "reason": "Spell system is not available."}

        known_spells = spell_repo.get_known_spells(game_id, char_id)
        if not known_spells:
            return {"ok": False, "reason": "You don't know any spells to inscribe on a scroll."}

        scribable = [s for s in known_spells if s in self._SCROLL_MAP]
        if not scribable:
            return {"ok": False, "reason": "None of your known spells can be scribed onto a scroll."}

        spell_target = (action.parameters.get("spell_name") or "").lower().strip()
        if spell_target:
            chosen = self._resolve_scribe_spell(action, context, game_id)
            if not chosen:
                return {"ok": False, "reason": f"You don't know a scribable spell matching '{spell_target}'. Scribable: {', '.join(scribable)}"}
        return {"ok": True}

    def _handle_scribe_scroll(
        self, action: Action, context: GameContext,
        char_id: str, game_id: str, mutations: list[StateMutation],
    ) -> None:
        """Add mutations to create a scroll from a known spell."""
        chosen_spell = self._resolve_scribe_spell(action, context, game_id)
        scroll_id = self._SCROLL_MAP[chosen_spell]
        mutations.append(StateMutation(
            target_type="inventory", target_id=char_id,
            field="items_add", old_value=None,
            new_value=json.dumps({"item_id": scroll_id, "quantity": 1}),
        ))

    def _update_work_order_progress(
        self, game_id: str, char_id: str,
        event_type: str, details: dict,
    ) -> None:
        """Update progress on active guild work orders after a craft event."""
        repos = self._repos or {}
        guild_repo = repos.get("guild")
        if not guild_repo:
            return

        from text_rpg.mechanics.guilds import update_work_order_progress

        active_orders = guild_repo.get_active_orders(game_id, char_id)
        for order in active_orders:
            new_progress = update_work_order_progress(order, event_type, details)
            if new_progress != order.get("progress", {}):
                guild_repo.update_order_progress(order["id"], new_progress)

    def _resolve_train(self, action: Action, context: GameContext) -> ActionResult:
        target = (action.target_id or "").lower().strip()
        if not target:
            skills_list = ", ".join(TRADE_SKILL_DESCRIPTIONS.keys())
            return ActionResult(action_id=action.id, success=False,
                                outcome_description=f"Train what? Available skills: {skills_list}")

        repos = self._repos or {}
        trade_repo = repos.get("trade_skill")
        if not trade_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Training is not available.")

        # Match skill name
        skill_name = None
        for sname in TRADE_SKILL_DESCRIPTIONS:
            if target == sname or target in sname or sname in target:
                skill_name = sname
                break

        if not skill_name:
            skills_list = ", ".join(TRADE_SKILL_DESCRIPTIONS.keys())
            return ActionResult(action_id=action.id, success=False,
                                outcome_description=f"Unknown skill '{target}'. Available: {skills_list}")

        char = context.character
        char_id = char["id"]
        game_id = context.game_id

        # Check if already learned
        existing = trade_repo.get_skill(game_id, char_id, skill_name)
        if existing and existing.get("is_learned"):
            level = existing.get("level", 1)
            xp = existing.get("xp", 0)
            return ActionResult(action_id=action.id, success=False,
                                outcome_description=f"You already know {skill_name} (level {level}, {xp} XP). Practice by crafting!")

        # Check if a trainer NPC is present
        trainer_present = False
        trainer_name = "a trainer"
        for entity in context.entities:
            props = safe_json(entity.get("properties"), {})
            teaches = props.get("teaches", [])
            if skill_name in teaches:
                trainer_present = True
                trainer_name = entity.get("name", "the trainer")
                break

        # Apply guild training discount
        cost = TRAINING_COST.get(skill_name, 25)
        guild_repo = repos.get("guild")
        guild_discount_applied = False
        if guild_repo:
            from text_rpg.content.loader import load_all_guilds
            from text_rpg.mechanics.guilds import training_cost_with_guild

            guilds_data = load_all_guilds()
            memberships = guild_repo.get_memberships(game_id, char_id)
            for m in memberships:
                gdata = guilds_data.get(m["guild_id"], {})
                if gdata.get("profession") == skill_name:
                    cost = training_cost_with_guild(cost, True, m.get("rank", "initiate"))
                    guild_discount_applied = True
                    break

        if not trainer_present:
            cost = cost * 3  # Much more expensive without a trainer
            gold = char.get("gold", 0)
            if gold < cost:
                return ActionResult(action_id=action.id, success=False,
                                    outcome_description=f"No trainer is nearby. Self-study costs {cost} gp (you have {gold} gp). Find a {skill_name} trainer for a better price ({cost // 3} gp).")
        else:
            gold = char.get("gold", 0)
            if gold < cost:
                return ActionResult(action_id=action.id, success=False,
                                    outcome_description=f"{trainer_name} can teach you {skill_name} for {cost} gp, but you only have {gold} gp.")

        # Deduct gold and learn skill
        new_gold = gold - cost
        mutations = [
            StateMutation(target_type="character", target_id=char_id, field="gold", old_value=gold, new_value=new_gold),
        ]
        trade_repo.learn_skill(game_id, char_id, skill_name)

        # Auto-learn starting recipes
        from text_rpg.mechanics.crafting import get_available_recipes
        starting_recipes = get_available_recipes(skill_name, 1)
        for recipe in starting_recipes:
            trade_repo.learn_recipe(game_id, char_id, recipe.id, skill_name)

        recipe_names = [r.name for r in starting_recipes]
        if trainer_present:
            desc = f"{trainer_name} teaches you the basics of {skill_name} for {cost} gp."
        else:
            desc = f"Through self-study, you learn the basics of {skill_name} for {cost} gp."
        if recipe_names:
            desc += f" You learn: {', '.join(recipe_names)}."

        events = [{
            "event_type": "SKILL_LEARNED",
            "description": f"Learned {skill_name}",
            "actor_id": char_id,
            "mechanical_details": {"skill": skill_name, "cost": cost, "recipes": [r.id for r in starting_recipes]},
        }]

        return ActionResult(
            action_id=action.id, success=True, outcome_description=desc,
            state_mutations=mutations, events=events,
        )

    def get_available_actions(self, context: GameContext) -> list[dict]:
        return [
            {"action_type": "craft", "description": "Craft an item using a known recipe"},
            {"action_type": "train", "description": "Learn a new trade skill"},
        ]
