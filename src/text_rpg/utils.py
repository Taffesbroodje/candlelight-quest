"""Shared utility functions for the Text RPG."""
from __future__ import annotations

import json


def safe_json(value, default=None):
    """Deserialize a JSON string if needed, or return default.

    Handles the common pattern where SQLite columns may contain JSON strings,
    Python objects, or NULL values.
    """
    if value is None:
        return default if default is not None else {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}
    return value


def safe_props(obj: dict) -> dict:
    """Safely extract and deserialize 'properties' from a DB row."""
    props = obj.get("properties") or {}
    return safe_json(props, {})
