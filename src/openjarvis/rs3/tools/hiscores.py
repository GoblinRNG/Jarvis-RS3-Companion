"""Player Hiscores lookup via Jagex public API."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_HISCORE_CACHE: Dict[str, dict] = {}
_CACHE_TTL = 60  # seconds

_HISCORES_URL = "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json"
_RS3_HISCORES_URL = "https://secure.runescape.com/m=hiscore/index_lite.json"

# Ordered skill names as returned by the RS3 hiscores CSV endpoint
_SKILL_ORDER = [
    "overall", "attack", "defence", "strength", "constitution",
    "ranged", "prayer", "magic", "cooking", "woodcutting",
    "fletching", "fishing", "firemaking", "crafting", "smithing",
    "mining", "herblore", "agility", "thieving", "slayer",
    "farming", "runecrafting", "hunter", "construction", "summoning",
    "dungeoneering", "divination", "invention", "archaeology", "necromancy",
]


async def get_hiscores(rsn: str) -> dict:
    """Fetch RS3 hiscores for *rsn*.

    Returns a dict mapping skill name → {rank, level, xp}.
    Raises ``ValueError`` if the player is not found.
    """
    key = rsn.lower().strip()

    if key in _HISCORE_CACHE and time.time() - _HISCORE_CACHE[key]["t"] < _CACHE_TTL:
        return _HISCORE_CACHE[key]["data"]

    url = f"https://secure.runescape.com/m=hiscore/index_lite.ws?player={rsn}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            raise ValueError(f"Player {rsn!r} not found on hiscores.")
        resp.raise_for_status()
        text = resp.text

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    skills: dict = {}
    for i, line in enumerate(lines[: len(_SKILL_ORDER)]):
        parts = line.split(",")
        if len(parts) >= 3:
            skill = _SKILL_ORDER[i] if i < len(_SKILL_ORDER) else f"skill_{i}"
            try:
                skills[skill] = {
                    "rank": int(parts[0]),
                    "level": int(parts[1]),
                    "xp": int(parts[2]),
                }
            except ValueError:
                skills[skill] = {"rank": -1, "level": 1, "xp": 0}

    result = {"rsn": rsn, "skills": skills, "fetched_at": time.time()}
    _HISCORE_CACHE[key] = {"t": time.time(), "data": result}
    return result


def total_level(hiscores: dict) -> int:
    """Sum skill levels from a hiscores result dict."""
    return sum(s["level"] for s in hiscores.get("skills", {}).values() if s["level"] > 0)


def combat_level(hiscores: dict) -> float:
    """Estimate RS3 combat level from hiscores data (RS3 formula)."""
    s = hiscores.get("skills", {})

    def lvl(skill: str) -> int:
        return s.get(skill, {}).get("level", 1)

    base = 0.25 * (lvl("defence") + lvl("constitution") + lvl("prayer") // 2)
    melee = 0.325 * (lvl("attack") + lvl("strength"))
    ranged = 0.325 * (1.5 * lvl("ranged"))
    magic = 0.325 * (1.5 * lvl("magic"))
    necromancy = 0.325 * (1.5 * lvl("necromancy"))
    return round(base + max(melee, ranged, magic, necromancy), 1)


# ── Tool schema ──────────────────────────────────────────────────────────────

HISCORES_SCHEMA = {
    "name": "get_hiscores",
    "description": "Fetch player hiscores by RSN (RuneScape player name).",
    "input_schema": {
        "type": "object",
        "properties": {
            "rsn": {"type": "string", "description": "The player's RuneScape Name."},
        },
        "required": ["rsn"],
    },
}
