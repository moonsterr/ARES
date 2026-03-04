"""
Agent CHARLIE-A — ACLED Conflict Event Fetcher
===============================================
Fetches armed conflict events from the Armed Conflict Location & Event Data
Project (ACLED) API and converts them to ConflictIntel events.

ACLED provides real-time conflict data with lat/lon, actors, fatalities,
and event types for 170+ countries — high-value for ground truth.

Registration: https://acleddata.com/register/ (free, instant)

Key features
------------
• Filters to Middle East + North Africa + Ukraine theatre by ISO codes
• Maps ACLED event types to ARES EventCategory
• Uses DST with α=0.80 (ACLED is cross-referenced and reliable)
• SHA-256 deduplication by ACLED event_id_cnty
• Circuit breaker wraps every API call
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Optional
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..database import insert_event
from ..intelligence.confidence import initial_bba
from ..models.event import ConflictIntel, EventCategory, LocationEntity
from ..utils.circuit_breaker import CircuitBreaker
from ..websocket_manager import manager

logger = logging.getLogger("acled_fetcher")

# ── Circuit breaker ───────────────────────────────────────────────────
_cb = CircuitBreaker("acled", failure_threshold=3, recovery_timeout=300, cache_ttl=1800)

# ── Deduplication ─────────────────────────────────────────────────────
_SEEN: dict[str, float] = {}
_DEDUP_TTL_S = 86_400  # 24 hours

# ── Middle East + North Africa + Ukraine ISO3 codes ───────────────────
ACLED_ISO_COUNTRIES = (
    "ISR,PSE,LBN,SYR,IRQ,IRN,YEM,SAU,ARE,KWT,BHR,QAT,OMN,JOR,"
    "EGY,LBY,TUN,DZA,MAR,SDN,ETH,SOM,DJI,ERI,"
    "TUR,ARM,AZE,GEO,UKR,RUS"
)

# ── ACLED → ARES category mapping ────────────────────────────────────
_CATEGORY_MAP: dict[str, EventCategory] = {
    "Battles":                           EventCategory.ground_strike,
    "Explosions/Remote violence":        EventCategory.explosion,
    "Violence against civilians":        EventCategory.casualty_report,
    "Protests":                          EventCategory.troop_movement,
    "Riots":                             EventCategory.troop_movement,
    "Strategic developments":            EventCategory.troop_movement,
    "Air/drone strike":                  EventCategory.air_alert,
    "Shelling/artillery/missile attack": EventCategory.explosion,
    "Armed clash":                       EventCategory.ground_strike,
    "Attack":                            EventCategory.ground_strike,
    "Government regains territory":      EventCategory.troop_movement,
    "Non-state actor overtakes territory": EventCategory.troop_movement,
}


def _map_category(event_type: str, sub_event_type: str) -> EventCategory:
    return (
        _CATEGORY_MAP.get(sub_event_type)
        or _CATEGORY_MAP.get(event_type)
        or EventCategory.unknown
    )


def _entry_hash(event_id: str) -> str:
    return hashlib.sha256(str(event_id).encode()).hexdigest()


def _prune_seen():
    cutoff = time.monotonic() - _DEDUP_TTL_S
    for k in [k for k, v in _SEEN.items() if v < cutoff]:
        del _SEEN[k]


async def _fetch_acled(client: httpx.AsyncClient) -> Optional[list[dict]]:
    """Fetch recent ACLED events via REST API."""
    if not settings.ACLED_API_KEY:
        logger.warning("[CHARLIE-A] ACLED_API_KEY not set — agent idle")
        return None

    params = {
        "key":          settings.ACLED_API_KEY,
        "email":        settings.ACLED_EMAIL,
        "iso":          ACLED_ISO_COUNTRIES,
        "limit":        settings.ACLED_MAX_RECORDS,
        "fields":       "event_id_cnty|event_date|event_type|sub_event_type|country|location|latitude|longitude|fatalities|actor1|actor2|notes|source",
        "format":       "json",
        "timestamp":    "1",
    }
    url = f"{settings.ACLED_BASE_URL}?{urlencode(params)}"

    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 200 and "data" in data:
            return data["data"]
        else:
            logger.warning(f"[CHARLIE-A] Unexpected ACLED response: {data.get('status')}")
            return []
    except Exception as exc:
        logger.warning(f"[CHARLIE-A] ACLED fetch failed: {exc}")
        raise


_fetch_acled_safe = _cb.call(_fetch_acled)


async def _process_event(ev: dict) -> Optional[dict]:
    """Convert a single ACLED event dict to ConflictIntel and store it."""
    event_id = ev.get("event_id_cnty", "")
    h = _entry_hash(event_id)
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

    category = _map_category(
        ev.get("event_type", ""),
        ev.get("sub_event_type", ""),
    )

    actors = [a for a in [ev.get("actor1"), ev.get("actor2")] if a]
    notes  = ev.get("notes", "")
    location_name = ev.get("location", "")
    country = ev.get("country", "")

    intel = ConflictIntel(
        raw_text        = notes or f"{ev.get('event_type')} in {location_name}, {country}",
        translation     = notes or "",
        category        = category,
        confidence      = 0.85,  # ACLED is cross-referenced
        source_language = "en",
        is_confirmed    = bool(ev.get("fatalities", 0)),
        casualty_count  = int(ev.get("fatalities", 0)) or None,
        unit_mentions   = actors,
    )

    if lat is not None and lon is not None:
        intel.locations.append(LocationEntity(
            raw_text   = location_name,
            normalized = f"{location_name}, {country}",
            lat        = lat,
            lon        = lon,
            confidence = 0.95,
        ))

    # DST — ACLED is a curated, cross-referenced source
    alpha = settings.ACLED_RELIABILITY_ALPHA
    bba   = initial_bba(intel, alpha)
    intel.bel          = bba["belief"]
    intel.pl           = bba["plausibility"]
    intel.conflict_k   = bba["conflict_k"]
    intel.source_alpha = alpha

    try:
        eid = await insert_event(intel, source="acled")
    except Exception as exc:
        logger.error(f"[CHARLIE-A] DB insert failed for {event_id}: {exc}")
        return None

    payload = intel.model_dump()
    payload.update({
        "id":            eid,
        "source":        "acled",
        "acled_id":      event_id,
        "acled_date":    ev.get("event_date"),
        "lat":           intel.lat,
        "lon":           intel.lon,
        "location_name": intel.location_name,
        "category":      intel.category.value,
        "fusion_status": intel.fusion_status,
        "country":       country,
        "fatalities":    int(ev.get("fatalities", 0)),
        "actors":        actors,
    })

    await manager.broadcast_json(payload)
    logger.info(
        f"[CHARLIE-A] [{category.value.upper()}] {location_name}, {country} "
        f"— fatalities={ev.get('fatalities', 0)}"
    )
    return payload


async def poll_acled():
    """Main coroutine for Agent CHARLIE-A. Polls ACLED every ACLED_POLL_INTERVAL seconds."""
    if not settings.ENABLE_ACLED:
        logger.info("[CHARLIE-A] Agent disabled via ENABLE_ACLED")
        while True:
            await asyncio.sleep(3600)

    if not settings.ACLED_API_KEY:
        logger.warning("[CHARLIE-A] ACLED_API_KEY not configured — agent idle")
        while True:
            await asyncio.sleep(3600)

    interval = settings.ACLED_POLL_INTERVAL
    logger.info(f"[CHARLIE-A] ACLED fetcher starting — poll interval {interval}s")

    while True:
        cycle_start = time.monotonic()
        _prune_seen()

        async with httpx.AsyncClient(headers={"User-Agent": "ARES-OSINT/1.0"}) as client:
            events = await _fetch_acled_safe(client)

        ingested = 0
        if events:
            for ev in events:
                try:
                    r = await _process_event(ev)
                    if r:
                        ingested += 1
                except Exception as exc:
                    logger.error(f"[CHARLIE-A] Unhandled error: {exc}", exc_info=True)

        elapsed = time.monotonic() - cycle_start
        logger.info(
            f"[CHARLIE-A] Cycle: {len(events or [])} events fetched, "
            f"{ingested} new in {elapsed:.1f}s. CB={_cb.state.value}"
        )
        await asyncio.sleep(max(0.0, interval - elapsed))
