"""Main game turn loop — the 7-step pipeline."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from text_rpg.cli.input_handler import InputHandler
from text_rpg.engine.action_dispatcher import ActionDispatcher
from text_rpg.engine.system_registry import SystemRegistry
from text_rpg.engine.validators import validate_action, validate_mutations
from text_rpg.llm.context_packer import ContextPacker
from text_rpg.llm.output_parser import OutputParser
from text_rpg.llm.provider import LLMProvider
from text_rpg.models.action import Action, ActionResult
from text_rpg.rag.indexer import Indexer
from text_rpg.rag.retriever import Retriever
from text_rpg.mechanics import world_clock
from text_rpg.systems.base import GameContext
from text_rpg.utils import safe_json, safe_props

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"


@dataclass
class TurnResult:
    narrative: str = ""
    mechanical_summary: str = ""
    action_result: ActionResult | None = None
    events: list[dict] = field(default_factory=list)
    level_up: dict | None = None  # {"new_level": int, "hp_gained": int} if level-up occurred
    needs_warnings: list[str] = field(default_factory=list)  # Survival need warnings


class TurnLoop:
    def __init__(
        self,
        registry: SystemRegistry,
        dispatcher: ActionDispatcher,
        llm_provider: LLMProvider,
        context_packer: ContextPacker,
        retriever: Retriever,
        indexer: Indexer,
        repos: dict[str, Any],
        director: Any | None = None,
        world_sim: Any | None = None,
    ):
        self.registry = registry
        self.dispatcher = dispatcher
        self.llm = llm_provider
        self.packer = context_packer
        self.retriever = retriever
        self.indexer = indexer
        self.repos = repos
        self.director = director
        self.world_sim = world_sim
        self.input_handler = InputHandler()
        self.parser = OutputParser()

        self._jinja_env: Environment | None = None
        self._active_conversation: dict | None = None  # {"npc_id": str, "npc_name": str}

    @property
    def active_conversation(self) -> dict | None:
        """The NPC the player is currently in conversation with, or None."""
        return self._active_conversation

    def end_conversation(self) -> None:
        """End the current conversation (called externally when location changes, etc.)."""
        self._active_conversation = None

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(PROMPTS_DIR)),
                autoescape=False,
            )
        return self._jinja_env

    def process_turn(self, raw_input: str, game_id: str) -> TurnResult:
        """Process a single game turn through the 7-step pipeline."""
        # Step 2: Retrieve — build context
        context = self._build_context(game_id)
        game = self.repos["save_game"].get_game(game_id)
        turn_number = game.get("turn_number", 0) if game else 0

        # Conversation mode: if actively talking to an NPC, route input as dialogue
        if self._active_conversation:
            conv_result = self._handle_conversation_input(raw_input, context, game_id, turn_number)
            if conv_result is not None:
                return conv_result
            # conv_result is None → conversation broken, fall through to normal processing

        # Step 1: Normalize — classify input
        action = self._normalize_input(raw_input, context)

        # Validate action
        is_valid, reason = validate_action(action, context)
        if not is_valid:
            return TurnResult(narrative=reason)

        # Step 3: Constrain (advisory, skipped for most turns)
        # Step 4: Propose — dispatch to system
        result = self.dispatcher.dispatch(action, context)

        # Step 5: Validate & Execute
        if result.state_mutations:
            result.state_mutations = validate_mutations(result.state_mutations, context)
            self._apply_mutations(result.state_mutations, game_id)

        # Record events
        if result.events:
            self._record_events(result.events, game_id, turn_number, context)

        # Handle XP
        level_up_info = None
        if result.xp_gained > 0:
            level_up_info = self._award_xp(context.character["id"], result.xp_gained)

        # Step 5.4: Advance world clock and run world sim — skip during combat
        in_combat = context.combat_state and context.combat_state.get("is_active")
        if not in_combat:
            new_time = world_clock.advance(context.world_time)
            try:
                self.repos["save_game"].update_world_time(game_id, new_time)
            except Exception as e:
                logger.warning(f"Failed to update world_time: {e}")
            if self.world_sim:
                try:
                    sim_events = self.world_sim.tick(game_id, new_time)
                    if sim_events:
                        self._record_events(sim_events, game_id, turn_number, context)
                except Exception as e:
                    logger.warning(f"World sim tick failed: {e}")

        # Step 5.5: Director evaluation — skip during combat
        if self.director and not in_combat:
            try:
                director_events = self.director.evaluate(context, result, self.repos)
                if director_events:
                    self._record_events(director_events, game_id, turn_number, context)
            except Exception as e:
                logger.warning(f"Director evaluation failed: {e}")

        # Step 5.6: Auto-snapshot — skip during combat
        if not in_combat:
            self._maybe_snapshot(result, context, game_id)

        # Step 5.7: Tick survival needs — skip during combat
        needs_warnings = self._tick_survival_needs(context) if not in_combat else []

        # Step 5.8: Tick down weakened condition duration
        if not in_combat:
            self._tick_weakened_condition(context, game_id)

        # Step 6: Render — narrate
        narrative = self._narrate(result, context)

        # Check if a conversation was started — enter conversation mode
        self._check_enter_conversation(result)

        # Build mechanical summary
        mech_parts = []
        for dr in result.dice_rolls:
            mech_parts.append(f"{dr.purpose}: {dr.dice_expression} = {dr.total}")
        mechanical_summary = " | ".join(mech_parts) if mech_parts else ""

        return TurnResult(
            narrative=narrative,
            mechanical_summary=mechanical_summary,
            action_result=result,
            events=result.events,
            level_up=level_up_info,
            needs_warnings=needs_warnings,
        )

    def _handle_conversation_input(
        self, raw_input: str, context: GameContext, game_id: str, turn_number: int,
    ) -> TurnResult | None:
        """Handle input while in conversation mode.

        Returns a TurnResult if the input was handled as dialogue or conversation exit.
        Returns None if the input breaks conversation and should be processed normally.
        """
        npc_name = self._active_conversation["npc_name"]

        # Check for conversation exit phrases
        if self.input_handler.is_conversation_exit(raw_input):
            self._active_conversation = None
            return TurnResult(narrative=f"You end your conversation with {npc_name}.")

        # Check for clear non-dialogue actions (move, attack, etc.) — exit and process normally
        if self.input_handler.should_break_conversation(raw_input):
            self._active_conversation = None
            return None  # Fall through to normal turn processing

        # Everything else is dialogue directed at the current NPC
        action = Action(
            action_type="talk",
            actor_id=context.character["id"],
            target_id=npc_name,
            raw_input=raw_input,
        )

        is_valid, reason = validate_action(action, context)
        if not is_valid:
            return TurnResult(narrative=reason)

        result = self.dispatcher.dispatch(action, context)

        if result.state_mutations:
            result.state_mutations = validate_mutations(result.state_mutations, context)
            self._apply_mutations(result.state_mutations, game_id)

        if result.events:
            self._record_events(result.events, game_id, turn_number, context)

        if result.xp_gained > 0:
            self._award_xp(context.character["id"], result.xp_gained)

        narrative = self._narrate(result, context)

        mech_parts = []
        for dr in result.dice_rolls:
            mech_parts.append(f"{dr.purpose}: {dr.dice_expression} = {dr.total}")
        mechanical_summary = " | ".join(mech_parts) if mech_parts else ""

        return TurnResult(
            narrative=narrative,
            mechanical_summary=mechanical_summary,
            action_result=result,
            events=result.events,
        )

    def _check_enter_conversation(self, result: ActionResult) -> None:
        """After a turn, check if a DIALOGUE event occurred and enter conversation mode."""
        if not result.events:
            return
        for event in result.events:
            if event.get("event_type") == "DIALOGUE":
                details = event.get("mechanical_details", {})
                npc_name = details.get("npc_name", "")
                npc_id = event.get("target_id", "")
                if npc_name:
                    self._active_conversation = {"npc_id": npc_id, "npc_name": npc_name}
                return

    def _normalize_input(self, raw_input: str, context: GameContext) -> Action:
        """Step 1: Classify player input into a game action."""
        classified = self.input_handler.classify(raw_input)

        if classified["action_type"]:
            return Action(
                action_type=classified["action_type"],
                actor_id=context.character["id"],
                target_id=classified.get("target"),
                parameters=classified.get("parameters", {}),
                raw_input=raw_input,
            )

        # LLM fallback for ambiguous input
        try:
            available = self.registry.get_all_available_actions(context)
            action_types = list({a.get("action_type", "") for a in available if a.get("action_type")})
            action_context = self.packer.pack_action_context(raw_input, context.character, context.location, action_types)

            template = self.jinja_env.get_template("action_classify.j2")
            prompt = template.render(player_input=raw_input, context=action_context, valid_actions=", ".join(action_types))
            llm_result = self.llm.generate_structured(prompt)
            parsed = self.parser.parse_action_classification(llm_result)

            # If LLM confidence is too low, treat as unrecognized
            confidence = parsed.get("confidence", 0.5)
            if confidence < 0.4:
                return Action(action_type="unrecognized", actor_id=context.character["id"], raw_input=raw_input)

            return Action(
                action_type=parsed.get("action_type", "custom").lower(),
                actor_id=context.character["id"],
                target_id=parsed.get("target"),
                parameters=parsed.get("parameters", {}),
                raw_input=raw_input,
            )
        except Exception as e:
            logger.warning(f"LLM action classification failed: {e}")
            return Action(action_type="unrecognized", actor_id=context.character["id"], raw_input=raw_input)

    def _build_context(self, game_id: str) -> GameContext:
        """Step 2: Build a complete game context from DB."""
        game = self.repos["save_game"].get_game(game_id)
        character = self.repos["character"].get_by_game(game_id)
        location_id = game.get("current_location_id", "") if game else ""
        location = self.repos["location"].get(location_id, game_id) or {"id": location_id, "name": "Unknown", "description": "", "connections": []}
        # Populate connections from dedicated table (authoritative source)
        if self.repos.get("connection"):
            try:
                location["connections"] = self.repos["connection"].get_connections(game_id, location_id)
            except Exception:
                pass  # Fall back to embedded JSON if table not ready
        entities = self.repos["entity"].get_by_location(game_id, location_id)
        recent_events = self.repos["event_ledger"].get_recent(game_id, limit=10)
        combat = self.repos["world_state"].get_active_combat(game_id)
        inventory = self.repos["world_state"].get_inventory(character["id"], game_id) if character else None
        active_quests = self.repos["world_state"].get_active_quests(game_id)
        wt = game.get("world_time", 480) if game else 480

        # Fetch active companions
        companions = []
        if self.repos.get("companion"):
            try:
                companions = self.repos["companion"].get_active_companions(game_id)
            except Exception:
                pass

        return GameContext(
            game_id=game_id,
            character=character or {},
            location=location,
            entities=entities,
            combat_state=combat,
            inventory=inventory,
            recent_events=recent_events,
            turn_number=game.get("turn_number", 0) if game else 0,
            active_quests=active_quests,
            world_time=wt,
            companions=companions,
            loop_count=game.get("loop_count", 0) if game else 0,
        )

    def _apply_mutations(self, mutations: list, game_id: str) -> None:
        """Step 5: Apply state mutations to the database."""
        for m in mutations:
            try:
                if m.target_type == "character":
                    if m.field == "conditions":
                        val = json.dumps(m.new_value) if isinstance(m.new_value, list) else m.new_value
                        self.repos["character"].update_field(m.target_id, m.field, val)
                    else:
                        self.repos["character"].update_field(m.target_id, m.field, m.new_value)
                elif m.target_type == "entity":
                    self.repos["entity"].update_field(m.target_id, m.field, m.new_value)
                elif m.target_type == "location":
                    self.repos["location"].update_field(m.target_id, game_id, m.field, m.new_value)
                elif m.target_type in ("inventory", "items_transform"):
                    self._apply_inventory_mutation(m, game_id)
                elif m.target_type == "game":
                    if m.field == "current_location_id":
                        self.repos["save_game"].update_location(game_id, m.new_value)
            except Exception as e:
                logger.error(f"Failed to apply mutation {m.field} on {m.target_type}/{m.target_id}: {e}")

    def _apply_inventory_mutation(self, m: Any, game_id: str) -> None:
        """Apply a single inventory or items_transform mutation."""
        inv = self.repos["world_state"].get_inventory(m.target_id, game_id)
        if not inv:
            return
        items = safe_json(inv.get("items"), [])

        if m.target_type == "items_transform":
            transform = safe_json(m.new_value, {})
            self._remove_item(items, transform.get("remove_id", ""))
            self._add_item(items, transform.get("add_id", ""), 1)
        elif m.field == "items_add":
            new_item = safe_json(m.new_value, {})
            self._add_item(items, new_item.get("item_id", ""), new_item.get("quantity", 1))
        elif m.field == "items_remove_one":
            self._remove_item(items, m.new_value)
        elif m.field == "items_remove":
            item_id = m.new_value
            items[:] = [e for e in items if e.get("item_id") != item_id]

        self.repos["world_state"].update_inventory(inv["id"], items)

    @staticmethod
    def _add_item(items: list[dict], item_id: str, quantity: int) -> None:
        """Add quantity of item_id to items list, stacking if present."""
        for entry in items:
            if entry.get("item_id") == item_id:
                entry["quantity"] = entry.get("quantity", 1) + quantity
                return
        items.append({"item_id": item_id, "quantity": quantity})

    @staticmethod
    def _remove_item(items: list[dict], item_id: str) -> None:
        """Remove one instance of item_id from items list."""
        for i, entry in enumerate(items):
            if entry.get("item_id") == item_id:
                qty = entry.get("quantity", 1)
                if qty <= 1:
                    items.pop(i)
                else:
                    entry["quantity"] = qty - 1
                return

    def _record_events(self, events: list[dict], game_id: str, turn_number: int, context: GameContext) -> None:
        """Step 5b: Record events to ledger and index to RAG."""
        for event in events:
            event_dict = {
                "id": str(uuid.uuid4()),
                "game_id": game_id,
                "event_type": event.get("event_type", "CUSTOM"),
                "turn_number": turn_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor_id": event.get("actor_id", context.character.get("id")),
                "target_id": event.get("target_id"),
                "location_id": event.get("location_id", context.location.get("id")),
                "description": event.get("description", ""),
                "mechanical_details": json.dumps(event.get("mechanical_details", {})),
                "is_canonical": True,
            }
            try:
                self.repos["event_ledger"].append(event_dict)
            except Exception as e:
                logger.error(f"Failed to record event: {e}")

            # Index to RAG
            try:
                self.indexer.index_event(
                    game_id, event.get("event_type", "CUSTOM"),
                    event.get("description", ""),
                    location_id=context.location.get("id"),
                    actor_id=event.get("actor_id"),
                    turn_number=turn_number,
                )
            except Exception:
                pass

    # Event types that warrant longer narration
    _IMPORTANT_EVENTS = frozenset({
        "COMBAT_START", "COMBAT_END", "DEATH", "PLAYER_DEFEAT",
        "QUEST_COMPLETE", "DISCOVERY", "LEVEL_UP", "GUARD_CONFRONTATION",
    })

    def _narrate(self, result: ActionResult, context: GameContext) -> str:
        """Step 6: Ask LLM to narrate the mechanical outcome."""
        if not result.outcome_description:
            return ""

        # Don't narrate failures — return the mechanical message directly
        if not result.success:
            return result.outcome_description

        # Check for dialogue events that need NPC response
        for event in result.events:
            if event.get("event_type") in ("DIALOGUE", "QUEST_NEGOTIATION"):
                return self._generate_dialogue(event, context)

        # Scale narration length by importance
        is_important = any(
            e.get("event_type") in self._IMPORTANT_EVENTS
            for e in result.events
        )
        max_sentences = "4-6" if is_important else "2-3"
        max_tokens = 300 if is_important else 150

        try:
            # Build RAG context
            rag_context = self.retriever.build_context(
                result.outcome_description, context.game_id, context.location.get("id")
            )

            # Gather ambient NPC activity hints
            ambient_hints = self._gather_narrator_hints(context)

            narrative_context = self.packer.pack_narrative_context(
                character=context.character,
                location=context.location,
                recent_events=context.recent_events,
                rag_context=rag_context,
                combat_state=context.combat_state,
                nearby_entities=context.entities,
                world_time=context.world_time,
                narrator_hints=ambient_hints,
            )

            template = self.jinja_env.get_template("narrator.j2")
            prompt = template.render(
                context=narrative_context,
                mechanical_outcome=result.outcome_description,
                tone="neutral",
                max_sentences=max_sentences,
            )
            return self.llm.generate(prompt, max_tokens=max_tokens)
        except Exception as e:
            logger.warning(f"Narration failed: {e}")
            return result.outcome_description

    def _gather_narrator_hints(self, context: GameContext) -> list[str]:
        """Collect ambient hints for the narrator (NPC activities, world events, stories)."""
        import random
        from text_rpg.mechanics.world_sim import get_ambient_activity

        hints: list[str] = []

        # Only include hints ~40% of the time to avoid repetition
        if random.random() > 0.4:
            return hints

        try:
            period = world_clock.get_period(context.world_time)
            loc_id = context.location.get("id", "")
            # Get ambient NPC activities at current location
            ambient = get_ambient_activity(loc_id, context.entities, period)
            hints.extend(ambient[:2])
        except Exception:
            pass

        # Story seed narrator hints from active stories
        try:
            from text_rpg.mechanics.story_seeds import get_narrator_hints, load_all_seeds

            active_stories = self.repos["world_state"].get_active_stories(context.game_id)
            if active_stories:
                all_seeds = load_all_seeds()
                seed_map = {s["id"]: s for s in all_seeds}
                for story in active_stories[:1]:  # Only from first active story
                    seed = seed_map.get(story.get("seed_id", ""))
                    if not seed:
                        continue
                    variables = safe_json(story.get("resolved_variables"), {})
                    story_hints = get_narrator_hints(story, seed, variables)
                    if story_hints:
                        hints.append(random.choice(story_hints))
        except Exception:
            pass

        # Recent world event hints (from events in last 5 turns)
        try:
            for event in context.recent_events:
                if event.get("event_type") in ("WORLD_EVENT", "FACTION_GOAL"):
                    desc = event.get("description", "")
                    if desc and len(hints) < 3:
                        hints.append(desc)
        except Exception:
            pass

        return hints[:3]

    def _generate_dialogue(self, event: dict, context: GameContext) -> str:
        """Generate NPC dialogue using LLM."""
        details = event.get("mechanical_details", {})

        # Handle negotiation events with pre-generated NPC response
        if event.get("event_type") == "QUEST_NEGOTIATION":
            npc_name = details.get("npc_name", "NPC")
            npc_response = details.get("npc_response", "")
            if npc_response:
                return f'**{npc_name}:** "{npc_response}"'

        try:
            # Use personality from properties if available, fall back to dialogue_tags
            personality = details.get("npc_personality", "")
            if not personality:
                tags = details.get("npc_dialogue_tags", [])
                personality = ", ".join(tags) if tags else "friendly and helpful"

            is_greeting = details.get("is_greeting", False)
            template = self.jinja_env.get_template("npc_dialogue.j2")
            prompt = template.render(
                npc_name=details.get("npc_name", "NPC"),
                npc_description=details.get("npc_description", ""),
                npc_personality=personality,
                relationship=details.get("relationship"),
                npc_history=details.get("npc_history"),
                active_quests=details.get("active_quests"),
                context=self.packer._format_location(context.location),
                is_greeting=is_greeting,
                quest_hook=details.get("quest_hook", ""),
                player_says=details.get("player_input", "Hello"),
            )
            dialogue = self.llm.generate(prompt, max_tokens=200)
            npc_name = details.get("npc_name", "NPC")
            return f'**{npc_name}:** "{dialogue.strip()}"'
        except Exception as e:
            logger.warning(f"Dialogue generation failed: {e}")
            npc_name = details.get("npc_name", "NPC")
            return f'**{npc_name}:** "Hmm? Oh, hello there."'

    def _award_xp(self, character_id: str, xp: int) -> dict | None:
        """Award XP and check for level up. Returns level-up info dict or None."""
        try:
            from text_rpg.mechanics.ability_scores import modifier
            from text_rpg.mechanics.character_creation import CLASS_FEATURES
            from text_rpg.mechanics.leveling import can_level_up, proficiency_bonus, roll_hit_points_on_level_up

            char = self.repos["character"].get(character_id)
            if not char:
                return None

            old_xp = char.get("xp", 0)
            new_xp = old_xp + xp
            self.repos["character"].update_field(character_id, "xp", new_xp)

            current_level = char.get("level", 1)
            if not can_level_up(current_level, new_xp):
                return None

            # Level up!
            new_level = current_level + 1
            char_class = char.get("char_class", "fighter")

            # Roll HP
            scores = safe_json(char.get("ability_scores"), {})
            con_mod = modifier(scores.get("constitution", 10))
            hp_gained = roll_hit_points_on_level_up(char_class, con_mod)

            old_hp_max = char.get("hp_max", 10)
            new_hp_max = old_hp_max + hp_gained
            new_hp_current = char.get("hp_current", old_hp_max) + hp_gained

            # Update proficiency bonus
            new_prof = proficiency_bonus(new_level)

            # Get new class features
            new_features = CLASS_FEATURES.get((char_class, new_level), [])
            existing_features = safe_json(char.get("class_features"), [])
            updated_features = existing_features + new_features

            # Apply all level-up changes
            self.repos["character"].update_field(character_id, "level", new_level)
            self.repos["character"].update_field(character_id, "hp_max", new_hp_max)
            self.repos["character"].update_field(character_id, "hp_current", new_hp_current)
            self.repos["character"].update_field(character_id, "proficiency_bonus", new_prof)
            self.repos["character"].update_field(character_id, "hit_dice_remaining", new_level)
            self.repos["character"].update_field(character_id, "class_features", updated_features)

            # Update spell slots on level-up
            if char.get("spellcasting_ability"):
                from text_rpg.mechanics.spellcasting import get_spell_slots
                new_slots_max = get_spell_slots(char_class, new_level)
                if new_slots_max:
                    old_slots_remaining = safe_json(char.get("spell_slots_remaining"), {})
                    # Grant new slots (existing remaining + any new slot levels)
                    new_remaining = {str(k): v for k, v in old_slots_remaining.items()}
                    for sl, count in new_slots_max.items():
                        old_max = int((char.get("spell_slots_max") or {}).get(str(sl), 0))
                        gained = count - old_max
                        if gained > 0:
                            current = int(new_remaining.get(str(sl), 0))
                            new_remaining[str(sl)] = current + gained
                    self.repos["character"].update_field(character_id, "spell_slots_max", new_slots_max)
                    self.repos["character"].update_field(character_id, "spell_slots_remaining", new_remaining)

                # Wizard auto-learns 2 new spells on level-up
                if char_class == "wizard" and self.repos.get("spell"):
                    from text_rpg.content.loader import load_all_spells
                    all_spells = load_all_spells()
                    known = self.repos["spell"].get_known_spells(char.get("game_id", ""), character_id)
                    # Find unlearned wizard spells of castable level
                    learnable = [
                        s for s in all_spells.values()
                        if "wizard" in s.get("classes", [])
                        and s.get("level", 0) > 0
                        and s.get("level", 0) <= max(new_slots_max.keys(), default=0)
                        and s["id"] not in known
                    ]
                    for spell in learnable[:2]:
                        self.repos["spell"].learn_spell(char.get("game_id", ""), character_id, spell["id"])
                        self.repos["spell"].prepare_spell(char.get("game_id", ""), character_id, spell["id"])
                        new_features.append(f"Learned: {spell['name']}")

            # Record level-up event
            self.repos["event_ledger"].append({
                "id": str(uuid.uuid4()),
                "game_id": char.get("game_id", ""),
                "event_type": "LEVEL_UP",
                "turn_number": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor_id": character_id,
                "target_id": None,
                "location_id": None,
                "description": f"{char.get('name', 'Character')} reached level {new_level}!",
                "mechanical_details": json.dumps({
                    "new_level": new_level, "hp_gained": hp_gained,
                    "new_features": new_features,
                }),
                "is_canonical": True,
            })

            return {
                "new_level": new_level,
                "hp_gained": hp_gained,
                "new_features": new_features,
                "new_hp_max": new_hp_max,
                "new_prof_bonus": new_prof,
            }

        except Exception as e:
            logger.error(f"Failed to award XP: {e}")
            return None

    def _tick_survival_needs(self, context: GameContext) -> list[str]:
        """Tick survival needs forward one turn and return any warnings."""
        try:
            from text_rpg.mechanics.ability_scores import modifier
            from text_rpg.mechanics.survival import classify_need, tick_needs

            char = context.character
            char_id = char.get("id", "")
            if not char_id:
                return []

            # Get current needs (handle NULL from old saves)
            hunger = char.get("hunger") or 100
            thirst = char.get("thirst") or 100
            warmth = char.get("warmth") or 80
            morale = char.get("morale") or 75

            # Get climate from location
            climate = "temperate"
            loc = context.location
            if loc:
                props = safe_props(loc)
                climate = props.get("climate", "temperate")

            # Get CON modifier
            scores = safe_json(char.get("ability_scores"), {})
            con_mod = modifier(scores.get("constitution", 10))

            # Tick
            new_needs = tick_needs(hunger, thirst, warmth, morale, climate, con_mod)

            # Update DB
            for need_name, new_val in new_needs.items():
                old_val = char.get(need_name, 100)
                if new_val != old_val:
                    self.repos["character"].update_field(char_id, need_name, new_val)

            # Generate warnings for needs that just crossed a threshold
            warnings: list[str] = []
            for need_name in ("hunger", "thirst", "warmth", "morale"):
                old_val = char.get(need_name, 100) or 100
                new_val = new_needs[need_name]
                old_status = classify_need(need_name, old_val)
                new_status = classify_need(need_name, new_val)
                # Warn when crossing into a worse tier
                if new_status.penalty < old_status.penalty:
                    warnings.append(f"You feel {new_status.label.lower()}. ({need_name.title()}: {new_val}/100)")

            return warnings

        except Exception as e:
            logger.warning(f"Survival tick failed: {e}")
            return []

    def _tick_weakened_condition(self, context: GameContext, game_id: str) -> None:
        """Tick down the 'weakened' condition duration from death penalty."""
        try:
            char = context.character
            char_id = char.get("id", "")
            if not char_id:
                return

            wounds = safe_json(char.get("wounds"), [])

            # Find _weakened tracker
            weakened_entry = None
            for w in wounds:
                if w.get("type") == "_weakened":
                    weakened_entry = w
                    break

            if not weakened_entry:
                return

            remaining = weakened_entry.get("turns_remaining", 0) - 1
            if remaining <= 0:
                # Remove weakened
                wounds = [w for w in wounds if w.get("type") != "_weakened"]
                self.repos["character"].update_field(char_id, "wounds", json.dumps(wounds))
                # Remove weakened from conditions
                conditions = safe_json(char.get("conditions"), [])
                conditions = [c for c in conditions if c != "weakened"]
                self.repos["character"].update_field(char_id, "conditions", json.dumps(conditions))
                logger.info(f"Weakened condition expired for {char_id}")
            else:
                weakened_entry["turns_remaining"] = remaining
                self.repos["character"].update_field(char_id, "wounds", json.dumps(wounds))
        except Exception as e:
            logger.warning(f"Weakened tick failed: {e}")

    # -- Snapshot triggers --

    _SNAPSHOT_INTERVAL = 20  # Auto-snapshot every N turns

    def _maybe_snapshot(self, result: ActionResult, context: GameContext, game_id: str) -> None:
        """Create a snapshot if a trigger condition is met."""
        trigger = self._snapshot_trigger(result, context, game_id)
        if not trigger:
            return
        try:
            from text_rpg.engine.snapshots import StateSerializer

            snapshot_repo = self.repos.get("snapshot")
            if not snapshot_repo:
                return
            serializer = StateSerializer(self.repos)
            snapshot = serializer.capture(game_id, trigger)
            snapshot_repo.create_snapshot(snapshot)
            snapshot_repo.delete_old(game_id, keep_count=10)
            logger.info(f"Snapshot created: trigger={trigger}, turn={context.turn_number}")
        except Exception as e:
            logger.warning(f"Snapshot creation failed: {e}")

    def _snapshot_trigger(self, result: ActionResult, context: GameContext, game_id: str) -> str | None:
        """Determine if the current turn should trigger a snapshot.

        Returns the trigger type string, or None.
        """
        # After a successful long rest
        if result.action_type == "rest":
            rest_type = result.parameters.get("rest_type", "")
            if rest_type == "long":
                return "rest"

        # Region change — current_location_id mutation to a new region
        for m in (result.state_mutations or []):
            if m.target_type == "game" and m.field == "current_location_id":
                old_loc = context.location
                new_loc = self.repos["location"].get(m.new_value, game_id)
                if new_loc and old_loc.get("region_id") != new_loc.get("region_id"):
                    return "region"

        # Every N turns
        if context.turn_number > 0 and context.turn_number % self._SNAPSHOT_INTERVAL == 0:
            return "auto"

        return None
