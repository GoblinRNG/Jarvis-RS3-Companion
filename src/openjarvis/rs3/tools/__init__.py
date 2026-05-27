"""RS3 JARVIS tool implementations.

Each module exposes an async callable plus its JSON schema entry so the
LLM can invoke it as a function call.
"""

from openjarvis.rs3.tools.ge_price import get_ge_price, GE_PRICE_SCHEMA
from openjarvis.rs3.tools.hiscores import get_hiscores, HISCORES_SCHEMA
from openjarvis.rs3.tools.xp_calc import compute_xp_gap, XP_GAP_SCHEMA
from openjarvis.rs3.tools.training import lookup_training_method, TRAINING_SCHEMA
from openjarvis.rs3.tools.money_making import get_money_making, MONEY_MAKING_SCHEMA
from openjarvis.rs3.tools.quest import check_quest_eligibility, QUEST_SCHEMA
from openjarvis.rs3.tools.timers import set_timer, TIMER_SCHEMA
from openjarvis.rs3.tools.tool_handler import TOOL_SCHEMA, dispatch_tool

__all__ = [
    "get_ge_price",
    "get_hiscores",
    "compute_xp_gap",
    "lookup_training_method",
    "get_money_making",
    "check_quest_eligibility",
    "set_timer",
    "TOOL_SCHEMA",
    "dispatch_tool",
]
