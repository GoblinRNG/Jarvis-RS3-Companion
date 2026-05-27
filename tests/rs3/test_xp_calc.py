"""Tests for the RS3 XP calculator utilities."""

from __future__ import annotations

import pytest

from openjarvis.rs3.tools.xp_calc import (
    compute_xp_gap,
    hours_to_goal,
    level_for_xp,
    xp_for_level,
)


class TestXpForLevel:
    def test_level_1_requires_zero_xp(self):
        assert xp_for_level(1) == 0

    def test_level_2_matches_rs3_table(self):
        # Standard RS XP formula: level 2 = 83 XP
        assert xp_for_level(2) == 83

    def test_level_99_near_13m(self):
        # RS3 level 99 = 13,034,431 XP
        assert xp_for_level(99) == 13_034_431

    def test_level_120_near_104m(self):
        # RS3 level 120 = 104,273,167 XP
        assert xp_for_level(120) == 104_273_167

    def test_monotonic(self):
        table = [xp_for_level(lvl) for lvl in range(1, 121)]
        assert table == sorted(table)

    def test_clamps_below_1(self):
        assert xp_for_level(0) == xp_for_level(1) == 0

    def test_clamps_above_120(self):
        assert xp_for_level(121) == xp_for_level(120)


class TestLevelForXp:
    def test_zero_xp_is_level_1(self):
        assert level_for_xp(0) == 1

    def test_83_xp_is_level_2(self):
        assert level_for_xp(83) == 2

    def test_exactly_99(self):
        assert level_for_xp(13_034_431) == 99

    def test_just_below_99(self):
        assert level_for_xp(13_034_430) == 98

    def test_max_level_120(self):
        assert level_for_xp(104_273_167) == 120

    def test_beyond_120_still_120(self):
        assert level_for_xp(200_000_000) == 120


class TestComputeXpGap:
    def test_already_at_target(self):
        xp_99 = xp_for_level(99)
        assert compute_xp_gap(xp_99, 99) == 0

    def test_above_target_returns_zero(self):
        xp_99 = xp_for_level(99)
        assert compute_xp_gap(xp_99 + 1, 99) == 0

    def test_from_1_to_99(self):
        assert compute_xp_gap(0, 99) == xp_for_level(99)

    def test_partial_gap(self):
        gap = compute_xp_gap(xp_for_level(90), 99)
        expected = xp_for_level(99) - xp_for_level(90)
        assert gap == expected

    def test_gap_from_98_to_99(self):
        gap = compute_xp_gap(xp_for_level(98), 99)
        assert gap == xp_for_level(99) - xp_for_level(98)
        assert gap > 0


class TestHoursToGoal:
    def test_zero_rate_returns_inf(self):
        assert hours_to_goal(0, 99, 0) == float("inf")

    def test_negative_rate_returns_inf(self):
        assert hours_to_goal(0, 99, -100) == float("inf")

    def test_already_at_goal(self):
        assert hours_to_goal(xp_for_level(99), 99, 1_000_000) == 0.0

    def test_reasonable_estimate(self):
        # From level 1 to 99 at 1m XP/hr ≈ 13 hours
        h = hours_to_goal(0, 99, 1_000_000)
        assert 12.0 < h < 14.0

    def test_returns_float(self):
        result = hours_to_goal(0, 50, 500_000)
        assert isinstance(result, float)
