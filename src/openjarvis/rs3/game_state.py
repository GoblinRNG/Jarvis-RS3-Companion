"""Game-state capture — Phase 3/4 stubs with RuneMetrics polling.

Phase 3 adds RuneMetrics XP feed + Hiscores polling.
Phase 4 adds screen OCR (chatbox events, minimap, inventory).

All OCR capture is strictly read-only and processes frames locally —
no data leaves the machine, in compliance with Jagex ToS.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PlayerStats:
    skills: Dict[str, Dict[str, int]] = field(default_factory=dict)
    total_level: int = 0
    combat_level: float = 0.0
    quest_points: int = 0


@dataclass
class Equipment:
    head: str = ""
    neck: str = ""
    back: str = ""
    chest: str = ""
    legs: str = ""
    hands: str = ""
    feet: str = ""
    ring: str = ""
    main_hand: str = ""
    off_hand: str = ""
    ammo: str = ""


@dataclass
class GameState:
    """Snapshot of current game state passed to JARVIS each turn."""

    player_stats: PlayerStats = field(default_factory=PlayerStats)
    equipment: Equipment = field(default_factory=Equipment)
    inventory: List[str] = field(default_factory=list)
    bank_summary: Dict[str, Any] = field(default_factory=dict)
    location: str = "Unknown"
    active_task: str = ""
    dailies_state: Dict[str, bool] = field(default_factory=dict)
    ge_prices: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    minutes_to_reset: int = 0

    def to_context_dict(self) -> Dict[str, Any]:
        """Serialise to the JSON context block consumed by the LLM."""
        d = asdict(self)
        d["time"] = {
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
            "minutes_to_reset": self.minutes_to_reset,
        }
        return d


# ── Reset-time helpers ───────────────────────────────────────────────────────

def minutes_until_reset() -> int:
    """Return minutes until the next daily reset (00:00 UTC)."""
    now = time.gmtime()
    seconds_elapsed = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
    return (86400 - seconds_elapsed) // 60


# ── RuneMetrics XP feed ──────────────────────────────────────────────────────

_RUNEMETRICS_URL = "https://apps.runescape.com/runemetrics/profile/profile"


async def fetch_runemetrics(rsn: str) -> Optional[Dict[str, Any]]:
    """Fetch a player's RuneMetrics profile.

    Returns the raw JSON dict or None on failure.
    Note: RuneMetrics profiles must be set to 'Public' by the player.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _RUNEMETRICS_URL,
                params={"user": rsn, "activities": 20},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("RuneMetrics fetch failed for %r: %s", rsn, exc)
        return None


# ── OCR overlay (Phase 4 stub) ───────────────────────────────────────────────

class ScreenCapture:
    """Read-only screen OCR for game-state enrichment (Phase 4).

    All processing is local — no frames leave the machine.
    We observe only; no input automation of any kind.
    """

    def __init__(self) -> None:
        self._available = self._check_deps()

    @staticmethod
    def _check_deps() -> bool:
        try:
            import PIL  # noqa: F401
            return True
        except ImportError:
            return False

    def capture_chatbox(self) -> List[str]:
        """Return recent chatbox lines (Phase 4 stub)."""
        if not self._available:
            return []
        # TODO (Phase 4): implement region capture + Tesseract/PaddleOCR
        return []

    def capture_inventory(self) -> List[str]:
        """Return current inventory item names via template matching (Phase 4 stub)."""
        if not self._available:
            return []
        # TODO (Phase 4): region capture + sprite library matching
        return []

    def detect_events(self) -> List[str]:
        """Parse chatbox for game events (death, level-up, etc.) (Phase 4 stub)."""
        lines = self.capture_chatbox()
        events = []
        for line in lines:
            lower = line.lower()
            if "you have died" in lower:
                events.append("death")
            elif "you've advanced" in lower or "congratulations" in lower:
                events.append(f"level_up:{line}")
            elif "completed slayer task" in lower:
                events.append("slayer_task_complete")
        return events


# ── Composite collector ──────────────────────────────────────────────────────

class GameStateCollector:
    """Collects and fuses game state from all available sources."""

    def __init__(self, config) -> None:
        self._cfg = config
        self._ocr = ScreenCapture()
        self._last_hiscores: Optional[Dict] = None
        self._last_hiscores_t: float = 0.0
        self._ge_cache: Dict[str, Any] = {}
        self._ge_cache_t: float = 0.0

    def collect(self) -> Dict[str, Any]:
        """Return a game-context dict synchronously (safe to call from any thread)."""
        state = GameState()
        state.preferences = {
            "ironman": self._cfg.player.ironman,
            "hcim": self._cfg.player.hcim,
            "afk_preference": self._cfg.player.afk_preference,
            "combat_style": self._cfg.player.combat_style,
            "honorific": self._cfg.player.honorific,
            "playtime_min_per_day": self._cfg.player.playtime_min_per_day,
        }
        state.minutes_to_reset = minutes_until_reset()
        state.ge_prices = dict(self._ge_cache)

        # Inject cached hiscores if available
        if self._last_hiscores:
            skills = self._last_hiscores.get("skills", {})
            state.player_stats = PlayerStats(
                skills=skills,
                total_level=sum(s.get("level", 1) for s in skills.values()),
                quest_points=0,
            )

        # OCR enrichment (no-op in Phase 1)
        state.inventory = self._ocr.capture_inventory()

        return state.to_context_dict()

    async def poll_hiscores(self) -> None:
        """Refresh hiscores in the background (Phase 3)."""
        from openjarvis.rs3.tools.hiscores import get_hiscores
        interval = self._cfg.data.hiscores_poll_seconds
        while True:
            await asyncio.sleep(interval)
            try:
                data = await get_hiscores(self._cfg.player.rsn)
                self._last_hiscores = data
                self._last_hiscores_t = time.time()
            except Exception as exc:
                logger.debug("Hiscores poll failed: %s", exc)

    async def poll_ge_prices(self, item_names: List[str]) -> None:
        """Refresh GE prices for a watchlist in the background (Phase 3)."""
        from openjarvis.rs3.tools.ge_price import get_ge_price
        interval = self._cfg.data.ge_poll_seconds
        while True:
            for item in item_names:
                try:
                    data = await get_ge_price(item)
                    self._ge_cache[item] = data
                    self._ge_cache_t = time.time()
                except Exception as exc:
                    logger.debug("GE price poll failed for %r: %s", item, exc)
            await asyncio.sleep(interval)
