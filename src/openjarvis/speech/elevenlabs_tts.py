"""ElevenLabs text-to-speech backend — cloned JARVIS voice.

Requires the ``elevenlabs`` package::

    pip install elevenlabs

Configure via env var ``ELEVENLABS_API_KEY`` or pass ``api_key`` directly.
Voice settings mirror the JARVIS spec: stability 0.55, similarity 0.85, style 0.30.
"""

from __future__ import annotations

import os
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

try:
    from elevenlabs import ElevenLabs, VoiceSettings  # type: ignore[import]
except ImportError:
    ElevenLabs = None  # type: ignore[assignment, misc]
    VoiceSettings = None  # type: ignore[assignment, misc]


@TTSRegistry.register("elevenlabs")
class ElevenLabsTTSBackend(TTSBackend):
    """ElevenLabs TTS backend using the Flash v2 model for low-latency synthesis.

    Parameters
    ----------
    api_key:
        ElevenLabs API key. Falls back to ``ELEVENLABS_API_KEY`` env var.
    voice_id:
        ID of the cloned JARVIS voice. Falls back to ``ELEVENLABS_VOICE_ID`` env var.
    model_id:
        ElevenLabs model to use. Default is ``eleven_flash_v2`` for low latency.
    stability:
        Voice stability (0.0–1.0). JARVIS default: 0.55.
    similarity_boost:
        Similarity boost (0.0–1.0). JARVIS default: 0.85.
    style:
        Style exaggeration (0.0–1.0). JARVIS default: 0.30.
    """

    backend_id = "elevenlabs"

    def __init__(
        self,
        *,
        api_key: str = "",
        voice_id: str = "",
        model_id: str = "eleven_flash_v2",
        stability: float = 0.55,
        similarity_boost: float = 0.85,
        style: float = 0.30,
    ) -> None:
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self._voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
        self._model_id = model_id
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if ElevenLabs is None:
            raise ImportError(
                "elevenlabs is not installed. "
                "Install with: pip install elevenlabs"
            )
        self._client = ElevenLabs(api_key=self._api_key)
        return self._client

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> TTSResult:
        """Synthesise text and return a TTSResult with MP3 audio bytes."""
        client = self._ensure_client()
        vid = voice_id or self._voice_id
        if not vid:
            raise ValueError(
                "voice_id must be set — either in config.yaml (voice.voice_id) "
                "or via the ELEVENLABS_VOICE_ID environment variable."
            )

        audio_iter = client.text_to_speech.convert(
            voice_id=vid,
            text=text,
            model_id=self._model_id,
            voice_settings=VoiceSettings(
                stability=self._stability,
                similarity_boost=self._similarity_boost,
                style=self._style,
            ),
        )

        chunks = []
        for chunk in audio_iter:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
        audio_bytes = b"".join(chunks)

        return TTSResult(
            audio=audio_bytes,
            format="mp3",
            voice_id=vid,
            sample_rate=44_100,
            metadata={"model": self._model_id},
        )

    def available_voices(self) -> List[str]:
        """Return available voice IDs from the ElevenLabs account."""
        client = self._ensure_client()
        try:
            resp = client.voices.get_all()
            return [v.voice_id for v in resp.voices]
        except Exception:
            return []

    def health(self) -> bool:
        """Check if ElevenLabs package is installed and API key is set."""
        return ElevenLabs is not None and bool(self._api_key)
