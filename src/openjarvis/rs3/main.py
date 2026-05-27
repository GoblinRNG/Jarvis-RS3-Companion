"""Entry point for the RS3 JARVIS companion.

Usage::

    # Using config.yaml
    python -m openjarvis.rs3.main

    # Programmatic
    from openjarvis.rs3 import JarvisRS3
    import asyncio

    jarvis = JarvisRS3.from_config("config.yaml")
    asyncio.run(jarvis.run())
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Auto-load .env if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore[import]

    def _find_env() -> Path | None:
        """Walk upward from the current file looking for a .env."""
        here = Path(__file__).resolve()
        for parent in [here, *here.parents]:
            candidate = parent / ".env"
            if candidate.exists():
                return candidate
        return None

    _env_file = _find_env()
    if _env_file:
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

logger = logging.getLogger(__name__)


class JarvisRS3:
    """High-level orchestrator for the RS3 JARVIS companion.

    Wires together the voice loop, game-state collector, scheduler,
    and HUD client.
    """

    def __init__(self, config) -> None:
        self._cfg = config
        self._state_collector = None
        self._scheduler = None
        self._hud = None

    @classmethod
    def from_config(cls, path: str | Path = "config.yaml") -> "JarvisRS3":
        """Load config from *path* and return a ready instance."""
        from openjarvis.rs3.config import RS3Config
        cfg = RS3Config.from_yaml(path)
        return cls(cfg)

    @classmethod
    def with_defaults(cls) -> "JarvisRS3":
        """Return an instance with default (stub) configuration."""
        from openjarvis.rs3.config import RS3Config
        return cls(RS3Config.default())

    # ── Database bootstrap ────────────────────────────────────────────────────

    def _ensure_db(self) -> Path:
        from openjarvis.rs3.db.schema import init_db
        from openjarvis.rs3.db.seed_data import seed_all

        db_path = init_db(self._cfg.db_path)
        seed_all(db_path)
        logger.info("RS3 database ready at %s", db_path)
        return db_path

    # ── Background tasks ──────────────────────────────────────────────────────

    async def _run_background(self, speak_cb) -> None:
        """Launch background polling and scheduler tasks."""
        from openjarvis.rs3.game_state import GameStateCollector
        from openjarvis.rs3.scheduler import RS3Scheduler

        self._state_collector = GameStateCollector(self._cfg)
        self._scheduler = RS3Scheduler(speak_cb=speak_cb)
        self._scheduler.start()

        # Background polling tasks (Phase 3)
        watchlist = ["elder overload", "super restore", "rocktail"]
        tasks = [
            asyncio.create_task(self._state_collector.poll_hiscores()),
            asyncio.create_task(self._state_collector.poll_ge_prices(watchlist)),
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._scheduler.stop()

    # ── Main run ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the full RS3 JARVIS companion. Blocks until interrupted."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        self._ensure_db()

        from openjarvis.rs3.game_state import GameStateCollector
        from openjarvis.rs3.voice.loop import VoiceLoop

        state_collector = GameStateCollector(self._cfg)

        if self._cfg.hud.enabled:
            from openjarvis.rs3.hud import HUDClient
            self._hud = HUDClient()

        loop = VoiceLoop(
            config=self._cfg,
            game_state_fn=state_collector.collect,
            hud_cb=self._hud.send_panel if self._hud else None,
        )

        # Run voice loop + background tasks concurrently
        await asyncio.gather(
            loop.run(),
            self._run_background(speak_cb=loop._speak),
        )


def main() -> None:
    """CLI entry point: ``jarvis-rs3``."""
    import argparse

    parser = argparse.ArgumentParser(description="RS3 JARVIS companion")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logger.error("Config file not found: %s", cfg_path)
        sys.exit(1)

    jarvis = JarvisRS3.from_config(cfg_path)
    try:
        asyncio.run(jarvis.run())
    except KeyboardInterrupt:
        print("\nGoodnight, sir.")


if __name__ == "__main__":
    main()
