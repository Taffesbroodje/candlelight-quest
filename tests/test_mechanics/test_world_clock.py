"""Tests for src/text_rpg/mechanics/world_clock.py."""
from __future__ import annotations

import pytest

from text_rpg.mechanics.world_clock import (
    MINUTES_PER_DAY,
    MINUTES_PER_TURN,
    advance,
    format_short,
    format_time,
    get_day,
    get_hour,
    get_minute,
    get_period,
    is_daytime,
)


class TestAdvance:
    def test_one_turn(self):
        assert advance(100, 1) == 110

    def test_multiple_turns(self):
        assert advance(0, 5) == 50

    def test_zero_turns(self):
        assert advance(100, 0) == 100


class TestGetDay:
    @pytest.mark.parametrize("minutes, expected", [
        (0, 1), (1439, 1), (1440, 2), (2880, 3), (7200, 6),
    ])
    def test_day_boundaries(self, minutes, expected):
        assert get_day(minutes) == expected


class TestGetHour:
    @pytest.mark.parametrize("minutes, expected", [
        (0, 0), (60, 1), (480, 8), (720, 12), (1380, 23), (1439, 23),
    ])
    def test_hour_values(self, minutes, expected):
        assert get_hour(minutes) == expected


class TestGetPeriod:
    @pytest.mark.parametrize("minutes, expected", [
        (0, "late_night"),           # hour 0
        (4 * 60, "late_night"),      # hour 4
        (5 * 60, "dawn"),            # hour 5
        (7 * 60 + 59, "dawn"),       # hour 7:59
        (8 * 60, "morning"),         # hour 8
        (12 * 60, "midday"),         # hour 12
        (14 * 60, "afternoon"),      # hour 14
        (17 * 60, "evening"),        # hour 17
        (20 * 60, "night"),          # hour 20
        (23 * 60, "late_night"),     # hour 23
    ])
    def test_period_boundaries(self, minutes, expected):
        assert get_period(minutes) == expected


class TestIsDaytime:
    @pytest.mark.parametrize("minutes, expected", [
        (5 * 60, False),     # hour 5 — not yet daytime
        (6 * 60, True),      # hour 6 — daytime starts
        (12 * 60, True),     # noon
        (19 * 60 + 59, True),  # hour 19:59 — still daytime
        (20 * 60, False),    # hour 20 — night
        (0, False),          # midnight
    ])
    def test_daytime_boundaries(self, minutes, expected):
        assert is_daytime(minutes) == expected


class TestFormatTime:
    @pytest.mark.parametrize("minutes, expected", [
        (480, "Morning, Day 1 (08:00)"),
        (750, "Midday, Day 1 (12:30)"),
        (1500, "Late Night, Day 2 (01:00)"),
    ])
    def test_format_examples(self, minutes, expected):
        assert format_time(minutes) == expected


class TestFormatShort:
    def test_basic(self):
        assert format_short(480) == "Morning, Day 1"
