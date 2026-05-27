"""Phase-1 voice loop: microphone → wake word → STT → Claude → TTS.

Requires optional dependencies::

    pip install pvporcupine sounddevice faster-whisper anthropic elevenlabs

The loop is intentionally kept thin.  Game-state collection, RAG retrieval,
and HUD integration (Phases 2-5) are injected via callbacks so this module
stays testable without hardware.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000          # Hz — Porcupine + Whisper both expect 16 kHz
FRAME_LENGTH = 512            # Porcupine frame length in samples
VAD_SILENCE_MS = 1_500        # ms of silence before utterance ends
MAX_UTTERANCE_S = 30          # hard cap on recording length


# ── Wake-word listener (Porcupine) ───────────────────────────────────────────

class WakeWordListener:
    """Wraps ``pvporcupine`` with graceful fallback when not installed."""

    def __init__(self, access_key: str, keyword: str = "jarvis") -> None:
        self._access_key = access_key
        self._keyword = keyword
        self._porcupine = None

    def _ensure_loaded(self):
        if self._porcupine is not None:
            return
        try:
            import pvporcupine  # type: ignore[import]
            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keywords=[self._keyword],
            )
            logger.info("Porcupine loaded (keyword=%r)", self._keyword)
        except ImportError:
            logger.warning("pvporcupine not installed — wake word detection disabled.")
        except Exception as exc:
            logger.error("Porcupine init failed: %s", exc)

    @property
    def frame_length(self) -> int:
        self._ensure_loaded()
        return self._porcupine.frame_length if self._porcupine else FRAME_LENGTH

    def process(self, pcm_frame) -> bool:
        """Return True if the wake word was detected in *pcm_frame*."""
        if self._porcupine is None:
            return False
        result = self._porcupine.process(pcm_frame)
        return result >= 0

    def delete(self) -> None:
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None


# ── Audio helpers ────────────────────────────────────────────────────────────

def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit PCM bytes in a minimal WAV container."""
    import struct
    num_samples = len(pcm_bytes) // 2
    duration_samples = num_samples
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm_bytes),
        b"WAVE",
        b"fmt ",
        16,          # chunk size
        1,           # PCM
        1,           # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,           # block align
        16,          # bits per sample
        b"data",
        len(pcm_bytes),
    )
    return header + pcm_bytes


# ── ElevenLabs TTS ───────────────────────────────────────────────────────────

async def _elevenlabs_speak(
    text: str,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_flash_v2",
    stability: float = 0.55,
    similarity: float = 0.85,
    style: float = 0.30,
) -> bytes:
    """Call ElevenLabs TTS and return raw audio bytes."""
    try:
        from elevenlabs import ElevenLabs, VoiceSettings  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "elevenlabs package not installed. "
            "Install with: pip install elevenlabs"
        ) from e

    client = ElevenLabs(api_key=api_key)
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model_id,
        voice_settings=VoiceSettings(
            stability=stability,
            similarity_boost=similarity,
            style=style,
        ),
    )
    # collect generator into bytes
    chunks = []
    for chunk in audio_iter:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
    return b"".join(chunks)


async def _sounddevice_play(audio_bytes: bytes, sample_rate: int = 44_100) -> None:
    """Play audio bytes via sounddevice (blocking until done)."""
    try:
        import numpy as np
        import sounddevice as sd  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "sounddevice/numpy not installed. "
            "Install with: pip install sounddevice numpy"
        ) from e

    # Decode MP3 → PCM using pydub or soundfile if available
    try:
        import pydub  # type: ignore[import]
        seg = pydub.AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        sd.play(samples, samplerate=seg.frame_rate)
        sd.wait()
        return
    except ImportError:
        pass

    # Fallback: assume raw PCM float32
    buf = np.frombuffer(audio_bytes, dtype=np.float32)
    sd.play(buf, samplerate=sample_rate)
    sd.wait()


# ── Main voice loop ──────────────────────────────────────────────────────────

