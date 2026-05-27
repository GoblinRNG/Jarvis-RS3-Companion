"""Grand Exchange live price fetching with 5-minute in-memory cache.

Uses the official Jagex GE API — no auth required.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_GE_CACHE: Dict[str, dict] = {}
_CACHE_TTL = 300  # seconds

# RS3 GE API endpoint
_GE_API = "https://secure.runescape.com/m=itemdb_rs/api/catalogue/detail.json"

# Minimal static item-name → item-id table for common items.
# In production this is populated from a full wiki scrape / SQLite lookup.
_ITEM_IDS: Dict[str, int] = {
    "abyssal whip": 4151,
    "dragon bones": 536,
    "yak-hide": 10820,
    "dwarf weed": 217,
    "lantadyme": 2481,
    "snapdragon": 3051,
    "torstol": 219,
    "rocktail": 15272,
    "sharks": 383,
    "monkfish": 7944,
    "magic logs": 1513,
    "yew logs": 1515,
    "rune ore": 447,
    "runite ore": 447,
    "coal": 453,
    "iron ore": 440,
    "nature rune": 561,
    "death rune": 560,
    "blood rune": 565,
    "soul rune": 566,
    "astral rune": 9075,
    "overload": 15332,
    "extreme attack": 15308,
    "extreme strength": 15309,
    "extreme defence": 15310,
    "extreme magic": 15313,
    "extreme ranging": 15316,
    "super restore": 3024,
    "prayer potion": 2434,
    "saradomin brew": 6685,
    "aggression potion": 37851,
    "antifire potion": 2452,
    "elder overload": 38932,
    "supreme overload": 33209,
    "dragonkin lamp": 33818,
}


async def resolve_item_id(item_name: str) -> Optional[int]:
    """Resolve an item name to its GE item ID.

    Checks the static table first; falls back to the GE search API.
    """
    normalised = item_name.lower().strip()
    if normalised in _ITEM_IDS:
        return _ITEM_IDS[normalised]

    # Try GE search API
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://secure.runescape.com/m=itemdb_rs/api/catalogue/items.json",
                params={"category": 1, "alpha": normalised[:1], "page": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("items", []):
                if item.get("name", "").lower() == normalised:
                    item_id = item["id"]
                    _ITEM_IDS[normalised] = item_id  # warm cache
                    return item_id
    except Exception as exc:
        logger.warning("GE search failed for %r: %s", item_name, exc)

    return None


async def get_ge_price(item_name: str) -> dict:
    """Fetch the current Grand Exchange price for *item_name*.

    Returns a dict with keys: name, price, trend, high_alch, cached_at.
    Raises ``ValueError`` if the item cannot be resolved.
    """
    key = item_name.lower().strip()

    # Serve from cache if still fresh
    if key in _GE_CACHE and time.time() - _GE_CACHE[key]["t"] < _CACHE_TTL:
        return _GE_CACHE[key]["data"]

    item_id = await resolve_item_id(key)
    if item_id is None:
        raise ValueError(f"Cannot resolve item ID for {item_name!r}")

    async with httpx.AsyncClient(timeout=8) as client:
        resp = await client.get(_GE_API, params={"item": item_id})
        resp.raise_for_status()
        raw = resp.json()["item"]

    # Normalise the price string (may be "1,234" or "1.2k")
    def _parse_price(p: str | int) -> int:
        if isinstance(p, int):
            return p
        p = str(p).replace(",", "").strip()
        if p.endswith("k"):
            return int(float(p[:-1]) * 1_000)
        if p.endswith("m"):
            return int(float(p[:-1]) * 1_000_000)
        if p.endswith("b"):
            return int(float(p[:-1]) * 1_000_000_000)
        return int(p) if p.isdigit() else 0

    result = {
        "name": raw["name"],
        "price": _parse_price(raw["current"]["price"]),
        "trend": raw["current"]["trend"],
        "high_alch": raw.get("highalch", 0),
        "members": raw.get("members", "true") == "true",
        "cached_at": time.time(),
    }
    _GE_CACHE[key] = {"t": time.time(), "data": result}
    return result


# ── Tool schema ──────────────────────────────────────────────────────────────

GE_PRICE_SCHEMA = {
    "name": "get_ge_price",
    "description": "Fetch live Grand Exchange price for an item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "item_name": {"type": "string", "description": "The item name to look up."},
        },
        "required": ["item_name"],
    },
}
