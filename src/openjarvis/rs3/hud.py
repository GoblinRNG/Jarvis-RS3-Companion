"""HUD overlay integration stubs (Phase 5).

The HUD is a Tauri (Rust + webview) translucent, frameless, click-through
overlay.  This module provides the Python side of the IPC bridge — it
sends panel updates via a local WebSocket that the Tauri frontend listens on.

Toggle: Ctrl+Alt+J (default).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_HUD_WS_PORT = 49152   # loopback-only, not user-facing


class HUDClient:
    """Sends panel updates to the Tauri HUD frontend over a local WebSocket."""

    def __init__(self, port: int = _HUD_WS_PORT) -> None:
        self._port = port
        self._ws = None

    async def _connect(self) -> None:
        """Lazily establish the WebSocket connection."""
        if self._ws is not None:
            return
        try:
            import websockets  # type: ignore[import]
            self._ws = await websockets.connect(f"ws://127.0.0.1:{self._port}/hud")
            logger.info("Connected to HUD frontend on port %d", self._port)
        except ImportError:
            logger.debug("websockets package not installed — HUD disabled.")
        except Exception as exc:
            logger.debug("HUD connection failed: %s", exc)

    async def send_panel(self, panel_type: str, markdown: str) -> None:
        """Push a rendered panel to the overlay.

        Parameters
        ----------
        panel_type:
            One of ``"table"``, ``"plan"``, ``"gear"``, ``"dailies"``, ``"generic"``.
        markdown:
            Markdown content for the HUD to render.
        """
        await self._connect()
        if self._ws is None:
            logger.debug("HUD not connected — dropping panel %r", panel_type)
            return
        payload = json.dumps({"type": "panel", "panel_type": panel_type, "markdown": markdown})
        try:
            await self._ws.send(payload)
        except Exception as exc:
            logger.warning("HUD send failed: %s", exc)
            self._ws = None

    async def send_xp_ticker(self, skill: str, xp_per_hr: int, gp_per_hr: int = 0) -> None:
        """Update the top-left XP/hr ticker strip."""
        await self._connect()
        if self._ws is None:
            return
        payload = json.dumps({
            "type": "xp_ticker",
            "skill": skill,
            "xp_per_hr": xp_per_hr,
            "gp_per_hr": gp_per_hr,
        })
        try:
            await self._ws.send(payload)
        except Exception as exc:
            logger.warning("HUD ticker send failed: %s", exc)
            self._ws = None

    async def send_dailies(self, dailies: Dict[str, bool]) -> None:
        """Update the dailies panel (key → done: bool)."""
        await self._connect()
        if self._ws is None:
            return
        payload = json.dumps({"type": "dailies", "state": dailies})
        try:
            await self._ws.send(payload)
        except Exception as exc:
            logger.warning("HUD dailies send failed: %s", exc)
            self._ws = None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
