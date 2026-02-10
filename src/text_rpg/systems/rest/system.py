"""Rest system — short and long rests."""
from __future__ import annotations

from text_rpg.mechanics.dice import roll
from text_rpg.mechanics.ability_scores import modifier
from text_rpg.mechanics.leveling import HIT_DICE
from text_rpg.mechanics.spellcasting import get_arcane_recovery_slots, get_spell_slots
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

import json


class RestSystem(GameSystem):
    def __init__(self, repos: dict | None = None):
        self._repos = repos or {}

    def inject(self, *, repos: dict | None = None, **kwargs) -> None:
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "rest"

    @property
    def handled_action_types(self) -> set[str]:
        return {"rest"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() == "rest"

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        rest_type = action.parameters.get("rest_type", "short")
        if rest_type == "long":
            return self._long_rest(action, context)
        return self._short_rest(action, context)

    def get_available_actions(self, context: GameContext) -> list[dict]:
        if context.combat_state and context.combat_state.get("is_active"):
            return []
        return [
            {"action_type": "rest", "parameters": {"rest_type": "short"}, "description": "Take a short rest"},
            {"action_type": "rest", "parameters": {"rest_type": "long"}, "description": "Take a long rest"},
        ]

    def _short_rest(self, action: Action, context: GameContext) -> ActionResult:
        char = context.character
        scores = safe_json(char.get("ability_scores"), {})
        con_mod = modifier(scores.get("constitution", 10))
        hit_dice_remaining = char.get("hit_dice_remaining", 0)

        if hit_dice_remaining <= 0:
            return ActionResult(
                action_id=action.id, success=True,
                outcome_description="You rest briefly but have no hit dice to spend.",
                events=[{"event_type": "REST", "description": "Took a short rest (no hit dice)."}],
            )

        cls = char.get("char_class", "fighter")
        if isinstance(cls, str):
            cls = cls.lower()
        hit_die = HIT_DICE.get(cls, "1d8")
        result = roll(hit_die)
        healed = max(1, result.total + con_mod)

        old_hp = char.get("hp_current", 0)
        max_hp = char.get("hp_max", old_hp)
        new_hp = min(old_hp + healed, max_hp)

        mutations = [
            StateMutation(target_type="character", target_id=char["id"], field="hp_current", old_value=old_hp, new_value=new_hp),
            StateMutation(target_type="character", target_id=char["id"], field="hit_dice_remaining", old_value=hit_dice_remaining, new_value=hit_dice_remaining - 1),
        ]
        desc = f"You take a short rest and recover {new_hp - old_hp} hit points."

        # Wizard Arcane Recovery: recover spell slot levels = ceil(level/2)
        if cls == "wizard" and char.get("spellcasting_ability"):
            slots_remaining = safe_json(char.get("spell_slots_remaining"), {})
            slots_max = safe_json(char.get("spell_slots_max"), {})

            recovery_budget = get_arcane_recovery_slots(char.get("level", 1))
            new_slots = {str(k): v for k, v in slots_remaining.items()}
            recovered_text = []
            for sl in sorted(int(k) for k in slots_max):
                if recovery_budget <= 0:
                    break
                current = int(new_slots.get(str(sl), 0))
                maximum = int(slots_max.get(str(sl), slots_max.get(sl, 0)))
                can_recover = maximum - current
                if can_recover > 0 and sl <= recovery_budget:
                    recover_count = min(can_recover, recovery_budget // sl)
                    if recover_count > 0:
                        new_slots[str(sl)] = current + recover_count
                        recovery_budget -= sl * recover_count
                        recovered_text.append(f"{recover_count} level-{sl}")

            if recovered_text:
                mutations.append(StateMutation(
                    target_type="character", target_id=char["id"],
                    field="spell_slots_remaining",
                    old_value={str(k): v for k, v in slots_remaining.items()},
                    new_value=new_slots,
                ))
                desc += f" Arcane Recovery: restored {', '.join(recovered_text)} spell slot(s)."

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=desc,
            dice_rolls=[DiceRoll(
                dice_expression=hit_die, rolls=result.individual_rolls,
                modifier=con_mod, total=healed, purpose="hit_dice_healing",
            )],
            state_mutations=mutations,
            events=[{"event_type": "REST", "description": desc}],
        )

    def _long_rest(self, action: Action, context: GameContext) -> ActionResult:
        char = context.character
        old_hp = char.get("hp_current", 0)
        max_hp = char.get("hp_max", old_hp)
        max_dice = char.get("level", 1)
        old_dice = char.get("hit_dice_remaining", 0)
        restored_dice = min(max(max_dice // 2, 1), max_dice - old_dice)

        mutations = [
            StateMutation(target_type="character", target_id=char["id"], field="hp_current", old_value=old_hp, new_value=max_hp),
            StateMutation(target_type="character", target_id=char["id"], field="hit_dice_remaining", old_value=old_dice, new_value=old_dice + restored_dice),
            StateMutation(target_type="character", target_id=char["id"], field="conditions", old_value=None, new_value=[]),
        ]
        desc = f"You take a long rest. All hit points restored. {restored_dice} hit dice recovered."

        # Restore all spell slots and clear concentration
        if char.get("spellcasting_ability"):
            slots_max = safe_json(char.get("spell_slots_max"), {})
            if slots_max:
                mutations.append(StateMutation(
                    target_type="character", target_id=char["id"],
                    field="spell_slots_remaining",
                    old_value=char.get("spell_slots_remaining"),
                    new_value={str(k): v for k, v in slots_max.items()},
                ))
                desc += " All spell slots restored."
            if char.get("concentration_spell"):
                mutations.append(StateMutation(
                    target_type="character", target_id=char["id"],
                    field="concentration_spell",
                    old_value=char.get("concentration_spell"),
                    new_value=None,
                ))

        # Attempt to heal wounds on long rest (50% each)
        from text_rpg.mechanics.wounds import heal_wound
        wounds = safe_json(char.get("wounds"), [])
        if wounds:
            remaining_wounds = []
            healed_wounds = []
            for wound in wounds:
                if wound.get("type") == "_weakened":
                    # Weakened always clears on long rest
                    healed_wounds.append("weakened")
                    continue
                if heal_wound(wound, "long_rest"):
                    healed_wounds.append(wound.get("type", "wound").replace("_", " "))
                else:
                    remaining_wounds.append(wound)
            if healed_wounds:
                desc += f" Wounds healed: {', '.join(healed_wounds)}."
            if remaining_wounds:
                desc += f" Wounds still festering: {len(remaining_wounds)}."
            mutations.append(StateMutation(
                target_type="character", target_id=char["id"],
                field="wounds", old_value=None, new_value=json.dumps(remaining_wounds),
            ))

        # Bounty decay on long rest
        if self._repos and self._repos.get("reputation"):
            try:
                # Get current region from location
                region_id = context.location.get("region_id", "")
                if region_id:
                    self._repos["reputation"].decay_bounty(context.game_id, region_id, 5)
                    bounty = self._repos["reputation"].get_bounty(context.game_id, region_id)
                    if bounty.get("amount", 0) > 0:
                        desc += f" Your bounty in the region has decreased slightly."
            except Exception:
                pass

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=desc,
            state_mutations=mutations,
            events=[{"event_type": "REST", "description": desc}],
        )
