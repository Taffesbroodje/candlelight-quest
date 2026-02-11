from __future__ import annotations
import tomllib
from pathlib import Path
from typing import Any

CONTENT_DIR = Path(__file__).parent

def load_toml(filepath: Path) -> dict[str, Any]:
    with open(filepath, "rb") as f:
        return tomllib.load(f)

def load_all_races() -> dict[str, dict]:
    races = {}
    race_dir = CONTENT_DIR / "races"
    for f in race_dir.glob("*.toml"):
        data = load_toml(f)
        races[data["id"]] = data
    return races

def load_all_classes() -> dict[str, dict]:
    classes = {}
    class_dir = CONTENT_DIR / "classes"
    for f in class_dir.glob("*.toml"):
        data = load_toml(f)
        classes[data["id"]] = data
    return classes

def load_all_spells() -> dict[str, dict]:
    spells = {}
    spell_dir = CONTENT_DIR / "spells"
    for f in spell_dir.glob("*.toml"):
        data = load_toml(f)
        for spell in data.get("spells", []):
            spells[spell["id"]] = spell
    return spells


def load_all_items() -> dict[str, dict]:
    items = {}
    items_dir = CONTENT_DIR / "items"
    for f in items_dir.glob("*.toml"):
        data = load_toml(f)
        for item in data.get("items", [data]):
            items[item["id"]] = item
    return items

def load_all_factions() -> dict[str, dict]:
    factions_file = CONTENT_DIR / "factions" / "factions.toml"
    if not factions_file.exists():
        return {}
    data = load_toml(factions_file)
    return {k: v for k, v in data.items() if isinstance(v, dict) and "name" in v}


def load_origins() -> list[dict[str, Any]]:
    """Deprecated: use load_all_origins() instead."""
    return load_all_origins()


def load_all_origins() -> list[dict[str, Any]]:
    """Load all origins from content/origins/*.toml directory.

    Each TOML file contains [[origins]] arrays. The filename (minus .toml)
    is used as the category if not specified in the origin data.
    """
    origins_dir = CONTENT_DIR / "origins"
    if not origins_dir.exists():
        return []
    all_origins: list[dict[str, Any]] = []
    for f in sorted(origins_dir.glob("*.toml")):
        category = f.stem
        data = load_toml(f)
        for origin in data.get("origins", []):
            if "category" not in origin:
                origin["category"] = category
            all_origins.append(origin)
    return all_origins


def filter_origins(
    origins: list[dict[str, Any]],
    race: str,
    char_class: str,
) -> list[dict[str, Any]]:
    """Filter origins to those available for a given race and class."""
    available = []
    for origin in origins:
        req_races = origin.get("required_races", [])
        exc_races = origin.get("excluded_races", [])
        req_classes = origin.get("required_classes", [])
        exc_classes = origin.get("excluded_classes", [])
        if req_races and race not in req_races:
            continue
        if race in exc_races:
            continue
        if req_classes and char_class not in req_classes:
            continue
        if char_class in exc_classes:
            continue
        available.append(origin)
    return available


def load_all_story_seeds() -> list[dict[str, Any]]:
    """Load all story seeds from content/stories/."""
    from text_rpg.mechanics.story_seeds import load_all_seeds
    return load_all_seeds()


def load_world_events() -> list[dict[str, Any]]:
    """Load world events from content/stories/world_events.toml."""
    events_file = CONTENT_DIR / "stories" / "world_events.toml"
    if not events_file.exists():
        return []
    data = load_toml(events_file)
    return data.get("events", [])


def load_all_regions() -> dict[str, dict[str, Any]]:
    """Load all region metadata (id, name, level ranges) without full location data."""
    regions: dict[str, dict[str, Any]] = {}
    regions_dir = CONTENT_DIR / "regions"
    if not regions_dir.exists():
        return regions
    for d in sorted(regions_dir.iterdir()):
        region_file = d / "region.toml"
        if d.is_dir() and region_file.exists():
            data = load_toml(region_file)
            regions[data["id"]] = data
    return regions


def load_all_guilds() -> dict[str, dict]:
    """Load all guild definitions from content/guilds/guilds.toml."""
    guilds_file = CONTENT_DIR / "guilds" / "guilds.toml"
    if not guilds_file.exists():
        return {}
    data = load_toml(guilds_file)
    return {k: v for k, v in data.items() if isinstance(v, dict) and "name" in v}


def load_work_order_templates() -> list[dict[str, Any]]:
    """Load work order templates from content/guilds/work_orders.toml."""
    orders_file = CONTENT_DIR / "guilds" / "work_orders.toml"
    if not orders_file.exists():
        return []
    data = load_toml(orders_file)
    return data.get("orders", [])


def load_region(region_id: str) -> dict[str, Any]:
    region_dir = CONTENT_DIR / "regions" / region_id
    region_data = load_toml(region_dir / "region.toml")
    region_data["locations"] = []
    locs_file = region_dir / "locations.toml"
    if locs_file.exists():
        loc_data = load_toml(locs_file)
        region_data["locations"] = loc_data.get("locations", [])
    npcs_file = region_dir / "npcs.toml"
    if npcs_file.exists():
        npc_data = load_toml(npcs_file)
        region_data["npcs"] = npc_data.get("npcs", [])
    quests_file = region_dir / "quests.toml"
    if quests_file.exists():
        quest_data = load_toml(quests_file)
        region_data["quests"] = quest_data.get("quests", [])
    encounters_file = region_dir / "encounters.toml"
    if encounters_file.exists():
        enc_data = load_toml(encounters_file)
        region_data["encounters"] = enc_data.get("encounters", [])
    shops_file = region_dir / "shops.toml"
    if shops_file.exists():
        shops_data = load_toml(shops_file)
        region_data["shops"] = shops_data.get("shops", [])
    return region_data
