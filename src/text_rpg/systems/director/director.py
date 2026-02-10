"""Main Director class — post-turn evaluator that generates living world content."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from text_rpg.llm.provider import LLMProvider
from text_rpg.models.action import Action, ActionResult, DiceRoll, StateMutation
from text_rpg.rag.indexer import Indexer
from text_rpg.rag.retriever import Retriever
from text_rpg.systems.base import GameContext
from text_rpg.systems.director import triggers
from text_rpg.utils import safe_json
from text_rpg.systems.director.schemas import validate_plausibility

logger = logging.getLogger(__name__)

# Cooldowns: minimum turns between generation types
_COOLDOWNS: dict[str, int] = {
    "npc": 5,
    "location": 3,
    "quest": 8,
    "enrich": 6,
    "pacing": 10,
    "story": 15,
    "faction_goals": 15,
    "world_event": 5,
}


class Director:
    """Post-turn evaluator that injects procedural content into the world.

    NOT a GameSystem — called from the turn loop after mutations are applied.
    Generated content becomes visible on the *next* turn.
    """

    def __init__(
        self,
        llm: LLMProvider,
        retriever: Retriever,
        indexer: Indexer,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.indexer = indexer
        # Track last generation turn per type to enforce cooldowns
        self._last_generation: dict[str, int] = {}

    def evaluate(
        self,
        context: GameContext,
        action_result: ActionResult,
        repos: dict[str, Any],
    ) -> list[dict]:
        """Called every turn after mutations are applied.

        Returns a list of event dicts to record (may be empty).
        At most one generation per turn.
        """
        events: list[dict] = []

        # 1. Check for quest follow-ups on completed quests
        for event in action_result.events:
            if event.get("event_type") == "QUEST_COMPLETE":
                quest_id = event.get("target_id")
                if quest_id:
                    quest = repos["world_state"].get_quest(quest_id, context.game_id)
                    if quest and triggers.should_generate_follow_up(quest, context):
                        result = self._try_generate_follow_up(quest, context, repos)
                        if result:
                            events.append(result)
                            return events

        # 2. Should we spawn an NPC?
        if self._can_generate("npc", context.turn_number):
            if triggers.should_spawn_npc(context, repos):
                result = self._try_generate_npc(context, repos)
                if result:
                    events.append(result)
                    return events

        # 3. Should we offer a quest from an existing NPC?
        if self._can_generate("quest", context.turn_number):
            for entity in context.entities:
                if entity.get("entity_type") == "npc" and entity.get("is_alive", True):
                    if triggers.should_offer_quest(entity, context):
                        result = self._try_prepare_quest(entity, context, repos)
                        if result:
                            events.append(result)
                            return events

        # 4. Should we enrich the location?
        if self._can_generate("enrich", context.turn_number):
            if triggers.should_enrich_location(context):
                result = self._try_enrich_location(context, repos)
                if result:
                    events.append(result)
                    return events

        # 5. Pacing check — seed hooks every N turns
        if self._can_generate("pacing", context.turn_number):
            if triggers.pacing_check(context):
                result = self._try_seed_hooks(context, repos)
                if result:
                    events.append(result)
                    return events

        # 6. Story progression — check story seed beats
        story_events = self._check_story_progression(context, repos)
        if story_events:
            events.extend(story_events)

        # 7. Faction goals — autonomous faction actions
        if self._can_generate("faction_goals", context.turn_number):
            faction_events = self._check_faction_goals(context, repos)
            if faction_events:
                events.extend(faction_events)
                self._last_generation["faction_goals"] = context.turn_number

        # 8. World events — random ambient events
        if self._can_generate("world_event", context.turn_number):
            world_events = self._check_world_events(context, repos)
            if world_events:
                events.extend(world_events)
                self._last_generation["world_event"] = context.turn_number

        return events

    def evaluate_plausibility(
        self,
        action: Action,
        context: GameContext,
    ) -> dict:
        """Evaluate how plausible a creative/unhandled player action is.

        Returns dict with: plausibility, skill, ability, reasoning,
        success_description, failure_description.
        """
        from text_rpg.systems.director.generators import evaluate_plausibility

        return evaluate_plausibility(self.llm, action.raw_input, context)

    def generate_creative_outcome(
        self,
        action: Action,
        context: GameContext,
        plausibility: dict,
        repos: dict[str, Any],
    ) -> ActionResult:
        """Generate the outcome of a successful creative action.

        May produce new locations, items, or NPC reactions depending on context.
        """
        description = plausibility.get("success_description", "You succeed against the odds.")
        events = [{
            "event_type": "CREATIVE_ACTION",
            "description": f"Creative action: {action.raw_input} — {description}",
            "actor_id": context.character.get("id"),
            "location_id": context.location.get("id"),
        }]

        return ActionResult(
            action_id=action.id,
            success=True,
            outcome_description=description,
            events=events,
        )

    def generate_location_for_direction(
        self,
        direction: str,
        context: GameContext,
        repos: dict[str, Any],
    ) -> dict | None:
        """Generate a new location when the player discovers an unknown path.

        Returns the new location dict (already saved to DB) or None on failure.
        """
        from text_rpg.systems.director.generators import generate_location

        try:
            location_data = generate_location(
                self.llm, context, direction, context.location,
            )
        except Exception as e:
            logger.warning(f"Location generation failed: {e}")
            return None

        source_loc_id = context.location.get("id", "")
        new_loc_id = location_data["id"]

        # Set game_id and region
        location_data["game_id"] = context.game_id
        location_data["region_id"] = context.location.get("region_id", "")

        # Save new location (without embedded connections)
        location_data["connections"] = json.dumps([])
        repos["location"].save(_serialize_location(location_data))

        # Create bidirectional connections in dedicated table
        reverse_dir = _reverse_direction(direction)
        conn_repo = repos.get("connection")
        if conn_repo:
            conn_repo.add_bidirectional(
                game_id=context.game_id,
                source_id=source_loc_id,
                target_id=new_loc_id,
                direction=direction,
                reverse_direction=reverse_dir,
                description=location_data.get("name", "a new area"),
                back_description=context.location.get("name", "the way back"),
            )
        else:
            # Fallback: update embedded JSON (legacy path)
            back_conn = {
                "direction": reverse_dir,
                "target_location_id": source_loc_id,
                "description": context.location.get("name", "the way back"),
                "is_locked": False,
            }
            new_conns = safe_json(location_data.get("connections"), [])
            new_conns.append(back_conn)
            repos["location"].update_field(new_loc_id, context.game_id, "connections", new_conns)

            src_conns = safe_json(context.location.get("connections"), [])
            src_conns.append({
                "direction": direction,
                "target_location_id": new_loc_id,
                "description": location_data.get("name", "a new area"),
                "is_locked": False,
            })
            repos["location"].update_field(source_loc_id, context.game_id, "connections", src_conns)

        # Optionally generate NPCs for the new location
        self._populate_new_location(location_data, context, repos)

        # Index to RAG
        try:
            self.indexer.index_lore(
                f"Location discovered: {location_data['name']} — {location_data.get('description', '')}",
                category="location",
                tags={"game_id": context.game_id, "location_id": new_loc_id},
            )
        except Exception:
            pass

        self._last_generation["location"] = context.turn_number
        return location_data

    # -- Private generation methods --

    def _can_generate(self, gen_type: str, turn_number: int) -> bool:
        """Check cooldown for a generation type."""
        last = self._last_generation.get(gen_type, -999)
        cooldown = _COOLDOWNS.get(gen_type, 5)
        return (turn_number - last) >= cooldown

    def _try_generate_npc(
        self, context: GameContext, repos: dict[str, Any]
    ) -> dict | None:
        """Attempt to generate and save a new NPC at the current location."""
        from text_rpg.systems.director.generators import generate_npc

        try:
            npc_data = generate_npc(self.llm, context, context.location, {})
        except Exception as e:
            logger.warning(f"NPC generation failed: {e}")
            return None

        npc_data["game_id"] = context.game_id
        npc_data["location_id"] = context.location.get("id", "")

        repos["entity"].save(_serialize_entity(npc_data))

        # Index to RAG
        try:
            self.indexer.index_npc_fact(
                context.game_id,
                npc_data["id"],
                npc_data["name"],
                f"New NPC appeared: {npc_data.get('description', '')}",
            )
        except Exception:
            pass

        self._last_generation["npc"] = context.turn_number
        return {
            "event_type": "DIRECTOR_NPC_SPAWN",
            "description": f"A new figure appears: {npc_data['name']}.",
            "target_id": npc_data["id"],
            "location_id": context.location.get("id"),
        }

    def _try_prepare_quest(
        self, npc: dict, context: GameContext, repos: dict[str, Any]
    ) -> dict | None:
        """Generate a quest from an NPC's quest hook and save it."""
        from text_rpg.systems.director.generators import generate_quest

        try:
            quest_data = generate_quest(self.llm, context, npc)
        except Exception as e:
            logger.warning(f"Quest generation failed: {e}")
            return None

        quest_data["game_id"] = context.game_id
        quest_data["quest_giver_id"] = npc.get("id", "")

        repos["world_state"].save_quest(_serialize_quest(quest_data))

        # Index to RAG
        try:
            self.indexer.index_lore(
                f"Quest available: {quest_data['name']} — {quest_data.get('description', '')}",
                category="quest",
                tags={"game_id": context.game_id, "quest_id": quest_data["id"]},
            )
        except Exception:
            pass

        self._last_generation["quest"] = context.turn_number
        return {
            "event_type": "DIRECTOR_QUEST_AVAILABLE",
            "description": f"{npc['name']} seems to have something on their mind.",
            "target_id": quest_data["id"],
            "location_id": context.location.get("id"),
            "mechanical_details": {
                "quest_name": quest_data.get("name", ""),
                "quest_description": quest_data.get("description", ""),
                "quest_giver": npc.get("name", ""),
            },
        }

    def _try_generate_follow_up(
        self, completed_quest: dict, context: GameContext, repos: dict[str, Any]
    ) -> dict | None:
        """Generate a follow-up quest after completion."""
        from text_rpg.systems.director.generators import generate_follow_up_quest

        try:
            quest_data = generate_follow_up_quest(self.llm, context, completed_quest)
        except Exception as e:
            logger.warning(f"Follow-up quest generation failed: {e}")
            return None

        quest_data["game_id"] = context.game_id
        quest_data["quest_giver_id"] = completed_quest.get("quest_giver_id", "")

        repos["world_state"].save_quest(_serialize_quest(quest_data))

        self._last_generation["quest"] = context.turn_number
        return {
            "event_type": "DIRECTOR_QUEST_FOLLOW_UP",
            "description": "A new opportunity arises from your completed quest.",
            "target_id": quest_data["id"],
            "location_id": context.location.get("id"),
            "mechanical_details": {
                "quest_name": quest_data.get("name", ""),
                "quest_description": quest_data.get("description", ""),
            },
        }

    def _try_enrich_location(
        self, context: GameContext, repos: dict[str, Any]
    ) -> dict | None:
        """Add flavour to an empty location — perhaps an NPC or item."""
        result = self._try_generate_npc(context, repos)
        if result:
            self._last_generation["enrich"] = context.turn_number
            return result
        return None

    def _try_seed_hooks(
        self, context: GameContext, repos: dict[str, Any]
    ) -> dict | None:
        """Pacing check — save an intent for future content."""
        # Check bounty level for tension context
        bounty_amount = 0
        rep_repo = repos.get("reputation")
        if rep_repo:
            region_id = context.location.get("region_id", "")
            if region_id:
                bounty = rep_repo.get_bounty(context.game_id, region_id)
                bounty_amount = bounty.get("amount", 0)

        intent = {
            "id": str(uuid.uuid4()),
            "game_id": context.game_id,
            "intent_type": "seed_hook",
            "description": "Director pacing review — world may need new content.",
            "data": {
                "turn_number": context.turn_number,
                "location_id": context.location.get("id"),
                "character_level": context.character.get("level", 1),
                "bounty_amount": bounty_amount,
                "loop_count": getattr(context, "loop_count", 0),
                "deja_vu": getattr(context, "loop_count", 0) > 0,
            },
            "is_active": True,
        }
        try:
            repos["intent"].save(intent)
        except Exception as e:
            logger.warning(f"Failed to save pacing intent: {e}")

        self._last_generation["pacing"] = context.turn_number
        return None  # Intents are silent — no event

    def _check_faction_goals(
        self, context: GameContext, repos: dict[str, Any]
    ) -> list[dict]:
        """Check and resolve faction goal outcomes."""
        from text_rpg.content.loader import load_all_factions
        from text_rpg.mechanics.faction_goals import apply_goal_effects, check_faction_goals

        try:
            factions = load_all_factions()
            events = check_faction_goals(factions, context.turn_number)

            for event in events:
                details = event.get("mechanical_details", {})
                effects = details.get("effects", [])
                if effects:
                    apply_goal_effects(effects, context.game_id, repos)

                # Index to RAG
                try:
                    self.indexer.index_event(
                        context.game_id,
                        "FACTION_GOAL",
                        event.get("description", ""),
                        location_id=context.location.get("id"),
                        turn_number=context.turn_number,
                    )
                except Exception:
                    pass

            return events
        except Exception as e:
            logger.warning(f"Faction goals check failed: {e}")
            return []

    def _check_world_events(
        self, context: GameContext, repos: dict[str, Any]
    ) -> list[dict]:
        """Check and trigger random world events."""
        from text_rpg.content.loader import load_world_events
        from text_rpg.mechanics.faction_goals import check_world_events

        try:
            events_pool = load_world_events()
            if not events_pool:
                return []

            loc_type = context.location.get("location_type", "wilderness")

            # Get cooldowns from DB
            cooldowns: dict[str, int] = {}
            for event in events_pool:
                eid = event.get("id", "")
                if eid:
                    last = repos["world_state"].get_event_cooldown(context.game_id, eid)
                    if last:
                        cooldowns[eid] = last

            triggered = check_world_events(
                events_pool, context.turn_number, context.world_time, loc_type, cooldowns
            )

            result_events: list[dict] = []
            for event in triggered:
                eid = event.get("id", "")
                # Save cooldown
                repos["world_state"].set_event_cooldown(
                    context.game_id, eid, context.turn_number
                )

                result_events.append({
                    "event_type": "WORLD_EVENT",
                    "description": event.get("narrator_hint", event.get("description", "")),
                    "location_id": context.location.get("id"),
                    "mechanical_details": {
                        "event_id": eid,
                        "event_description": event.get("description", ""),
                    },
                })

            return result_events
        except Exception as e:
            logger.warning(f"World events check failed: {e}")
            return []

    def _check_story_progression(
        self, context: GameContext, repos: dict[str, Any]
    ) -> list[dict]:
        """Check and advance story seed progression.

        - Activates new stories if none are active (after turn 5)
        - Advances existing stories when beat triggers are met
        - Max 2 concurrent active stories
        """
        from text_rpg.mechanics.story_seeds import (
            check_beat_trigger,
            get_narrator_hints,
            load_all_seeds,
            next_beat,
            resolve_variables,
            select_seed,
        )

        events: list[dict] = []

        try:
            active_stories = repos["world_state"].get_active_stories(context.game_id)
            completed_ids = repos["world_state"].get_completed_story_ids(context.game_id)
            all_seeds = load_all_seeds()
            seed_map = {s["id"]: s for s in all_seeds}

            # -- Advance existing stories --
            for story in active_stories:
                seed_id = story.get("seed_id", "")
                seed = seed_map.get(seed_id)
                if not seed:
                    continue

                current_beat = story.get("current_beat", "hook")
                nxt = next_beat(current_beat)
                if not nxt:
                    continue  # At resolution, wait for quest completion

                beat_def = seed.get(nxt, {})
                if not beat_def:
                    continue

                # Build game state for trigger check
                completed_quest_ids = []
                for q in repos["world_state"].get_all_quests(context.game_id):
                    if q.get("status") == "completed":
                        completed_quest_ids.append(q["id"])

                game_state = {
                    "turn_number": context.turn_number,
                    "character_level": context.character.get("level", 1),
                    "completed_quest_ids": completed_quest_ids,
                }

                story_state = {
                    "current_beat": current_beat,
                    "beat_turn_numbers": story.get("beat_turn_numbers") or {},
                    "quest_ids": story.get("quest_ids") or [],
                }

                if check_beat_trigger(beat_def, story_state, game_state):
                    # Advance to next beat
                    activated = safe_json(story.get("activated_beats"), [])
                    activated.append(nxt)

                    quest_ids = safe_json(story.get("quest_ids"), [])

                    beat_turns = safe_json(story.get("beat_turn_numbers"), {})
                    beat_turns[nxt] = context.turn_number

                    # Generate a quest for this beat if it has a template
                    quest_template = beat_def.get("quest_template")
                    if quest_template:
                        quest_event = self._generate_story_quest(
                            seed, nxt, story, quest_template, context, repos
                        )
                        if quest_event:
                            quest_id = quest_event.get("target_id", "")
                            if quest_id:
                                quest_ids.append(quest_id)
                            events.append(quest_event)

                    repos["world_state"].update_story_beat(
                        context.game_id, seed_id, nxt, activated, quest_ids,
                    )

                    # Update beat_turn_numbers in story data
                    story_data = repos["world_state"].get_story_state(context.game_id, seed_id)
                    if story_data:
                        data = safe_json(story_data.get("data"), {})
                        data["beat_turn_numbers"] = beat_turns
                        repos["world_state"].save_story_state({
                            **story_data,
                            "beat_turn_numbers": beat_turns,
                        })

                    seed_name = seed.get("name", seed_id)
                    events.append({
                        "event_type": "STORY_BEAT",
                        "description": f"Story '{seed_name}' advances to {nxt}.",
                        "actor_id": context.character.get("id"),
                        "location_id": context.location.get("id"),
                        "mechanical_details": {
                            "story_name": seed_name,
                            "beat_name": nxt,
                            "seed_id": seed_id,
                        },
                    })

            # -- Activate new stories --
            if len(active_stories) < 2 and context.turn_number >= 5:
                # Check cooldown: don't activate too often
                last_activation = self._last_generation.get("story", -999)
                if (context.turn_number - last_activation) >= 15:
                    active_tags = []
                    for s in active_stories:
                        sid = s.get("seed_id", "")
                        sd = seed_map.get(sid, {})
                        active_tags.extend(sd.get("tags", []))

                    game_state = {
                        "turn_number": context.turn_number,
                        "character_level": context.character.get("level", 1),
                    }

                    selected = select_seed(all_seeds, game_state, completed_ids, active_tags)
                    if selected:
                        variables = resolve_variables(selected, context)
                        story_id = f"{context.game_id}_{selected['id']}"

                        repos["world_state"].save_story_state({
                            "id": story_id,
                            "game_id": context.game_id,
                            "seed_id": selected["id"],
                            "status": "active",
                            "current_beat": "hook",
                            "resolved_variables": variables,
                            "activated_beats": ["hook"],
                            "beat_turn_numbers": {"hook": context.turn_number},
                            "quest_ids": [],
                            "data": {},
                        })

                        # Generate hook quest if template exists
                        hook = selected.get("hook", {})
                        quest_template = hook.get("quest_template")
                        if quest_template:
                            quest_event = self._generate_story_quest(
                                selected, "hook",
                                {"resolved_variables": variables, "seed_id": selected["id"]},
                                quest_template, context, repos,
                            )
                            if quest_event:
                                quest_id = quest_event.get("target_id", "")
                                if quest_id:
                                    repos["world_state"].update_story_beat(
                                        context.game_id, selected["id"],
                                        "hook", ["hook"], [quest_id],
                                    )
                                events.append(quest_event)

                        self._last_generation["story"] = context.turn_number

                        seed_name = selected.get("name", selected["id"])
                        events.append({
                            "event_type": "STORY_BEAT",
                            "description": f"A new story begins: '{seed_name}'.",
                            "actor_id": context.character.get("id"),
                            "location_id": context.location.get("id"),
                            "mechanical_details": {
                                "story_name": seed_name,
                                "beat_name": "hook",
                                "seed_id": selected["id"],
                            },
                        })

        except Exception as e:
            logger.warning(f"Story progression check failed: {e}")

        return events

    def _generate_story_quest(
        self,
        seed: dict,
        beat_name: str,
        story: dict,
        quest_template: dict,
        context: GameContext,
        repos: dict[str, Any],
    ) -> dict | None:
        """Generate a quest from a story beat's quest_template."""
        from text_rpg.mechanics.story_seeds import fill_template
        from text_rpg.systems.director.generators import generate_quest

        variables = safe_json(story.get("resolved_variables"), {})

        # Build a synthetic NPC for quest generation
        quest_type = quest_template.get("type", "investigate")
        target = quest_template.get("target", "")
        report_to = quest_template.get("report_to", "")

        # Resolve target and report_to from variables
        target_name = variables.get(target, target.replace("_", " "))
        report_to_name = variables.get(report_to, report_to.replace("_", " "))

        seed_name = seed.get("name", "Unknown")
        beat_desc = f"Story: {seed_name}, Beat: {beat_name}"

        # Find an NPC to be the quest giver
        quest_giver_id = variables.get(f"{report_to}_id", "")
        if not quest_giver_id:
            # Find first available NPC
            for e in context.entities:
                if e.get("entity_type") == "npc" and e.get("is_alive", True):
                    quest_giver_id = e.get("id", "")
                    break

        try:
            # Use Director's quest generator with story context
            quest_data = generate_quest(self.llm, context, {
                "name": report_to_name,
                "description": f"Quest giver for {seed_name}",
                "id": quest_giver_id,
                "dialogue_tags": ["concerned", "urgent"],
                "properties": json.dumps({
                    "motivation": beat_desc,
                    "quest_hook": f"A {quest_type} task related to {target_name}. {seed.get('description_template', '')}",
                }),
            })
        except Exception as e:
            logger.warning(f"Story quest generation failed: {e}")
            return None

        quest_data["game_id"] = context.game_id
        quest_data["quest_giver_id"] = quest_giver_id

        repos["world_state"].save_quest(_serialize_quest(quest_data))

        # Index to RAG
        try:
            self.indexer.index_lore(
                f"Story quest: {quest_data['name']} — {quest_data.get('description', '')}",
                category="quest",
                tags={"game_id": context.game_id, "quest_id": quest_data["id"]},
            )
        except Exception:
            pass

        self._last_generation["quest"] = context.turn_number
        return {
            "event_type": "DIRECTOR_QUEST_AVAILABLE",
            "description": f"A new quest emerges from the story: {quest_data.get('name', '')}",
            "target_id": quest_data["id"],
            "location_id": context.location.get("id"),
            "mechanical_details": {
                "quest_name": quest_data.get("name", ""),
                "quest_description": quest_data.get("description", ""),
                "quest_giver": report_to_name,
            },
        }

    def _populate_new_location(
        self, location_data: dict, context: GameContext, repos: dict[str, Any]
    ) -> None:
        """Optionally add 0-1 NPCs to a newly generated location."""
        loc_type = location_data.get("location_type", "wilderness")
        # Towns/settlements are more likely to have NPCs
        if loc_type in ("town", "village", "settlement", "tavern", "shop"):
            from text_rpg.systems.director.generators import generate_npc
            try:
                npc_data = generate_npc(
                    self.llm, context, location_data, {},
                )
                npc_data["game_id"] = context.game_id
                npc_data["location_id"] = location_data["id"]
                repos["entity"].save(_serialize_entity(npc_data))
            except Exception as e:
                logger.debug(f"Failed to populate new location with NPC: {e}")


# -- Serialization helpers --

def _serialize_entity(data: dict) -> dict:
    """Prepare entity dict for DB storage."""
    out = dict(data)
    for field in ("ability_scores", "attacks", "behaviors", "dialogue_tags", "loot_table", "properties"):
        if field in out and out[field] is not None and not isinstance(out[field], str):
            out[field] = json.dumps(out[field])
    return out


def _serialize_location(data: dict) -> dict:
    """Prepare location dict for DB storage."""
    out = dict(data)
    for field in ("connections", "entities", "items", "properties"):
        if field in out and out[field] is not None and not isinstance(out[field], str):
            out[field] = json.dumps(out[field])
    return out


def _serialize_quest(data: dict) -> dict:
    """Prepare quest dict for DB storage."""
    out = dict(data)
    for field in ("objectives", "item_rewards"):
        if field in out and out[field] is not None and not isinstance(out[field], str):
            out[field] = json.dumps(out[field])
    return out


def _reverse_direction(direction: str) -> str:
    """Return the opposite compass direction."""
    opposites = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "up": "down", "down": "up",
    }
    return opposites.get(direction.lower(), "back")