class VoiceLoop:
    """Full Phase-1 voice loop.

    Parameters
    ----------
    config:
        ``RS3Config`` instance.
    game_state_fn:
        Callable ``() → dict`` that returns the current game context.
        Defaults to returning an empty dict (Phase 1 stub).
    tool_dispatch_fn:
        Async callable for tool resolution (Phase 2+).
    hud_cb:
        Async callable for HUD panel updates (Phase 5+).
    wiki_search_cb:
        Async callable for RAG wiki search (Phase 2+).
    """

    def __init__(
        self,
        config,
        game_state_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        tool_dispatch_fn: Optional[Callable] = None,
        hud_cb: Optional[Callable] = None,
        wiki_search_cb: Optional[Callable] = None,
    ) -> None:
        self._cfg = config
        self._game_state_fn = game_state_fn or (lambda: {})
        self._tool_dispatch_fn = tool_dispatch_fn
        self._hud_cb = hud_cb
        self._wiki_search_cb = wiki_search_cb
        self._muted_until: float = 0.0
        self._death_timestamps: list = []
        self._system_prompt: Optional[str] = None

    # ── TTS / audio ──────────────────────────────────────────────────────────

    async def _synthesise(self, text: str) -> bytes:
        """Synthesise text via ElevenLabs."""
        vc = self._cfg.voice
        return await _elevenlabs_speak(
            text,
            api_key=self._cfg.elevenlabs_key(),
            voice_id=vc.voice_id,
            model_id=vc.tts_model,
            stability=vc.stability,
            similarity=vc.similarity,
            style=vc.style,
        )

    async def _speak(self, text: str) -> None:
        """Synthesise and play *text*, unless muted."""
        if time.time() < self._muted_until:
            logger.debug("Muted; skipping TTS: %r", text)
            return
        try:
            audio = await self._synthesise(text)
            await _sounddevice_play(audio)
        except Exception as exc:
            logger.error("TTS/playback failed: %s", exc)

    def _speak_bytes(self, audio_bytes: bytes) -> None:
        """Play pre-rendered audio bytes synchronously (for cached lines)."""
        asyncio.ensure_future(_sounddevice_play(audio_bytes))

    # ── STT ──────────────────────────────────────────────────────────────────

    async def _transcribe(self, wav_bytes: bytes) -> str:
        """Transcribe audio bytes using faster-whisper."""
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            ) from e

        vc = self._cfg.voice
        model = WhisperModel(
            vc.stt_model, device=vc.stt_device, compute_type=vc.stt_compute_type
        )
        # Write to temp file — faster-whisper requires a file path
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(wav_bytes)
            tmp.flush()
            segments, _ = model.transcribe(tmp.name, language="en", vad_filter=True)
            return " ".join(s.text for s in segments).strip()

    # ── LLM ──────────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if self._system_prompt is None:
            prompt_path = Path("jarvis_system_prompt.txt")
            if prompt_path.exists():
                self._system_prompt = prompt_path.read_text()
            else:
                from openjarvis.rs3.system_prompt import JARVIS_SYSTEM_PROMPT
                self._system_prompt = JARVIS_SYSTEM_PROMPT
        return self._system_prompt

    async def _ask_claude(self, user_text: str, game_ctx: dict) -> str:
        """Send a turn to Claude, resolve any tool calls, and return final text."""
        try:
            from anthropic import Anthropic  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            ) from e

        from openjarvis.rs3.tools.tool_handler import TOOL_SCHEMA, dispatch_tool

        client = Anthropic(api_key=self._cfg.anthropic_key())
        messages = [{
            "role": "user",
            "content": (
                f"<context>{json.dumps(game_ctx)}</context>\n"
                f"<user>{user_text}</user>"
            ),
        }]

        lc = self._cfg.llm
        for _turn in range(8):  # max tool-calling depth
            response = client.messages.create(
                model=lc.model,
                max_tokens=lc.max_tokens,
                system=self._load_system_prompt(),
                messages=messages,
                tools=TOOL_SCHEMA,
            )

            if response.stop_reason == "end_turn":
                # Extract text from final response
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                # Append assistant turn
                messages.append({"role": "assistant", "content": response.content})

                # Resolve tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_str = await dispatch_tool(
                            block.name,
                            block.input,
                            db_path=self._cfg.db_path,
                            speak_cb=self._speak,
                            hud_cb=self._hud_cb,
                            wiki_search_cb=self._wiki_search_cb,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return "I'm afraid something went awry, sir. Please try again."

    # ── Mic recording helpers ────────────────────────────────────────────────

    async def _record_utterance(self) -> bytes:
        """Record from mic until VAD detects silence, returning PCM bytes."""
        try:
            import sounddevice as sd  # type: ignore[import]
            import numpy as np
        except ImportError:
            logger.warning("sounddevice not installed — returning empty audio.")
            return b""

        import webrtcvad  # type: ignore[import]
        vad = webrtcvad.Vad(int(self._cfg.voice.vad_threshold * 3))

        frame_duration_ms = 30  # ms
        frame_samples = int(SAMPLE_RATE * frame_duration_ms / 1000)
        silence_frames = VAD_SILENCE_MS // frame_duration_ms
        max_frames = int(MAX_UTTERANCE_S * 1000 / frame_duration_ms)

        pcm_frames: list = []
        silent_count = 0
        speaking = False

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(max_frames):
                frame, _ = stream.read(frame_samples)
                pcm = frame.tobytes()
                is_speech = vad.is_speech(pcm, SAMPLE_RATE)

                if is_speech:
                    silent_count = 0
                    speaking = True
                else:
                    silent_count += 1

                if speaking:
                    pcm_frames.append(pcm)

                if speaking and silent_count >= silence_frames:
                    break

        return b"".join(pcm_frames)

    async def _listen_until_wake(self, wake_listener: WakeWordListener) -> None:
        """Block until the wake word is detected."""
        try:
            import sounddevice as sd  # type: ignore[import]
            import numpy as np
        except ImportError:
            logger.error("sounddevice not installed — waiting 5 s before proceeding.")
            await asyncio.sleep(5)
            return

        fl = wake_listener.frame_length
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=fl
        ) as stream:
            while True:
                frame, _ = stream.read(fl)
                pcm = frame[:, 0].tolist()
                if wake_listener.process(pcm):
                    logger.info("Wake word detected.")
                    return
                await asyncio.sleep(0)  # yield to event loop

    # ── Event detection helpers ──────────────────────────────────────────────

    def _record_death(self) -> None:
        """Record a death timestamp; detect losing streak (3 in 30 min)."""
        now = time.time()
        self._death_timestamps = [t for t in self._death_timestamps if now - t < 1800]
        self._death_timestamps.append(now)
        if len(self._death_timestamps) >= 3:
            asyncio.ensure_future(self._speak(
                "Perhaps a brief pause, sir. The boss will still be there."
            ))

    # ── Public run loop ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the voice loop. Blocks indefinitely."""
        from openjarvis.rs3.voice.personality import PersonalityPlayer

        wake = WakeWordListener(self._cfg.porcupine_key(), self._cfg.voice.wake_word)
        personality = PersonalityPlayer(
            voice_cache_dir=Path("voice_cache"),
            synthesise_fn=self._synthesise,
            play_fn=_sounddevice_play,
        )

        await personality.boot()
        logger.info("JARVIS voice loop started. Say %r to activate.", self._cfg.voice.wake_word)

        try:
            while True:
                await self._listen_until_wake(wake)
                pcm = await self._record_utterance()
                if not pcm:
                    continue

                wav = _pcm_to_wav(pcm)
                try:
                    text = await self._transcribe(wav)
                except Exception as exc:
                    logger.error("Transcription failed: %s", exc)
                    continue

                if not text:
                    continue

                logger.info("User said: %r", text)
                game_ctx = self._game_state_fn()

                try:
                    reply = await self._ask_claude(text, game_ctx)
                except Exception as exc:
                    logger.error("Claude request failed: %s", exc)
                    reply = "I encountered a technical difficulty, sir."

                logger.info("JARVIS: %r", reply)
                await self._speak(reply)

        except KeyboardInterrupt:
            logger.info("Shutting down.")
            await personality.shutdown()
        finally:
            wake.delete()
