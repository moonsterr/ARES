"""
Agent CHARLIE-B — UCDP Conflict Event Fetcher
==============================================
Fetches from the Uppsala Conflict Data Program (UCDP) GED API.
UCDP is an academically rigorous dataset — lower velocity than ACLED
but higher precision. Best used for context/baseline enrichment.

API: https://ucdpapi.pcr.uu.se/api/gedevents/24.1
No API key required.

Key features
------------
• Queries the UCDP REST API (not static JSON dumps)
• Filters by date range — only fetches events from last N days
• Maps UCDP type_of_violence to ARES EventCategory
• SHA-256 dedup by UCDP id
• Circuit breaker
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..database import insert_event
from ..intelligence.confidence import initial_bba
from ..models.event import ConflictIntel, EventCategory, LocationEntity
from ..utils.circuit_breaker import CircuitBreaker
from ..websocket_manager import manager

logger = logging.getLogger("ucdp_fetcher")

_cb = CircuitBreaker("ucdp", failure_threshold=3, recovery_timeout=600, cache_ttl=3600)
_SEEN: dict[str, float] = {}
_DEDUP_TTL_S = 172_800  # 48 hours

# UCDP type_of_violence → ARES category
# 1 = state-based, 2 = non-state, 3 = one-sided (civilian)
_VIOLENCE_TYPE_MAP: dict[int, EventCategory] = {
    1: EventCategory.ground_strike,
    2: EventCategory.ground_strike,
    3: EventCategory.casualty_report,
}


def _entry_hash(uid: str) -> str:
    return hashlib.sha256(str(uid).encode()).hexdigest()


def _prune_seen():
    cutoff = time.monotonic() - _DEDUP_TTL_S
    for k in [k for k, v in _SEEN.items() if v < cutoff]:
        del _SEEN[k]


async def _fetch_ucdp(client: httpx.AsyncClient) -> Optional[list[dict]]:
    """Fetch recent UCDP GED events via REST API."""
    # Fetch events from last UCDP_LOOKBACK_DAYS days
    since = (datetime.now(timezone.utc) - timedelta(days=settings.UCDP_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    params = {
        "StartDate": since,
        "pagesize":  settings.UCDP_MAX_RECORDS,
        "page":      1,
    }
    url = f"{settings.UCDP_BASE_URL}?{urlencode(params)}"

    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("Result", [])
    except Exception as exc:
        logger.warning(f"[CHARLIE-B] UCDP fetch failed: {exc}")
        raise


_fetch_ucdp_safe = _cb.call(_fetch_ucdp)


async def _process_event(ev: dict) -> Optional[dict]:
    uid = str(ev.get("id", ""))
    h = _entry_hash(uid)
    if h in _SEEN:
        return None
    _SEEN[h] = time.monotonic()

    lat = ev.get("latitude")
    lon = ev.get("longitude")
    try:
        lat = float(lat) if lat else None
        lon = float(lon) if lon else None
    except (TypeError, ValueError):
        lat = lon = None

    vtype    = ev.get("type_of_violence", 1)
    category = _VIOLENCE_TYPE_MAP.get(vtype, EventCategory.unknown)

    country       = ev.get("country", "")
    location_name = ev.get("adm_1", ev.get("adm_2", country))
    deaths        = int(ev.get("deaths_civilians", 0) or 0) + int(ev.get("deaths_a", 0) or 0) + int(ev.get("deaths_b", 0) or 0)
    side_a        = ev.get("side_a", "")
    side_b        = ev.get("side_b", "")
    actors        = [a for a in [side_a, side_b] if a]

    notes = ev.get("source_article", "") or f"{ev.get('conflict_name', '')} — {location_name}, {country}"

    intel = ConflictIntel(
        raw_text        = notes[:500],
        translation     = notes[:500],
        category        = category,
        confidence      = 0.80,
        source_language = "en",
        is_confirmed    = deaths > 0,
        casualty_count  = deaths or None,
        unit_mentions   = actors,
    )

    if lat is not None and lon is not None:
        intel.locations.append(LocationEntity(
            raw_text   = location_name,
            normalized = f"{location_name}, {country}",
            lat        = lat,
            lon        = lon,
            confidence = 0.90,
        ))

    alpha = settings.UCDP_RELIABILITY_ALPHA
    bba   = initial_bba(intel, alpha)
    intel.bel          = bba["belief"]
    intel.pl           = bba["plausibility"]
    intel.conflict_k   = bba["conflict_k"]
    intel.source_alpha = alpha

    try:
        eid = await insert_event(intel, source="ucdp")
    except Exception as exc:
        logger.error(f"[CHARLIE-B] DB insert failed for {uid}: {exc}")
        return None

    payload = intel.model_dump()
    payload.update({
        "id":            eid,
        "source":        "ucdp",
        "ucdp_id":       uid,
        "ucdp_date":     ev.get("date_start"),
        "lat":           intel.lat,
        "lon":           intel.lon,
        "location_name": intel.location_name,
        "category":      intel.category.value,
        "fusion_status": intel.fusion_status,
        "country":       country,
        "deaths":        deaths,
        "actors":        actors,
    })

    await manager.broadcast_json(payload)
    logger.info(f"[CHARLIE-B] [{category.value.upper()}] {location_name}, {country} deaths={deaths}")
    return payload


async def poll_ucdp():
    """Main coroutine for Agent CHARLIE-B. Runs on UCDP_POLL_INTERVAL."""
    if not settings.ENABLE_UCDP:
        logger.info("[CHARLIE-B] Agent disabled via ENABLE_UCDP")
        while True:
            await asyncio.sleep(3600)

    interval = settings.UCDP_POLL_INTERVAL
    logger.info(f"[CHARLIE-B] UCDP fetcher starting — poll interval {interval}s, lookback {settings.UCDP_LOOKBACK_DAYS}d")

    while True:
        cycle_start = time.monotonic()
        _prune_seen()

        async with httpx.AsyncClient(headers={"User-Agent": "ARES-OSINT/1.0"}) as client:
            events = await _fetch_ucdp_safe(client)

        ingested = 0
        if events:
            for ev in events:
                try:
                    r = await _process_event(ev)
                    if r:
                        ingested += 1
                except Exception as exc:
                    logger.error(f"[CHARLIE-B] Unhandled error: {exc}", exc_info=True)

        elapsed = time.monotonic() - cycle_start
        logger.info(
            f"[CHARLIE-B] Cycle: {len(events or [])} events, "
            f"{ingested} new in {elapsed:.1f}s. CB={_cb.state.value}"
        )
        await asyncio.sleep(max(0.0, interval - elapsed))
