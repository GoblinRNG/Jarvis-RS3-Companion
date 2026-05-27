"""Tests for game_state utilities (pure-logic and stub paths)."""

from __future__ import annotations

import time

import pytest

from openjarvis.rs3.game_state import (
    GameState,
    PlayerStats,
    minutes_until_reset,
)


class TestMinutesUntilReset:
    def test_returns_int(self):
        result = minutes_until_reset()
        assert isinstance(result, int)

    def test_within_day_range(self):
        result = minutes_until_reset()
        assert 0 <= result <= 1440


class TestGameState:
    def test_to_context_dict_has_expected_keys(self):
        state = GameState()
        d = state.to_context_dict()
        assert "player_stats" in d
        assert "equipment" in d
        assert "location" in d
        assert "dailies_state" in d
        assert "ge_prices" in d
        assert "preferences" in d
        assert "time" in d

    def test_time_field_has_utc_and_minutes(self):
        state = GameState()
        d = state.to_context_dict()
        assert "utc" in d["time"]
        assert "minutes_to_reset" in d["time"]

    def test_default_location(self):
        state = GameState()
        assert state.location == "Unknown"

    def test_preferences_round_trip(self):
        state = GameState(preferences={"ironman": True, "honorific": "sir"})
        d = state.to_context_dict()
        assert d["preferences"]["ironman"] is True


class TestGameStateCollector:
    def test_collect_returns_dict(self):
        from openjarvis.rs3.config import RS3Config
        from openjarvis.rs3.game_state import GameStateCollector
        cfg = RS3Config.default()
        collector = GameStateCollector(cfg)
        result = collector.collect()
        assert isinstance(result, dict)
        assert "preferences" in result

    def test_collect_includes_honorific(self):
        from openjarvis.rs3.config import RS3Config
        from openjarvis.rs3.game_state import GameStateCollector
        cfg = RS3Config.default()
        collector = GameStateCollector(cfg)
        result = collector.collect()
        assert result["preferences"]["honorific"] == "sir"
