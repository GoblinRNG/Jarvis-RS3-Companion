"""RS3 JARVIS configuration — loaded from config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PlayerConfig:
    rsn: str = "YourRSN"
    honorific: str = "sir"          # "sir" | "madam"
    ironman: bool = False
    hcim: bool = False
    combat_style: str = "necromancy"
    playtime_min_per_day: int = 90
    afk_preference: str = "semi"    # afk | semi | intensive | all


@dataclass
class VoiceConfig:
    wake_word: str = "jarvis"
    voice_id: str = ""
    stability: float = 0.55
    similarity: float = 0.85
    style: float = 0.30
    mute_hotkey: str = "ctrl+alt+m"
    hud_hotkey: str = "ctrl+alt+j"
    tts_model: str = "eleven_flash_v2"
    stt_model: str = "medium.en"
    stt_device: str = "auto"
    stt_compute_type: str = "int8"
    vad_threshold: float = 0.5


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 400
    temperature: float = 0.7


@dataclass
class DataConfig:
    ge_poll_seconds: int = 300
    hiscores_poll_seconds: int = 60
    wiki_refresh_cron: str = "0 4 * * *"
    db_path: str = "~/.jarvis_rs3/rs3.db"


@dataclass
class HUDConfig:
    enabled: bool = True
    position: str = "top_right"
    fade_seconds: int = 20
    always_on_top: bool = True


@dataclass
class APIKeysConfig:
    anthropic: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    elevenlabs: str = field(default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", ""))
    porcupine: str = field(default_factory=lambda: os.environ.get("PORCUPINE_ACCESS_KEY", ""))


@dataclass
class RS3Config:
    """Full RS3 JARVIS configuration."""

    player: PlayerConfig = field(default_factory=PlayerConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    data: DataConfig = field(default_factory=DataConfig)
    hud: HUDConfig = field(default_factory=HUDConfig)
    api_keys: APIKeysConfig = field(default_factory=APIKeysConfig)

    @property
    def db_path(self) -> Path:
        return Path(self.data.db_path).expanduser()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RS3Config":
        """Load configuration from a YAML file."""
        try:
            import yaml  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "PyYAML is required to load config.yaml. "
                "Install with: pip install pyyaml"
            ) from e

        raw = yaml.safe_load(Path(path).read_text())
        return cls._from_dict(raw or {})

    @classmethod
    def _from_dict(cls, d: dict) -> "RS3Config":
        def _get(section: str, klass):
            sub = d.get(section, {})
            fields = {f.name for f in klass.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            return klass(**{k: v for k, v in sub.items() if k in fields})

        return cls(
            player=_get("player", PlayerConfig),
            voice=_get("voice", VoiceConfig),
            llm=_get("llm", LLMConfig),
            data=_get("data", DataConfig),
            hud=_get("hud", HUDConfig),
            api_keys=_get("api_keys", APIKeysConfig),
        )

    @classmethod
    def default(cls) -> "RS3Config":
        """Return a default configuration instance."""
        return cls()

    # ── convenience helpers ──────────────────────────────────────────────────

    def anthropic_key(self) -> str:
        return self.api_keys.anthropic or os.environ.get("ANTHROPIC_API_KEY", "")

    def elevenlabs_key(self) -> str:
        return self.api_keys.elevenlabs or os.environ.get("ELEVENLABS_API_KEY", "")

    def porcupine_key(self) -> str:
        return self.api_keys.porcupine or os.environ.get("PORCUPINE_ACCESS_KEY", "")

    def honorific(self) -> str:
        return self.player.honorific
