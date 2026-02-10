"""Parse and validate LLM outputs."""
from __future__ import annotations

import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


class OutputParser:
    @staticmethod
    def parse_action_classification(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "action_type": raw.get("action_type", "custom").upper(),
            "target": raw.get("target"),
            "parameters": raw.get("parameters", {}),
            "confidence": min(1.0, max(0.0, float(raw.get("confidence", 0.5)))),
        }

    @staticmethod
    def parse_scene_plan(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "available_actions": raw.get("available_actions", []),
            "environmental_details": raw.get("environmental_details", []),
            "npc_intentions": raw.get("npc_intentions", {}),
            "tension_level": raw.get("tension_level", "low"),
        }

    @staticmethod
    def parse_narrative(raw: str) -> dict[str, Any]:
        text = raw.strip()
        hooks: list[str] = []
        hook_pattern = re.compile(r"\[HOOK:\s*(.+?)\]")
        for match in hook_pattern.finditer(text):
            hooks.append(match.group(1))
        clean_text = hook_pattern.sub("", text).strip()
        return {"narrative_text": clean_text, "suggested_hooks": hooks}

    @staticmethod
    def parse_dialogue(raw: str) -> dict[str, Any]:
        text = raw.strip()
        mood = "neutral"
        mood_match = re.match(r"\[(\w+)\]\s*", text)
        if mood_match:
            mood = mood_match.group(1).lower()
            text = text[mood_match.end():]
        return {"dialogue": text, "mood": mood}

    @staticmethod
    def extract_json_from_text(text: str) -> dict[str, Any] | None:
        text = text.strip()
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass
        brace_depth = 0
        start_idx = None
        for i, c in enumerate(text):
            if c == "{":
                if brace_depth == 0:
                    start_idx = i
                brace_depth += 1
            elif c == "}":
                brace_depth -= 1
                if brace_depth == 0 and start_idx is not None:
                    try:
                        return json.loads(text[start_idx : i + 1])
                    except json.JSONDecodeError:
                        start_idx = None
        return None
