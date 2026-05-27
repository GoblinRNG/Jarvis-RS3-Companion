"""Pre-canned JARVIS personality lines and voice-cache management.

At startup, lines that have a cached MP3 in ``voice_cache/`` are played
instantly (no API round-trip). Lines without a cache are synthesised and
then stored for next time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Trigger → spoken text mapping
PERSONALITY_LINES: Dict[str, str] = {
    "boot":            "At your service, sir.",
    "idle_10min":      "What is it you are trying to achieve, sir?",
    "shutdown":        "Time to rest, sir.",
    "death":           "Another untimely demise. Your gravestone holds for six minutes, sir.",
    "level_99":        "Ninety-nine, sir. A respectable showing.",
    "level_120":       "One hundred and twenty. The grind reciprocates.",
    "level_200m":      "Two hundred million. The skill is, by any reasonable measure, finished.",
    "losing_streak":   "Perhaps a brief pause, sir. The boss will still be there.",
    "reset_10min":     "Ten minutes to reset, sir. Vis wax and the penguin await.",
    "weekly_reset":    "The weekly reset has occurred, sir. Croesus and Vis Wax await.",
    "muted":           "As you wish, sir. I shall keep my thoughts to myself for a while.",
    "as_you_wish":     "As you wish, sir.",
    "may_i_remind":    "May I remind you, sir.",
}

# Canonical filenames for pre-rendered voice cache files.
# Keys match PERSONALITY_LINES keys; values are MP3 filenames.
VOICE_CACHE_FILES: Dict[str, str] = {
    "boot":          "Voicy_At_Your_Service_Sir.mp3",
    "idle_10min":    "Voicy_What_Is_It_You_Are_Trying_To_Achieve_Sir_.mp3",
    "shutdown":      "Voicy_Time_To_Rest_.mp3",
    "as_you_wish":   "Voicy_As_You_Wish_.mp3",
    "may_i_remind":  "Voicy_May_I_Remind_You.mp3",
    "startup":       "Voicy_Jarvis_Start_Up.mp3",
}


class PersonalityPlayer:
    """Manages playback of personality lines, preferring cached audio."""

    def __init__(
        self,
        voice_cache_dir: Path,
        synthesise_fn=None,
        play_fn=None,
    ) -> None:
        """
        Parameters
        ----------
        voice_cache_dir:
            Directory containing pre-rendered MP3 files.
        synthesise_fn:
            Async callable(text: str) → bytes — used when no cache exists.
        play_fn:
            Async callable(audio_bytes: bytes) — plays audio bytes.
        """
        self._cache_dir = voice_cache_dir
        self._synthesise = synthesise_fn
        self._play = play_fn

    def _cache_path(self, trigger: str) -> Optional[Path]:
        """Return cached MP3 path for *trigger*, or None if absent."""
        filename = VOICE_CACHE_FILES.get(trigger)
        if filename:
            p = self._cache_dir / filename
            if p.exists():
                return p
        # Also check a generic name
        generic = self._cache_dir / f"{trigger}.mp3"
        return generic if generic.exists() else None

    async def say(self, trigger: str, custom_text: Optional[str] = None) -> None:
        """Speak a personality line.

        Uses cached audio when available; synthesises and caches otherwise.

        Parameters
        ----------
        trigger:
            Key from PERSONALITY_LINES (e.g. ``"boot"``).
        custom_text:
            Override the default text for this trigger.
        """
        text = custom_text or PERSONALITY_LINES.get(trigger, trigger)

        # Try cache first
        cached = self._cache_path(trigger)
        if cached:
            logger.debug("Playing cached line %r from %s", trigger, cached)
            if self._play:
                audio = cached.read_bytes()
                await self._play(audio)
            return

        # Synthesise + cache
        logger.debug("Synthesising line %r: %r", trigger, text)
        if self._synthesise:
            try:
                audio: bytes = await self._synthesise(text)
                # Save to cache for future use
                out = self._cache_dir / f"{trigger}.mp3"
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                out.write_bytes(audio)
                logger.info("Cached personality line %r → %s", trigger, out)
                if self._play:
                    await self._play(audio)
            except Exception as exc:
                logger.error("Failed to synthesise personality line %r: %s", trigger, exc)
        else:
            logger.info("Personality line (no TTS): %s", text)

    async def boot(self) -> None:
        await self.say("boot")

    async def idle(self) -> None:
        await self.say("idle_10min")

    async def shutdown(self) -> None:
        await self.say("shutdown")

    async def death(self, gravestone_minutes: int = 6) -> None:
        text = f"Another untimely demise. Your gravestone holds for {gravestone_minutes} minutes, sir."
        await self.say("death", custom_text=text)

    async def level_milestone(self, skill: str, level: int) -> None:
        if level == 200_000_000:
            trigger, text = "level_200m", f"Two hundred million {skill} XP. The skill is, by any reasonable measure, finished."
        elif level == 120:
            trigger, text = "level_120", f"One hundred and twenty {skill}. The grind reciprocates."
        elif level == 99:
            trigger, text = "level_99", f"Ninety-nine {skill}, sir. A respectable showing."
        else:
            return
        await self.say(trigger, custom_text=text)

    async def losing_streak(self) -> None:
        await self.say("losing_streak")

    async def reset_warning(self, minutes: int = 10) -> None:
        text = f"{minutes} minutes to reset, sir. Vis wax and the penguin await."
        await self.say("reset_10min", custom_text=text)
