"""Quest eligibility checker against the rs3.db SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def check_quest_eligibility(
    db_path: Path,
    quest_name: str,
    player_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """Check whether a player meets the requirements for *quest_name*.

    Parameters
    ----------
    db_path:
        Path to the rs3.db SQLite database.
    quest_name:
        Quest name (case-insensitive, partial match supported).
    player_stats:
        Player stats dict with keys ``skills`` ({skill: {level, xp}}) and
        ``quest_points``.

    Returns
    -------
    Dict with keys:
        eligible: bool
        quest_name: str
        missing_skills: list of {skill, required, current}
        missing_quests: list of str
        missing_qp: int (0 if met)
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM quests WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{quest_name}%",),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "eligible": False,
            "quest_name": quest_name,
            "error": f"Quest {quest_name!r} not found in database.",
            "missing_skills": [],
            "missing_quests": [],
            "missing_qp": 0,
        }

    row = dict(rows[0])
    player_skills: Dict[str, Dict] = player_stats.get("skills", {})
    player_qp: int = player_stats.get("quest_points", 0)
    # completed_quests: optional list of quest names the player has finished.
    # When not provided we leave quest prereqs as informational only (JARVIS
    # trusts the player to verify their own quest log).
    completed_quests: Optional[List[str]] = player_stats.get("completed_quests")

    # Parse requirements
    try:
        skill_reqs: Dict[str, int] = json.loads(row.get("skill_reqs_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        skill_reqs = {}
    try:
        quest_reqs: List[str] = json.loads(row.get("quest_reqs_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        quest_reqs = []

    qp_req: int = row.get("qp_required", 0) or 0

    missing_skills = []
    for skill, required_level in skill_reqs.items():
        current_level = player_skills.get(skill, {}).get("level", 1)
        if current_level < required_level:
            missing_skills.append({
                "skill": skill,
                "required": required_level,
                "current": current_level,
            })

    # Quest prereqs — only block if the player supplied their completed quest log.
    if completed_quests is not None:
        done_lower = {q.lower() for q in completed_quests}
        missing_quests = [q for q in quest_reqs if q.lower() not in done_lower]
    else:
        # Quest log unknown — report requirements but don't block eligibility.
        missing_quests = quest_reqs

    missing_qp = max(0, qp_req - player_qp)

    # eligible = skill + QP gates met; quest log is the player's responsibility
    # unless they provided their completed_quests list.
    quest_blocking = bool(missing_quests) and completed_quests is not None
    eligible = not missing_skills and not quest_blocking and missing_qp == 0

    return {
        "eligible": eligible,
        "quest_name": row["name"],
        "qp_reward": row.get("qp", 0),
        "missing_skills": missing_skills,
        "missing_quests": missing_quests,
        "missing_qp": missing_qp,
    }


# ── Tool schema ──────────────────────────────────────────────────────────────

QUEST_SCHEMA = {
    "name": "check_quest_eligibility",
    "description": "Verify if player meets requirements for a quest.",
    "input_schema": {
        "type": "object",
        "properties": {
            "quest_name": {"type": "string", "description": "Quest name to check."},
            "player_stats": {
                "type": "object",
                "description": "Player stats including skills and quest_points.",
            },
        },
        "required": ["quest_name", "player_stats"],
    },
}
