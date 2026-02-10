"""ASCII map display — proximity-limited BFS tree with direction labels."""
from __future__ import annotations

from collections import deque
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel

from text_rpg.utils import safe_json
from rich.text import Text


# Maximum BFS depth to show on the map.
MAX_MAP_DEPTH = 3


def _get_connections(loc: dict) -> list[dict]:
    """Extract connections list from a location dict (handles JSON strings)."""
    connections = safe_json(loc.get("connections"), [])
    return [c for c in connections if isinstance(c, dict)]


# Short direction labels for compact display.
_DIR_SHORT: dict[str, str] = {
    "north": "N", "south": "S", "east": "E", "west": "W",
    "northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW",
    "up": "Up", "down": "Dn",
}


class MapDisplay:
    """Renders a proximity-limited map of visited locations and known exits."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(
        self,
        locations: list[dict],
        current_location_id: str,
        home_location_id: str | None = None,
        connection_repo: Any | None = None,
        game_id: str = "",
        total_locations: int | None = None,
    ) -> None:
        """Render the map as a Rich Panel with proximity-limited BFS tree.

        If connection_repo is provided, connections are fetched from the
        dedicated table. Otherwise falls back to embedded JSON in locations.
        """
        if not locations:
            self.console.print("[dim]No map data available.[/dim]")
            return

        loc_map: dict[str, dict] = {}
        for loc in locations:
            loc_map[loc.get("id", "")] = loc

        current = loc_map.get(current_location_id)
        if not current:
            self.console.print("[dim]Map unavailable for current location.[/dim]")
            return

        visited_ids = {loc["id"] for loc in locations if loc.get("visited")}

        # Build the connection graph: either from repo or from embedded JSON.
        # graph[loc_id] = [conn_dict, ...]
        graph: dict[str, list[dict]] = {}
        if connection_repo and game_id:
            try:
                graph = connection_repo.get_nearby_graph(
                    game_id, current_location_id, MAX_MAP_DEPTH,
                )
            except Exception:
                graph = {}

        # BFS from current location up to MAX_MAP_DEPTH.
        seen: set[str] = {current_location_id}
        # Each entry: (loc_id, depth, direction_from_parent)
        order: list[tuple[str, int, str]] = [(current_location_id, 0, "")]
        queue: deque[tuple[str, int]] = deque([(current_location_id, 0)])
        truncated = 0  # count of locations beyond the depth limit

        while queue:
            loc_id, depth = queue.popleft()

            # Get connections (prefer graph from repo, fall back to loc dict)
            if loc_id in graph:
                conns = graph[loc_id]
            else:
                loc = loc_map.get(loc_id)
                conns = _get_connections(loc) if loc else []

            for conn in conns:
                target_id = conn.get("target_location_id", "")
                direction = conn.get("direction", "?")
                if target_id in seen:
                    continue
                seen.add(target_id)

                if depth + 1 <= MAX_MAP_DEPTH:
                    order.append((target_id, depth + 1, direction))
                    # Only recurse further into visited locations
                    if target_id in visited_ids and depth + 1 < MAX_MAP_DEPTH:
                        queue.append((target_id, depth + 1))
                else:
                    truncated += 1

        # Summary stats
        shown_count = len(order)
        total = total_locations or len(locations)

        # Build text output
        content = Text()
        content.append("World Map", style="bold cyan")
        content.append(f"  ({shown_count} shown", style="dim")
        if total > shown_count:
            content.append(f" / {total} discovered", style="dim")
        content.append(")\n\n", style="dim")

        for loc_id, depth, direction in order:
            loc = loc_map.get(loc_id, {})
            is_current = loc_id == current_location_id
            is_visited = loc_id in visited_ids
            is_home = loc_id == home_location_id

            indent = "  " * depth

            # Direction arrow from parent
            if direction:
                dir_label = _DIR_SHORT.get(direction.lower(), direction)
                content.append(f"{indent}{dir_label} ", style="cyan")
                content.append("-> ", style="dim")
            else:
                content.append(indent)

            # Marker and name
            if is_current:
                marker = " * "
                name = loc.get("name", loc_id)
                style = "bold green"
            elif is_visited:
                marker = " o "
                name = loc.get("name", loc_id)
                style = "yellow"
            else:
                marker = " ? "
                name = "???"
                style = "dim"

            content.append(marker, style=style)
            content.append(name, style=style)

            if is_home:
                content.append(" H", style="bold magenta")

            content.append("\n")

        if truncated > 0:
            content.append(f"\n  ... and {truncated} more locations beyond range\n", style="dim italic")

        # Legend
        content.append("\n")
        content.append(" *  = You are here  ", style="bold green")
        content.append(" o  = Visited  ", style="yellow")
        content.append(" ?  = Undiscovered", style="dim")
        if home_location_id:
            content.append("  H = Your home", style="bold magenta")

        self.console.print(Panel(content, border_style="cyan", box=box.ROUNDED))
