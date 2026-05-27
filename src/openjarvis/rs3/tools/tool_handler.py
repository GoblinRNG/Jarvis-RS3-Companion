"""Claude tool-call dispatcher for the RS3 JARVIS tool suite.

Converts Anthropic ``tool_use`` content blocks into concrete Python calls
and returns a ``tool_result`` block ready for the next conversation turn.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openjarvis.rs3.tools.ge_price import GE_PRICE_SCHEMA, get_ge_price
from openjarvis.rs3.tools.hiscores import HISCORES_SCHEMA, get_hiscores
from openjarvis.rs3.tools.money_making import MONEY_MAKING_SCHEMA, get_money_making
from openjarvis.rs3.tools.quest import QUEST_SCHEMA, check_quest_eligibility
from openjarvis.rs3.tools.timers import TIMER_SCHEMA, set_timer
from openjarvis.rs3.tools.training import TRAINING_SCHEMA, lookup_training_method
from openjarvis.rs3.tools.xp_calc import XP_GAP_SCHEMA, compute_xp_gap

logger = logging.getLogger(__name__)

# ── Anthropic-format tool schema list ───────────────────────────────────────

TOOL_SCHEMA: List[Dict[str, Any]] = [
    GE_PRICE_SCHEMA,
    HISCORES_SCHEMA,
    XP_GAP_SCHEMA,
    TRAINING_SCHEMA,
    MONEY_MAKING_SCHEMA,
    QUEST_SCHEMA,
    TIMER_SCHEMA,
    {
        "name": "show_hud_panel",
        "description": "Push a rendered panel to the HUD overlay (table, plan, gear sheet).",
        "input_schema": {
            "type": "object",
            "properties": {
                "panel_type": {
                    "type": "string",
                    "enum": ["table", "plan", "gear", "dailies", "generic"],
                },
                "markdown": {"type": "string", "description": "Markdown content to render."},
            },
            "required": ["panel_type", "markdown"],
        },
    },
    {
        "name": "wiki_search",
        "description": "Hybrid retrieval over the RS3 wiki RAG index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "top_k": {"type": "integer", "description": "Number of results (default 8).", "default": 8},
            },
            "required": ["query"],
        },
    },
]


async def dispatch_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    db_path: Optional[Path] = None,
    speak_cb: Optional[Callable] = None,
    hud_cb: Optional[Callable] = None,
    wiki_search_cb: Optional[Callable] = None,
) -> str:
    """Dispatch a tool call by name and return a JSON-serialisable result string.

    Parameters
    ----------
    tool_name:
        Name of the tool as reported by the LLM.
    tool_input:
        The ``input`` dict from the ``tool_use`` content block.
    db_path:
        Path to rs3.db — required for DB-backed tools.
    speak_cb:
        Async callback used by the timer tool to fire voice reminders.
    hud_cb:
        Async callback that pushes panels to the HUD overlay.
    wiki_search_cb:
        Async callback for RAG wiki retrieval.
    """
    try:
        if tool_name == "get_ge_price":
            result = await get_ge_price(tool_input["item_name"])

        elif tool_name == "get_hiscores":
            result = await get_hiscores(tool_input["rsn"])

        elif tool_name == "compute_xp_gap":
            gap = compute_xp_gap(tool_input["current_xp"], tool_input["target_level"])
            result = {"xp_gap": gap, "target_level": tool_input["target_level"]}

        elif tool_name == "lookup_training_method":
            if db_path is None:
                return json.dumps({"error": "Database not configured."})
            result = lookup_training_method(
                db_path,
                tool_input["skill"],
                tool_input["current_level"],
                tool_input.get("target_level"),
                tool_input.get("intensity_max", "all"),
            )

        elif tool_name == "get_money_making":
            if db_path is None:
                return json.dumps({"error": "Database not configured."})
            result = get_money_making(
                db_path,
                min_gp_per_hr=tool_input.get("min_gp_per_hr", 0),
                intensity_max=tool_input.get("intensity_max", "all"),
                skill_reqs=tool_input.get("skill_reqs"),
            )

        elif tool_name == "check_quest_eligibility":
            if db_path is None:
                return json.dumps({"error": "Database not configured."})
            result = check_quest_eligibility(
                db_path,
                tool_input["quest_name"],
                tool_input["player_stats"],
            )

        elif tool_name == "set_timer":
            result = await set_timer(
                tool_input["minutes"],
                tool_input["message"],
                speak_cb=speak_cb,
            )

        elif tool_name == "show_hud_panel":
            if hud_cb:
                await hud_cb(tool_input.get("panel_type", "generic"), tool_input.get("markdown", ""))
            result = {"status": "panel_sent"}

        elif tool_name == "wiki_search":
            if wiki_search_cb:
                result = await wiki_search_cb(
                    tool_input["query"], tool_input.get("top_k", 8)
                )
            else:
                result = {"error": "Wiki RAG not configured (Phase 2)."}

        else:
            result = {"error": f"Unknown tool: {tool_name!r}"}

    except Exception as exc:
        logger.exception("Tool %r raised an exception", tool_name)
        result = {"error": str(exc)}

    return json.dumps(result, default=str)
