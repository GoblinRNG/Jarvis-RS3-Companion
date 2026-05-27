"""RS3 JARVIS — one-shot setup wizard.

Run once to go from zero to a working Phase-1 voice loop::

    python scripts/setup_rs3.py

What it does
------------
1.  Checks Python 3.10+
2.  Installs all Phase-1 Python dependencies
3.  Collects API keys interactively (or reads from .env / env vars)
4.  Clones the JARVIS voice on ElevenLabs from voice_cache/ samples
5.  Updates config.yaml and .env with the voice_id and RSN
6.  Initialises the SQLite knowledge database and seeds it
7.  Runs a full smoke test (Claude ping · Porcupine · audio playback)
8.  Prints the launch command

Requirements: Python 3.10+ and pip on PATH.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── ANSI colours ─────────────────────────────────────────────────────────────
R = "\033[1;31m"  # bold red
G = "\033[1;32m"  # bold green
Y = "\033[1;33m"  # bold yellow
B = "\033[1;34m"  # bold blue
C = "\033[1;36m"  # bold cyan
W = "\033[0m"     # reset

def ok(msg: str)   -> None: print(f"{G}  ✔  {msg}{W}")
def info(msg: str) -> None: print(f"{B}  ℹ  {msg}{W}")
def warn(msg: str) -> None: print(f"{Y}  ⚠  {msg}{W}")
def err(msg: str)  -> None: print(f"{R}  ✘  {msg}{W}", file=sys.stderr)
def hdr(msg: str)  -> None: print(f"\n{C}{'─'*60}\n  {msg}\n{'─'*60}{W}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kwargs)


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    """Prompt the user for a value; return default if they just hit Enter."""
    import getpass
    prompt_str = f"  {label}"
    if default:
        prompt_str += f" [{default[:6]}…]" if secret and default else f" [{default}]"
    prompt_str += ": "
    val = (getpass.getpass(prompt_str) if secret else input(prompt_str)).strip()
    return val or default


def _load_env() -> dict[str, str]:
    """Load .env if it exists; return a dict of key→value."""
    env_path = ROOT / ".env"
    result: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _write_env(values: dict[str, str]) -> None:
    env_path = ROOT / ".env"
    # Merge with existing
    existing = _load_env()
    existing.update(values)
    lines = [f"{k}={v}" for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n")
    ok(f".env written to {env_path}")


def _patch_yaml(key_path: list[str], value: str) -> None:
    """Simple YAML patcher — updates a leaf value at the given key path."""
    config_path = ROOT / "config.yaml"
    text = config_path.read_text()
    leaf = key_path[-1]
    pattern = rf'(^\s*{re.escape(leaf)}:\s*)["\']?[^"\'#\n]*["\']?'
    replacement = rf'\g<1>"{value}"'
    new_text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    config_path.write_text(new_text)


# ── Steps ────────────────────────────────────────────────────────────────────

def step_check_python() -> None:
    hdr("Step 1 — Python version")
    v = sys.version_info
    if v < (3, 10):
        err(f"Python 3.10+ required; you have {v.major}.{v.minor}. Please upgrade.")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def step_install_deps() -> None:
    hdr("Step 2 — Installing Python dependencies")
    req = ROOT / "requirements-rs3.txt"
    info(f"pip install -r {req.name}")
    try:
        _run([sys.executable, "-m", "pip", "install", "-r", str(req), "-q"])
        ok("Dependencies installed")
    except subprocess.CalledProcessError:
        err("pip install failed — check your internet connection and try again.")
        sys.exit(1)

    # Also install the package itself in editable mode
    try:
        _run([sys.executable, "-m", "pip", "install", "-e", str(ROOT), "-q"])
        ok("openjarvis package installed (editable)")
    except subprocess.CalledProcessError:
        warn("Could not install openjarvis in editable mode — continuing anyway.")


def step_collect_keys(env: dict[str, str]) -> dict[str, str]:
    hdr("Step 3 — API keys")
    print(f"""
  You need three free API keys.  Get them here:

  {B}Anthropic{W}  → https://console.anthropic.com/  (Claude API)
  {B}ElevenLabs{W} → https://elevenlabs.io/           (voice cloning + TTS)
  {B}Picovoice{W}  → https://console.picovoice.ai/    (wake word "JARVIS")

  Press Enter to keep an existing value shown in [brackets].
