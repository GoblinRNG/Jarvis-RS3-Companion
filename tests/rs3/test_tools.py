"""Tests for RS3 tool implementations (DB-backed and pure-logic tools)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from openjarvis.rs3.db.schema import init_db
from openjarvis.rs3.db.seed_data import seed_all
from openjarvis.rs3.tools.training import lookup_training_method
from openjarvis.rs3.tools.money_making import get_money_making
from openjarvis.rs3.tools.quest import check_quest_eligibility
from openjarvis.rs3.tools.xp_calc import compute_xp_gap, xp_for_level


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = init_db(tmp_path / "rs3.db")
    seed_all(path)
    return path


# ── Training methods ──────────────────────────────────────────────────────────

class TestLookupTrainingMethod:
    def test_slayer_at_95_returns_results(self, db: Path):
        rows = lookup_training_method(db, "slayer", 95)
        assert len(rows) > 0

    def test_results_have_required_keys(self, db: Path):
        rows = lookup_training_method(db, "slayer", 95)
        assert rows
        for row in rows:
            assert "method_name" in row
            assert "xp_per_hr" in row
            assert "intensity" in row

    def test_intensity_filter_afk(self, db: Path):
        rows = lookup_training_method(db, "slayer", 85, intensity_max="afk")
        for row in rows:
            assert row["intensity"].lower() == "afk"

    def test_unknown_skill_returns_empty(self, db: Path):
        rows = lookup_training_method(db, "doesnotexist", 99)
        assert rows == []

    def test_level_gate_respected(self, db: Path):
        # Croesus requires level 95 slayer; should NOT appear at level 80
        rows = lookup_training_method(db, "slayer", 80)
        names = [r["method_name"] for r in rows]
        # Level 80 < lo_lvl 95 — Croesus should not appear
        assert not any("Croesus" in n for n in names)

    def test_ordered_by_xp_per_hr_desc(self, db: Path):
        rows = lookup_training_method(db, "slayer", 95)
        xp_rates = [r["xp_per_hr"] for r in rows]
        assert xp_rates == sorted(xp_rates, reverse=True)


# ── Money making ──────────────────────────────────────────────────────────────

class TestGetMoneyMaking:
    def test_returns_results(self, db: Path):
        rows = get_money_making(db)
        assert len(rows) > 0

    def test_min_gp_filter(self, db: Path):
        rows = get_money_making(db, min_gp_per_hr=10_000_000)
        for row in rows:
            assert row["gp_per_hr"] >= 10_000_000

    def test_intensity_filter(self, db: Path):
        rows = get_money_making(db, intensity_max="afk")
        for row in rows:
            assert row["intensity"].lower() == "afk"

    def test_skill_req_filter(self, db: Path):
        # Low-level player (combat 50) should not see Telos
        rows = get_money_making(
            db,
            skill_reqs={"combat": 50},
        )
        names = [r["method"] for r in rows]
        assert not any("Telos" in n for n in names)

    def test_limit_respected(self, db: Path):
        rows = get_money_making(db, limit=3)
        assert len(rows) <= 3


# ── Quest eligibility ─────────────────────────────────────────────────────────

class TestCheckQuestEligibility:
    def _max_stats(self):
        return {
            "skills": {s: {"level": 120, "xp": 104_273_167} for s in [
                "attack", "strength", "defence", "magic", "ranged", "prayer",
                "agility", "crafting", "mining", "smithing", "runecrafting",
                "thieving", "herblore", "summoning", "slayer", "dungeoneering",
                "divination", "invention", "archaeology", "necromancy",
                "cooking", "woodcutting", "firemaking", "fletching", "fishing",
                "farming", "hunter", "construction", "combat",
            ]},
            "quest_points": 300,
        }

    def test_cook_assistant_always_eligible(self, db: Path):
        result = check_quest_eligibility(db, "Cook's Assistant", {})
        assert result["eligible"] is True

    def test_max_player_eligible_for_desert_treasure(self, db: Path):
        # Without a completed_quests list, quest prereqs are informational only —
        # JARVIS trusts the player to verify their own quest log.
        result = check_quest_eligibility(db, "Desert Treasure", self._max_stats())
        assert result["eligible"] is True

    def test_missing_quest_prereqs_block_when_log_provided(self, db: Path):
        # If the player provides their quest log, unfulfilled prereqs block eligibility.
        stats = dict(self._max_stats())
        stats["completed_quests"] = []  # completed nothing
        result = check_quest_eligibility(db, "Desert Treasure", stats)
        assert result["eligible"] is False
        assert len(result["missing_quests"]) > 0

    def test_low_level_not_eligible_for_desert_treasure(self, db: Path):
        stats = {"skills": {"magic": {"level": 1, "xp": 0}}, "quest_points": 0}
        result = check_quest_eligibility(db, "Desert Treasure", stats)
        assert result["eligible"] is False
        assert any(m["skill"] == "magic" for m in result["missing_skills"])

    def test_unknown_quest_returns_not_eligible(self, db: Path):
        result = check_quest_eligibility(db, "Quest That Does Not Exist", {})
        assert result["eligible"] is False
        assert "error" in result

    def test_result_contains_expected_keys(self, db: Path):
        result = check_quest_eligibility(db, "Cook's Assistant", {})
        assert "eligible" in result
        assert "quest_name" in result
        assert "missing_skills" in result
        assert "missing_quests" in result
        assert "missing_qp" in result


# ── Tool handler dispatch ─────────────────────────────────────────────────────

class TestToolHandlerDispatch:
    @pytest.mark.asyncio
    async def test_compute_xp_gap_dispatch(self):
        from openjarvis.rs3.tools.tool_handler import dispatch_tool
        result_str = await dispatch_tool(
            "compute_xp_gap",
            {"current_xp": 0, "target_level": 99},
        )
        result = json.loads(result_str)
        assert result["xp_gap"] == xp_for_level(99)

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        from openjarvis.rs3.tools.tool_handler import dispatch_tool
        result_str = await dispatch_tool("nonexistent_tool", {})
        result = json.loads(result_str)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_show_hud_panel_calls_cb(self):
        from openjarvis.rs3.tools.tool_handler import dispatch_tool
        called = []

        async def fake_hud(panel_type, markdown):
            called.append((panel_type, markdown))

        await dispatch_tool(
            "show_hud_panel",
            {"panel_type": "table", "markdown": "# Test"},
            hud_cb=fake_hud,
        )
        assert called == [("table", "# Test")]

    @pytest.mark.asyncio
    async def test_set_timer_returns_confirmation(self):
        from openjarvis.rs3.tools.tool_handler import dispatch_tool
        result_str = await dispatch_tool(
            "set_timer",
            {"minutes": 5, "message": "Check your herbs, sir."},
        )
        result = json.loads(result_str)
        assert result["minutes"] == 5
        assert "confirmation" in result
