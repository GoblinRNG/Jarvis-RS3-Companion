"""Training-method lookup against the rs3.db SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def lookup_training_method(
    db_path: Path,
    skill: str,
    current_level: int,
    target_level: Optional[int] = None,
    intensity_max: str = "all",
) -> List[Dict[str, Any]]:
    """Query training methods for *skill* at *current_level*.

    Parameters
    ----------
    db_path:
        Path to the rs3.db SQLite database.
    skill:
        Skill name (e.g. "slayer", "herblore").
    current_level:
        Player's current level.
    target_level:
        If set, filters to methods that are relevant up to this level.
    intensity_max:
        Maximum intensity tier: ``"afk"`` ⊂ ``"semi"`` ⊂ ``"intensive"`` ⊂ ``"all"``.

    Returns
    -------
    List of method dicts ordered by ``xp_per_hr DESC``.
    """
    INTENSITY_ORDER = {"afk": 0, "semi": 1, "intensive": 2, "all": 3}
    max_tier = INTENSITY_ORDER.get(intensity_max.lower(), 3)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM training_methods
            WHERE LOWER(skill) = LOWER(?)
              AND lo_lvl <= ?
              AND (? IS NULL OR hi_lvl >= ?)
            ORDER BY xp_per_hr DESC
        """
        rows = cursor.execute(
            query, (skill, current_level, target_level, target_level)
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            # Filter by intensity
            row_tier = INTENSITY_ORDER.get(d.get("intensity", "intensive").lower(), 2)
            if row_tier <= max_tier:
                try:
                    d["requirements"] = json.loads(d.get("requirements_json") or "{}")
                except (json.JSONDecodeError, TypeError):
                    d["requirements"] = {}
                results.append(d)
        return results
    finally:
        conn.close()


# ── Tool schema ──────────────────────────────────────────────────────────────

TRAINING_SCHEMA = {
    "name": "lookup_training_method",
    "description": "Query the training methods DB filtered by skill, level, and intensity.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skill": {"type": "string", "description": "Skill name (e.g. slayer, herblore)."},
            "current_level": {"type": "integer", "description": "Player's current level."},
            "target_level": {"type": "integer", "description": "Optional target level."},
            "intensity_max": {
                "type": "string",
                "enum": ["afk", "semi", "intensive", "all"],
                "description": "Maximum intensity tier.",
            },
        },
        "required": ["skill", "current_level"],
    },
}
