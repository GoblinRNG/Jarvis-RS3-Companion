"""In-game voice reminder timers."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Registered timers: {timer_id: asyncio.Task}
_active_timers: dict = {}
_timer_counter = 0


async def set_timer(
    minutes: int,
    message: str,
    speak_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """Schedule a voice reminder *message* after *minutes* minutes.

    Parameters
    ----------
    minutes:
        Delay in minutes (1–120).
    message:
        Text to speak when the timer fires.
    speak_cb:
        Optional async callable that receives the message text. When None,
        the reminder is only logged.

    Returns
    -------
    Dict with timer_id and confirmation text.
    """
    global _timer_counter
    minutes = max(1, min(120, int(minutes)))
    _timer_counter += 1
    timer_id = f"timer_{_timer_counter}"

    async def _fire():
        await asyncio.sleep(minutes * 60)
        logger.info("Timer %s fired: %s", timer_id, message)
        if speak_cb:
            try:
                await speak_cb(message)
            except Exception as exc:
                logger.error("Timer speak callback failed: %s", exc)
        _active_timers.pop(timer_id, None)

    task = asyncio.create_task(_fire())
    _active_timers[timer_id] = task
    return {
        "timer_id": timer_id,
        "minutes": minutes,
        "message": message,
        "confirmation": f"Timer set for {minutes} minute{'s' if minutes != 1 else ''}.",
    }


def cancel_timer(timer_id: str) -> bool:
    """Cancel a pending timer. Returns True if found and cancelled."""
    task = _active_timers.pop(timer_id, None)
    if task:
        task.cancel()
        return True
    return False


def active_timer_count() -> int:
    """Return the number of currently active timers."""
    return len(_active_timers)


# ── Tool schema ──────────────────────────────────────────────────────────────

TIMER_SCHEMA = {
    "name": "set_timer",
    "description": "Schedule a voice reminder in N minutes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "minutes": {"type": "integer", "description": "Delay in minutes."},
            "message": {"type": "string", "description": "Message to speak when timer fires."},
        },
        "required": ["minutes", "message"],
    },
}
