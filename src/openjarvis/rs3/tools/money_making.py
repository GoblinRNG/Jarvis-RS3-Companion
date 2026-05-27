"""Money-making method lookup against the rs3.db SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_money_making(
    db_path: Path,
    min_gp_per_hr: int = 0,
    intensity_max: str = "all",
    skill_reqs: Optional[Dict[str, int]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return money-making methods that satisfy the given constraints.

    Parameters
    ----------
    db_path:
        Path to the rs3.db SQLite database.
    min_gp_per_hr:
        Minimum GP/hr threshold.
    intensity_max:
        Maximum intensity tier the player is willing to use.
    skill_reqs:
        Dict of {skill: level} representing the player's current levels.
        Methods with unmet requirements are filtered out.
    limit:
        Maximum number of results to return.
    """
    INTENSITY_ORDER = {"afk": 0, "semi": 1, "intensive": 2, "all": 3}
    max_tier = INTENSITY_ORDER.get(intensity_max.lower(), 3)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM money_making WHERE gp_per_hr >= ? ORDER BY gp_per_hr DESC",
            (min_gp_per_hr,),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            row_tier = INTENSITY_ORDER.get(d.get("intensity", "intensive").lower(), 2)
            if row_tier > max_tier:
                continue

            # Check skill requirements against player's levels
            if skill_reqs:
                try:
                    reqs: Dict[str, int] = json.loads(d.get("requirements_json") or "{}")
                except (json.JSONDecodeError, TypeError):
                    reqs = {}
                if not all(skill_reqs.get(sk, 0) >= lvl for sk, lvl in reqs.items()):
                    continue

            results.append(d)
            if len(results) >= limit:
                break

        return results
    finally:
        conn.close()


# ── Tool schema ──────────────────────────────────────────────────────────────

MONEY_MAKING_SCHEMA = {
    "name": "get_money_making",
    "description": "List money-making methods at or below given requirements.",
    "input_schema": {
        "type": "object",
        "properties": {
            "min_gp_per_hr": {"type": "integer", "description": "Minimum GP per hour."},
            "intensity_max": {
                "type": "string",
                "enum": ["afk", "semi", "intensive", "all"],
                "description": "Maximum intensity tier.",
            },
            "skill_reqs": {
                "type": "object",
                "description": "Player's current skill levels {skill: level}.",
            },
        },
        "required": [],
    },
}
