"""RS3 daily/weekly reset scheduler with voice announcements.

Uses APScheduler when available, falling back to a simple asyncio loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RS3Scheduler:
    """Schedules daily/weekly reset events and fires voice announcements."""

    def __init__(self, speak_cb: Optional[Callable[[str], None]] = None) -> None:
        """
        Parameters
        ----------
        speak_cb:
            Async callable that speaks a text string. When None, events are only logged.
        """
        self._speak = speak_cb
        self._scheduler = None
        self._tasks: list = []

    async def _announce(self, text: str) -> None:
        logger.info("RS3 Event: %s", text)
        if self._speak:
            try:
                await self._speak(text)
            except Exception as exc:
                logger.error("Announce failed: %s", exc)

    # ── APScheduler path ──────────────────────────────────────────────────────

    def _init_apscheduler(self) -> bool:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import]
            self._scheduler = AsyncIOScheduler(timezone="UTC")
            return True
        except ImportError:
            return False

    def _register_jobs(self) -> None:
        """Register daily/weekly announcements."""

        # Daily reset: 00:00 UTC
        self._scheduler.add_job(
            self._on_daily_reset,
            trigger="cron",
            hour=0,
            minute=0,
            id="daily_reset",
        )
        # Warning 10 minutes before reset: 23:50 UTC
        self._scheduler.add_job(
            self._on_reset_warning,
            trigger="cron",
            hour=23,
            minute=50,
            id="reset_warning_10min",
        )
        # Weekly reset: Wednesday 00:00 UTC
        self._scheduler.add_job(
            self._on_weekly_reset,
            trigger="cron",
            day_of_week="wed",
            hour=0,
            minute=0,
            id="weekly_reset",
        )

    async def _on_daily_reset(self) -> None:
        await self._announce(
            "The daily reset has occurred, sir. "
            "Your dailies have refreshed — herb runs, Vis Wax, and Big Chinchompa await."
        )

    async def _on_weekly_reset(self) -> None:
        await self._announce(
            "The weekly reset has occurred, sir. "
            "Croesus, Shattered Worlds, and Penguin Hide and Seek are all available again."
        )

    async def _on_reset_warning(self) -> None:
        await self._announce(
            "Ten minutes to reset, sir. Vis Wax and the penguin await."
        )

    # ── Async fallback ────────────────────────────────────────────────────────

    async def _asyncio_daily_loop(self) -> None:
        """Simple asyncio fallback — polls every minute."""
        while True:
            now = datetime.now(tz=timezone.utc)
            if now.hour == 0 and now.minute == 0:
                if now.weekday() == 2:  # Wednesday
                    await self._on_weekly_reset()
                else:
                    await self._on_daily_reset()
            elif now.hour == 23 and now.minute == 50:
                await self._on_reset_warning()
            await asyncio.sleep(60)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the scheduler (non-blocking)."""
        if self._init_apscheduler():
            self._register_jobs()
            self._scheduler.start()
            logger.info("RS3Scheduler started via APScheduler.")
        else:
            logger.warning(
                "APScheduler not installed — using asyncio fallback. "
                "Install with: pip install apscheduler"
            )
            task = asyncio.ensure_future(self._asyncio_daily_loop())
            self._tasks.append(task)

    def stop(self) -> None:
        """Stop the scheduler cleanly."""
        if self._scheduler:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
