"""Quick smoke-test: ask JARVIS one RS3 question via text (no microphone needed).

Usage::

    python scripts/test_jarvis.py
    python scripts/test_jarvis.py --question "How long to 99 slayer from 85 at Croesus?"
    python scripts/test_jarvis.py --speak     # also play TTS audio

The script loads .env, sends the question to Claude with the full JARVIS system
prompt + all RS3 tools, and prints (and optionally speaks) the reply.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Auto-load .env
try:
    from dotenv import load_dotenv  # type: ignore[import]
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

DEFAULT_QUESTION = "What should I train tonight to get 99 Slayer as efficiently as possible?"


async def ask(question: str, speak: bool) -> None:
    try:
        from anthropic import Anthropic  # type: ignore[import]
    except ImportError:
        print("ERROR: anthropic not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Run setup_rs3.py first.", file=sys.stderr)
        sys.exit(1)

    from openjarvis.rs3.config import RS3Config
    from openjarvis.rs3.game_state import GameStateCollector
    from openjarvis.rs3.tools.tool_handler import TOOL_SCHEMA, dispatch_tool
    from openjarvis.rs3.db.schema import init_db
    from openjarvis.rs3.db.seed_data import seed_all

    # Bootstrap DB
    db_path = init_db()
    seed_all(db_path)

    cfg = RS3Config.from_yaml(ROOT / "config.yaml") if (ROOT / "config.yaml").exists() else RS3Config.default()
    collector = GameStateCollector(cfg)
    game_ctx = collector.collect()

    # Load system prompt
    prompt_file = ROOT / "jarvis_system_prompt.txt"
    system = prompt_file.read_text() if prompt_file.exists() else (
        "You are JARVIS, a refined British butler and RuneScape 3 expert. "
        "Be concise — 1-3 spoken sentences."
    )

    client = Anthropic(api_key=api_key)
    messages = [{
        "role": "user",
        "content": (
            f"<context>{json.dumps(game_ctx)}</context>\n"
            f"<user>{question}</user>"
        ),
    }]

    print(f"\n\033[1;34mYou:\033[0m  {question}\n")

    # Agentic loop (up to 8 tool-call rounds)
    for _round in range(8):
        response = client.messages.create(
            model=cfg.llm.model,
            max_tokens=cfg.llm.max_tokens,
            system=system,
            messages=messages,
            tools=TOOL_SCHEMA,
        )

        if response.stop_reason == "end_turn":
            reply = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reply = block.text
                    break
            print(f"\033[1;32mJARVIS:\033[0m  {reply}\n")

            if speak:
                await _speak_reply(cfg, reply)
            return

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  \033[1;33m[tool]\033[0m  {block.name}({json.dumps(block.input)[:80]})")
                    result_str = await dispatch_tool(block.name, block.input, db_path=db_path)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    print("(no response after tool loop)")


async def _speak_reply(cfg, text: str) -> None:
    voice_id = cfg.voice.voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
    el_key = cfg.elevenlabs_key()
    if not el_key or not voice_id:
        print("  (TTS skipped — no ELEVENLABS_API_KEY or voice_id)")
        return
    try:
        from elevenlabs import ElevenLabs, VoiceSettings  # type: ignore[import]
        import sounddevice as sd  # type: ignore[import]
        import numpy as np
        import io

        el = ElevenLabs(api_key=el_key)
        audio_iter = el.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=cfg.voice.tts_model,
            voice_settings=VoiceSettings(
                stability=cfg.voice.stability,
                similarity_boost=cfg.voice.similarity,
                style=cfg.voice.style,
            ),
        )
        audio_bytes = b"".join(c for c in audio_iter if isinstance(c, bytes))

        import pydub  # type: ignore[import]
        seg = pydub.AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
        sd.play(samples, samplerate=seg.frame_rate)
        sd.wait()
    except Exception as exc:
        print(f"  (TTS error: {exc})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-mode JARVIS smoke test")
    parser.add_argument("--question", "-q", default=DEFAULT_QUESTION,
                        help="Question to ask JARVIS")
    parser.add_argument("--speak", action="store_true",
                        help="Play TTS audio of the response")
    args = parser.parse_args()

    asyncio.run(ask(args.question, speak=args.speak))


if __name__ == "__main__":
    main()
