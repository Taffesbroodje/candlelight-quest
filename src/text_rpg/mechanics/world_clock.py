"""World clock — tracks in-game time. Each player turn = ~10 minutes."""
from __future__ import annotations

MINUTES_PER_TURN = 10
MINUTES_PER_DAY = 1440  # 24 * 60

# Period boundaries: (start_hour, end_hour_exclusive)
_PERIODS = [
    (5, 8, "dawn"),
    (8, 12, "morning"),
    (12, 14, "midday"),
    (14, 17, "afternoon"),
    (17, 20, "evening"),
    (20, 23, "night"),
    # late_night wraps: 23-5
]

ALL_PERIODS = ("dawn", "morning", "midday", "afternoon", "evening", "night", "late_night")


def advance(current_minutes: int, turns: int = 1) -> int:
    """Advance the clock by *turns* turns. Returns new total minutes."""
    return current_minutes + turns * MINUTES_PER_TURN


def get_day(total_minutes: int) -> int:
    """Day number (1-based)."""
    return (total_minutes // MINUTES_PER_DAY) + 1


def get_hour(total_minutes: int) -> int:
    """Hour of day (0-23)."""
    return (total_minutes % MINUTES_PER_DAY) // 60


def get_minute(total_minutes: int) -> int:
    """Minute within the hour (0-59)."""
    return total_minutes % 60


def get_period(total_minutes: int) -> str:
    """Return the current time period name."""
    hour = get_hour(total_minutes)
    for start, end, name in _PERIODS:
        if start <= hour < end:
            return name
    return "late_night"  # 23-4


def is_daytime(total_minutes: int) -> bool:
    """True between 6:00 and 20:00."""
    hour = get_hour(total_minutes)
    return 6 <= hour < 20


def format_time(total_minutes: int) -> str:
    """Human-readable time string, e.g. 'Morning, Day 2 (8:30)'."""
    period = get_period(total_minutes).replace("_", " ").title()
    day = get_day(total_minutes)
    hour = get_hour(total_minutes)
    minute = get_minute(total_minutes)
    return f"{period}, Day {day} ({hour:02d}:{minute:02d})"


def format_short(total_minutes: int) -> str:
    """Short format, e.g. 'Morning, Day 2'."""
    period = get_period(total_minutes).replace("_", " ").title()
    day = get_day(total_minutes)
    return f"{period}, Day {day}"