""")

    keys: dict[str, str] = {}

    keys["ANTHROPIC_API_KEY"] = _prompt(
        "Anthropic API key",
        default=env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
        secret=True,
    )
    if not keys["ANTHROPIC_API_KEY"]:
        err("Anthropic API key is required.")
        sys.exit(1)

    keys["ELEVENLABS_API_KEY"] = _prompt(
        "ElevenLabs API key",
        default=env.get("ELEVENLABS_API_KEY", os.environ.get("ELEVENLABS_API_KEY", "")),
        secret=True,
    )
    if not keys["ELEVENLABS_API_KEY"]:
        err("ElevenLabs API key is required.")
        sys.exit(1)

    keys["PORCUPINE_ACCESS_KEY"] = _prompt(
        "Picovoice access key",
        default=env.get("PORCUPINE_ACCESS_KEY", os.environ.get("PORCUPINE_ACCESS_KEY", "")),
        secret=True,
    )
    if not keys["PORCUPINE_ACCESS_KEY"]:
        err("Picovoice access key is required.")
        sys.exit(1)

    return keys


def step_player_config() -> dict[str, str]:
    hdr("Step 4 — Player settings")
    rsn = _prompt("Your RuneScape Name (RSN)", default="YourRSN")
    honorific = _prompt("Honorific (sir / madam)", default="sir")
    while honorific not in ("sir", "madam"):
        honorific = _prompt("Please enter 'sir' or 'madam'", default="sir")
    combat = _prompt(
        "Combat style (melee / range / magic / necromancy)",
        default="necromancy",
    )
    afk = _prompt(
        "AFK preference (afk / semi / intensive / all)",
        default="semi",
    )
    return {"rsn": rsn, "honorific": honorific, "combat_style": combat, "afk_preference": afk}


def step_clone_voice(api_key: str, existing_voice_id: str) -> str:
    hdr("Step 5 — ElevenLabs voice cloning")

    if existing_voice_id:
        reuse = _prompt(
            f"Found existing voice_id [{existing_voice_id[:8]}…]. Reuse it? (y/n)",
            default="y",
        )
        if reuse.lower() != "n":
            ok(f"Reusing existing voice (id={existing_voice_id})")
            return existing_voice_id

    try:
        from elevenlabs import ElevenLabs  # type: ignore[import]
    except ImportError:
        err("elevenlabs package not available despite install — check pip output above.")
        sys.exit(1)

    client = ElevenLabs(api_key=api_key)

    # Check for existing JARVIS voice on the account
    try:
        existing = client.voices.get_all()
        for voice in existing.voices:
            if voice.name.lower() == "jarvis":
                ok(f"Found JARVIS voice on your account (id={voice.voice_id})")
                return voice.voice_id
    except Exception as exc:
        warn(f"Could not list voices: {exc}")

    # Upload samples
    sample_files = [
        ROOT / "voice_cache" / "Voicy_At_Your_Service_Sir.mp3",
        ROOT / "voice_cache" / "Voicy_May_I_Remind_You.mp3",
        ROOT / "voice_cache" / "Voicy_As_You_Wish_.mp3",
        ROOT / "voice_cache" / "Voicy_Jarvis_Start_Up.mp3",
    ]
    samples = [p for p in sample_files if p.exists()]
    if not samples:
        err("No voice samples found in voice_cache/. Cannot clone.")
        sys.exit(1)

    info(f"Uploading {len(samples)} samples to ElevenLabs Instant Voice Cloning…")
    for s in samples:
        info(f"  {s.name} ({s.stat().st_size // 1024} KB)")

    try:
        voice = client.voices.add(
            name="JARVIS",
            description="Refined British butler — calm, articulate, dry wit.",
            files=[str(p) for p in samples],
            labels={"accent": "british", "style": "butler"},
        )
        voice_id: str = voice.voice_id
        ok(f"Voice clone created! voice_id = {voice_id}")
        return voice_id
    except Exception as exc:
        err(f"Voice cloning failed: {exc}")
        info("You can clone manually at https://elevenlabs.io/voice-lab and paste the ID.")
        fallback = _prompt("Paste voice_id manually (or press Enter to skip)", default="")
        if not fallback:
            warn("No voice_id set — TTS will fall back to text logging until you add it.")
        return fallback


def step_write_config(keys: dict[str, str], player: dict[str, str], voice_id: str) -> None:
    hdr("Step 6 — Updating config.yaml")

    # Write .env
    env_values = dict(keys)
    if voice_id:
        env_values["ELEVENLABS_VOICE_ID"] = voice_id
    _write_env(env_values)

    # Patch config.yaml fields
    _patch_yaml(["rsn"], player["rsn"])
    _patch_yaml(["honorific"], player["honorific"])
    _patch_yaml(["combat_style"], player["combat_style"])
    _patch_yaml(["afk_preference"], player["afk_preference"])
    if voice_id:
        _patch_yaml(["voice_id"], voice_id)

    ok("config.yaml patched")


def step_init_db() -> None:
    hdr("Step 7 — Initialising knowledge database")
    try:
        from openjarvis.rs3.db.schema import init_db
        from openjarvis.rs3.db.seed_data import seed_all
        db_path = init_db()
        seed_all(db_path)
        ok(f"Database ready at {db_path}")
    except Exception as exc:
        err(f"Database init failed: {exc}")
        sys.exit(1)


def step_prewarm_whisper() -> None:
    hdr("Step 8 — Pre-downloading Whisper model")
    info("Downloading faster-whisper 'medium.en' (~1.5 GB) — one-time download…")
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
        # Load with int8 quantization to reduce VRAM/RAM requirement
        model = WhisperModel("medium.en", device="auto", compute_type="int8")
        ok("Whisper 'medium.en' model ready")
        del model
    except ImportError:
        warn("faster-whisper not available — STT will fail at runtime.")
    except Exception as exc:
        warn(f"Whisper pre-warm failed: {exc} — will retry at runtime.")


def step_smoke_test(keys: dict[str, str], voice_id: str) -> None:
    hdr("Step 9 — Smoke test")

    # Set env vars for the test
    for k, v in keys.items():
        os.environ[k] = v
    if voice_id:
        os.environ["ELEVENLABS_VOICE_ID"] = voice_id

    # ── Claude ping ───────────────────────────────────────────────────────
    info("Testing Claude API connection…")
    try:
        from anthropic import Anthropic  # type: ignore[import]
        client = Anthropic(api_key=keys["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": "Say only: ready"}],
        )
        ok(f"Claude API OK — response: {resp.content[0].text!r}")
    except Exception as exc:
        err(f"Claude API failed: {exc}")
        warn("Check your ANTHROPIC_API_KEY and billing.")

    # ── Porcupine ─────────────────────────────────────────────────────────
    info("Testing Porcupine wake-word engine…")
    try:
        import pvporcupine  # type: ignore[import]
        pico = pvporcupine.create(
            access_key=keys["PORCUPINE_ACCESS_KEY"],
            keywords=["jarvis"],
        )
        pico.delete()
        ok("Porcupine OK — 'jarvis' built-in keyword loaded")
    except Exception as exc:
        err(f"Porcupine failed: {exc}")
        warn("Check your PORCUPINE_ACCESS_KEY at https://console.picovoice.ai/")

    # ── ElevenLabs TTS → audio playback ──────────────────────────────────
    if voice_id:
        info("Testing ElevenLabs TTS + audio playback (will speak one line)…")
        try:
            from elevenlabs import ElevenLabs, VoiceSettings  # type: ignore[import]
            import sounddevice as sd  # type: ignore[import]
            import numpy as np
            import io

            el = ElevenLabs(api_key=keys["ELEVENLABS_API_KEY"])
            audio_iter = el.text_to_speech.convert(
                voice_id=voice_id,
                text="At your service, sir.",
                model_id="eleven_flash_v2",
                voice_settings=VoiceSettings(stability=0.55, similarity_boost=0.85, style=0.30),
            )
            audio_bytes = b"".join(c for c in audio_iter if isinstance(c, bytes))

            try:
                import pydub  # type: ignore[import]
                seg = pydub.AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
                sd.play(samples, samplerate=seg.frame_rate)
                sd.wait()
                ok("Audio playback OK — you should have heard JARVIS!")
            except ImportError:
                ok("TTS synthesis OK (pydub not installed; skipping playback)")
        except Exception as exc:
            err(f"ElevenLabs/audio test failed: {exc}")
            warn("Check ELEVENLABS_API_KEY and that your speakers/headphones are connected.")
    else:
        warn("Skipping TTS test (no voice_id). Add voice_id to config.yaml to enable.")


def step_done() -> None:
    hdr("✅  Setup complete — JARVIS is ready!")
    print(f"""
  ─── Launch (full voice loop — needs mic + speakers) ───────────────────
    {G}python run_jarvis.py{W}

  ─── Quick text test (no mic needed) ──────────────────────────────────
    {G}python scripts/test_jarvis.py{W}
    {G}python scripts/test_jarvis.py --speak{W}  ← plays TTS audio too

  ─── How to use ──────────────────────────────────────────────────────
  Say  {Y}\"JARVIS\"{W}  then speak your question.  Examples:
    • "What should I train for slayer tonight?"
    • "What boss should I farm for GP right now?"
    • "Can I start Sliske's Endgame?"
    • "How long to 99 Herblore making saradomin brews?"
    • "Remind me in 30 minutes to do my herb run."
    • "Run my daily checklist."

  ─── API key docs ─────────────────────────────────────────────────────
    Anthropic  → https://docs.anthropic.com/
    ElevenLabs → https://elevenlabs.io/docs/
    Picovoice  → https://picovoice.ai/docs/quick-start/porcupine-python/
""")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Must run from or have access to the project root
    os.chdir(ROOT)

    print(f"""
{C}╔══════════════════════════════════════════════════════╗
║          RS3 JARVIS — Phase 1 Setup Wizard           ║
╚══════════════════════════════════════════════════════╝{W}
  This will install dependencies, clone your butler voice,
  and verify everything works before you launch.
""")

    env = _load_env()

    step_check_python()
    step_install_deps()

    keys = step_collect_keys(env)
    player = step_player_config()

    existing_voice_id = (
        env.get("ELEVENLABS_VOICE_ID")
        or os.environ.get("ELEVENLABS_VOICE_ID", "")
    )
    voice_id = step_clone_voice(keys["ELEVENLABS_API_KEY"], existing_voice_id)

    step_write_config(keys, player, voice_id)
    step_init_db()
    step_prewarm_whisper()
    step_smoke_test(keys, voice_id)
    step_done()


if __name__ == "__main__":
    main()
