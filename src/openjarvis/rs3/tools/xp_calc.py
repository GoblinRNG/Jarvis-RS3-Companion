"""XP gap calculator and RS3 level table.

Uses the standard RuneScape XP formula — no external dependencies.
Results are cached at module load so repeated calls are O(1).
"""

from __future__ import annotations

import functools
from typing import Dict

# ── XP table ────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _build_xp_table() -> Dict[int, int]:
    """Return {level: cumulative_xp_required} for levels 1–120."""
    table: Dict[int, int] = {1: 0}
    for lvl in range(2, 121):
        total = 0
        for L in range(1, lvl):
            total += int(L + 300 * (2 ** (L / 7.0)))
        table[lvl] = total // 4
    return table


def xp_for_level(level: int) -> int:
    """Return total XP required to reach *level* (1-indexed, capped at 120)."""
    level = max(1, min(120, level))
    return _build_xp_table()[level]


def level_for_xp(xp: int) -> int:
    """Return the current level for a given XP total (1-120)."""
    table = _build_xp_table()
    result = 1
    for lvl, required in table.items():
        if xp >= required:
            result = lvl
        else:
            break
    return result


def compute_xp_gap(current_xp: int, target_level: int) -> int:
    """Return XP needed to reach *target_level* from *current_xp*.

    Returns 0 when the player already meets or exceeds the target.
    """
    return max(0, xp_for_level(target_level) - current_xp)


def hours_to_goal(current_xp: int, target_level: int, xp_per_hour: int) -> float:
    """Estimate hours to reach *target_level* at the given XP/hr rate."""
    if xp_per_hour <= 0:
        return float("inf")
    gap = compute_xp_gap(current_xp, target_level)
    return round(gap / xp_per_hour, 2)


# ── Tool schema ──────────────────────────────────────────────────────────────

XP_GAP_SCHEMA = {
    "name": "compute_xp_gap",
    "description": "Total XP needed from current XP to target level.",
    "input_schema": {
        "type": "object",
        "properties": {
            "current_xp": {"type": "integer", "description": "Player's current XP in the skill."},
            "target_level": {"type": "integer", "description": "Desired target level (1-120)."},
        },
        "required": ["current_xp", "target_level"],
    },
}
