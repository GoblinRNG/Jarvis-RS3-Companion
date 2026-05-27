"""Upload voice_cache/ samples to ElevenLabs and create the JARVIS clone.

Usage::

    python scripts/clone_voice.py --api-key YOUR_KEY
    python scripts/clone_voice.py          # reads ELEVENLABS_API_KEY env var

The voice_id is printed to stdout so setup_rs3.py can capture it,
and it is also written back to config.yaml and .env automatically.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Speech-only samples are best for cloning — exclude the startup jingle
VOICE_SAMPLES = [
    ROOT / "voice_cache" / "Voicy_At_Your_Service_Sir.mp3",
    ROOT / "voice_cache" / "Voicy_May_I_Remind_You.mp3",
    ROOT / "voice_cache" / "Voicy_As_You_Wish_.mp3",
    ROOT / "voice_cache" / "Voicy_Jarvis_Start_Up.mp3",  # add jingle last for more audio
]


def _patch_config(voice_id: str) -> None:
    """Write the voice_id back into config.yaml and .env."""
    config_path = ROOT / "config.yaml"
    if config_path.exists():
        text = config_path.read_text()
        import re
        text = re.sub(
            r'(voice_id:\s*")[^"]*(")',
            rf'\g<1>{voice_id}\g<2>',
            text,
        )
        # also handle unquoted empty value
        text = re.sub(
            r'(voice_id:\s*)(\s*#.*)?$',
            rf'\1"{voice_id}"  # ElevenLabs cloned voice',
            text,
            flags=re.MULTILINE,
        )
        config_path.write_text(text)
        print(f"  ✔  config.yaml updated (voice_id = {voice_id})")

    env_path = ROOT / ".env"
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("ELEVENLABS_VOICE_ID"):
                new_lines.append(f"ELEVENLABS_VOICE_ID={voice_id}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"ELEVENLABS_VOICE_ID={voice_id}")
        env_path.write_text("\n".join(new_lines) + "\n")
        print(f"  ✔  .env updated (ELEVENLABS_VOICE_ID = {voice_id})")


def clone_voice(api_key: str, force: bool = False) -> str:
    """Create (or return existing) the JARVIS voice clone.

    Returns the voice_id string.
    """
    try:
        from elevenlabs import ElevenLabs  # type: ignore[import]
    except ImportError:
        print("ERROR: elevenlabs not installed. Run: pip install elevenlabs", file=sys.stderr)
        sys.exit(1)

    client = ElevenLabs(api_key=api_key)

    # Check if we already have a JARVIS clone
    if not force:
        existing = client.voices.get_all()
        for voice in existing.voices:
            if voice.name.lower() == "jarvis":
                print(f"  ℹ  Found existing JARVIS voice (id={voice.voice_id}). "
                      "Pass --force to re-clone.")
                return voice.voice_id

    # Gather sample files
    samples = [p for p in VOICE_SAMPLES if p.exists()]
    if not samples:
        print("ERROR: No voice samples found in voice_cache/", file=sys.stderr)
        sys.exit(1)

    print(f"  ⬆  Uploading {len(samples)} sample(s) to ElevenLabs Instant Voice Cloning…")
    for s in samples:
        print(f"       {s.name} ({s.stat().st_size // 1024} KB)")

    voice = client.voices.add(
        name="JARVIS",
        description=(
            "Refined British butler — calm, articulate, dry wit. "
            "The JARVIS RS3 companion voice."
        ),
        files=[str(p) for p in samples],
        labels={"accent": "british", "style": "butler"},
    )

    voice_id: str = voice.voice_id
    print(f"  ✔  Voice clone created! voice_id = {voice_id}")
    return voice_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone the JARVIS voice on ElevenLabs")
    parser.add_argument("--api-key", default=os.environ.get("ELEVENLABS_API_KEY", ""),
                        help="ElevenLabs API key (or set ELEVENLABS_API_KEY env var)")
    parser.add_argument("--force", action="store_true",
                        help="Re-clone even if a JARVIS voice already exists")
    parser.add_argument("--no-patch", action="store_true",
                        help="Skip patching config.yaml and .env")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: No ElevenLabs API key. Use --api-key or set ELEVENLABS_API_KEY.",
              file=sys.stderr)
        sys.exit(1)

    voice_id = clone_voice(args.api_key, force=args.force)

    if not args.no_patch:
        _patch_config(voice_id)

    # Always print so callers can capture it
    print(voice_id)


if __name__ == "__main__":
    main()
