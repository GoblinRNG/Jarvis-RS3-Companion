"""RS3 JARVIS — RuneScape 3 companion module.

Provides the full voice pipeline (wake word → STT → Claude → TTS),
game-state capture, GE/Hiscores tools, XP calculators, daily reset
scheduling, and HUD overlay integration.

Quick start (Phase 1 — voice loop only)::

    from openjarvis.rs3 import JarvisRS3
    import asyncio

    jarvis = JarvisRS3.from_config("config.yaml")
    asyncio.run(jarvis.run())
"""

from __future__ import annotations

from openjarvis.rs3.config import RS3Config
from openjarvis.rs3.main import JarvisRS3

__all__ = ["JarvisRS3", "RS3Config"]
