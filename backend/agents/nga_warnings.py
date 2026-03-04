"""
Agent CHARLIE-C — NGA Maritime Warnings (NAVAREA)
==================================================
Fetches broadcast maritime warnings from the National Geospatial-Intelligence
Agency (NGA) MSI API. These are official NAVAREA navigation warnings covering
military exercises, hazardous areas, mine warnings, and other maritime threats.

Source: https://msi.gs.mil/api/publications/broadcast-warn
No API key required.

Key features
------------
• Polls NAVAREA I (NE Atlantic), II (NW Atlantic), III (S Atlantic),
  IV (Caribbean), IX (Persian Gulf/Red Sea), X (Arabian Sea), XI (Indian Ocean)
• Extracts coordinate blocks from warning text using regex
• Circuit breaker
• Broadcasts as naval_event category
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from typing import Optional

import httpx

from ..config import settings
from ..database import insert_event
from ..intelligence.confidence import initial_bba
from ..models.event import ConflictIntel, EventCategory, LocationEntity
from ..utils.circuit_breaker import CircuitBreaker
from ..websocket_manager import manager

logger = logging.getLogger("nga_warnings")

_cb = CircuitBreaker("nga", failure_threshold=3, recovery_timeout=300, cache_ttl=1800)
_SEEN: dict[str, float] = {}
_DEDUP_TTL_S = 86_400

# NAVAREA regions relevant to ARES theatre
NAVAREA_REGIONS = ["IX", "X", "XI", "I", "III"]

# Regex to extract DD or DM coordinates from NAVAREA warning text
_COORD_RE = re.compile(
    r"(\d{1,3})[°\-\s](\d{1,2}(?:\.\d+)?)[\'′\s]?([NS])\s*[,/]?\s*"
    r"(\d{1,3})[°\-\s](\d{1,2}(?:\.\d+)?)[\'′\s]?([EW])"
)


def _dms_to_dd(deg: float, minutes: float, direction: str) -> float:
    dd = deg + minutes / 60.0
    if direction in ("S", "W"):
        dd = -dd
    return dd


def _extract_coords(text: str) -> Optional[tuple[float, float]]:
    """Extract first coordinate pair from a NAVAREA warning text block."""
    m = _COORD_RE.search(text)
    if m:
        try:
            lat = _dms_to_dd(float(m.group(1)), float(m.group(2)), m.group(3))
            lon = _dms_to_dd(float(m.group(4)), float(m.group(5)), m.group(6))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except (ValueError, TypeError):
            pass
    return None


def _entry_hash(msgnum: str) -> str:
    return hashlib.sha256(str(msgnum).encode()).hexdigest()


def _prune_seen():
    cutoff = time.monotonic() - _DEDUP_TTL_S
    for k in [k for k, v in _SEEN.items() if v < cutoff]:
        del _SEEN[k]


async def _fetch_warnings(client: httpx.AsyncClient) -> Optional[list[dict]]:
    """Fetch NAVAREA broadcast warnings from NGA MSI API."""
    url = settings.NGA_BASE_URL
    try:
        resp = await client.get(
            url,
            params={"output": "json", "status": "active"},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # NGA API returns list or {"broadcastWarn": [...]}
        if isinstance(data, list):
            return data
        return data.get("broadcastWarn", data.get("items", []))
    except Exception as exc:
        logger.warning(f"[CHARLIE-C] NGA fetch failed: {exc}")
        raise


_fetch_warnings_safe = _cb.call(_fetch_warnings)


async def _process_warning(w: dict) -> Optional[dict]:
    msgnum = str(w.get("msgNum", w.get("number", w.get("id", ""))))
    h = _entry_hash(msgnum)
    if h in _SEEN:
        return None
    _SEEN[h] = time.monotonic()

    text    = w.get("text", w.get("body", ""))
    subject = w.get("subregion", w.get("subject", w.get("navArea", "")))
    coords  = _extract_coords(text)

    intel = ConflictIntel(
        raw_text        = text[:500],
        translation     = text[:500],
        category        = EventCategory.naval_event,
        confidence      = 0.75,
        source_language = "en",
        is_confirmed    = True,
    )

    if coords:
        intel.locations.append(LocationEntity(
            raw_text   = subject or "Maritime Warning",
            normalized = subject or "Maritime Warning",
            lat        = coords[0],
            lon        = coords[1],
            confidence = 0.85,
        ))

    alpha = 0.82  # NGA is official government source
    bba   = initial_bba(intel, alpha)
    intel.bel          = bba["belief"]
    intel.pl           = bba["plausibility"]
    intel.conflict_k   = bba["conflict_k"]
    intel.source_alpha = alpha

    try:
        eid = await insert_event(intel, source="nga")
    except Exception as exc:
        logger.error(f"[CHARLIE-C] DB insert failed: {exc}")
        return None

    payload = intel.model_dump()
    payload.update({
        "id":            eid,
        "source":        "nga",
        "nga_msgnum":    msgnum,
        "lat":           intel.lat,
        "lon":           intel.lon,
        "location_name": intel.location_name or subject,
        "category":      "naval_event",
        "fusion_status": intel.fusion_status,
        "subject":       subject,
    })

    await manager.broadcast_json(payload)
    logger.info(f"[CHARLIE-C] NAVAREA warning {msgnum}: {subject[:60]}")
    return payload


async def poll_nga():
    """Main coroutine for Agent CHARLIE-C."""
    if not settings.ENABLE_NGA:
        logger.info("[CHARLIE-C] Agent disabled via ENABLE_NGA")
        while True:
            await asyncio.sleep(3600)

    interval = settings.NGA_POLL_INTERVAL
    logger.info(f"[CHARLIE-C] NGA warnings starting — poll interval {interval}s")

    while True:
        cycle_start = time.monotonic()
        _prune_seen()

        async with httpx.AsyncClient(headers={"User-Agent": "ARES-OSINT/1.0"}) as client:
            warnings = await _fetch_warnings_safe(client)

        ingested = 0
        if warnings:
            for w in warnings:
                try:
                    r = await _process_warning(w)
                    if r:
                        ingested += 1
                except Exception as exc:
                    logger.error(f"[CHARLIE-C] Unhandled error: {exc}", exc_info=True)

        elapsed = time.monotonic() - cycle_start
        logger.info(
            f"[CHARLIE-C] Cycle: {len(warnings or [])} warnings, "
            f"{ingested} new in {elapsed:.1f}s. CB={_cb.state.value}"
        )
        await asyncio.sleep(max(0.0, interval - elapsed))
