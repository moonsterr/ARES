"""
Agent BRAVO-G — GDELT News Geo-Event Extractor
================================================
Polls the GDELT v2 Doc API for conflict-related articles, uses LLM to extract
geographic locations from headlines, and creates structured events.

Key features
------------
• Query-based filtering — configurable search query for conflict keywords
• LLM geo-extraction — uses Ollama to extract lat/lon from article context
• Deduplication — same URL never creates duplicate events within 24h
• Source labelling — source field is "gdelt"
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
from ..intelligence.geocoder import resolve_location, lookup_local
from ..intelligence.llm_pipeline import process_gdelt_entry
from ..intelligence.confidence import initial_bba
from ..models.event import ConflictIntel, LocationEntity
from ..websocket_manager import manager

logger = logging.getLogger("bravo_gdelt")

_SEEN: dict[str, float] = {}
_DEDUP_TTL_S: int = 86_400  # 24 hours


def _entry_hash(url: str) -> str:
    """Stable SHA-256 fingerprint for a GDELT entry."""
    raw = url.strip().lower()
    return hashlib.sha256(raw.encode()).hexdigest()


def _prune_seen():
    """Remove stale entries from the in-process dedup store."""
    cutoff = time.monotonic() - _DEDUP_TTL_S
    stale = [k for k, v in _SEEN.items() if v < cutoff]
    for k in stale:
        del _SEEN[k]


async def _fetch_gdelt(client: httpx.AsyncClient) -> Optional[list[dict]]:
    """Fetch articles from GDELT v2 Doc API."""
    params = {
        "query": settings.GDELT_QUERY,
        "mode": settings.GDELT_MODE,
        "maxrecords": settings.GDELT_MAX_RECORDS,
        "format": "json",
        "sort": "DateDesc",
    }
    url = f"{settings.GDELT_BASE_URL}?{urlencode(params)}"
    
    try:
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        
        if isinstance(data, dict) and "articles" in data:
            return data["articles"]
        elif isinstance(data, list):
            return data
        else:
            logger.warning("[BRAVO-G] Unexpected GDELT response format")
            return []
            
    except Exception as exc:
        logger.warning(f"[BRAVO-G] Failed to fetch GDELT: {exc}")
        return None


async def _process_article(article: dict) -> Optional[dict]:
    """
    Process a single GDELT article:
      1. Dedup check
      2. LLM pipeline (extract entities + category)
      3. LLM geo-extraction
      4. Geocoding
      5. DST confidence
      6. DB insert + broadcast
    """
    url = article.get("url", "")
    title = article.get("title", "")
    seendate = article.get("seendate", "")
    
    if not url or not title:
        return None

    # 1. Deduplication
    h = _entry_hash(url)
    if h in _SEEN:
        logger.debug(f"[BRAVO-G] Duplicate skipped: {title[:60]}")
        return None
    _SEEN[h] = time.monotonic()

    # 2. LLM pipeline
    raw_text = f"{title}. {article.get('seentext', '')}"
    intel: ConflictIntel = await process_gdelt_entry(raw_text, title)

    if intel.category.value == "unknown" and intel.confidence < 0.3:
        logger.debug(f"[BRAVO-G] Low-confidence unknown dropped: {title[:60]}")
        _SEEN.pop(h, None)
        return None

    # 3. Geo-extraction from article
    # If LLM didn't find coordinates, try to geocode the location
    if not intel.locations or all(loc.lat is None for loc in intel.locations):
        # Try to extract location from title directly
        if intel.locations and intel.locations[0].raw_text:
            coords = await resolve_location(intel.locations[0].raw_text, intel.locations[0].normalized)
            if coords:
                intel.locations[0].lat = coords[0]
                intel.locations[0].lon = coords[1]
                local_hit = lookup_local(intel.locations[0].normalized or intel.locations[0].raw_text)
                if local_hit:
                    intel.locations[0].confidence = local_hit[3]

    # 4. Use provided coordinates if available from GDELT
    if article.get("domain") and not intel.locations:
        # GDELT sometimes includes coordinates in social image
        pass  # LLM extraction is primary

    # 5. High-confidence promotion
    used_local_db = False
    for loc in intel.locations:
        if loc.lat is not None:
            local_hit = lookup_local(loc.normalized or loc.raw_text)
            if local_hit:
                loc.confidence = local_hit[3]
                used_local_db = True
                break

    if used_local_db and intel.confidence >= 0.75:
        intel.is_confirmed = True

    # 6. DST initialization
    alpha = 0.60  # GDELT is a news aggregator - moderate reliability
    bba_result = initial_bba(intel, alpha)
    intel.bel = bba_result["belief"]
    intel.pl = bba_result["plausibility"]
    intel.conflict_k = bba_result["conflict_k"]
    intel.source_alpha = alpha

    # 7. DB insert
    try:
        event_id = await insert_event(intel, source="gdelt")
    except Exception as exc:
        logger.error(f"[BRAVO-G] DB insert failed for '{title[:60]}': {exc}")
        return None

    # 8. Broadcast
    payload = intel.model_dump()
    payload.update({
        "id": event_id,
        "source": "gdelt",
        "gdelt_url": url,
        "gdelt_domain": article.get("domain", ""),
        "lat": intel.lat,
        "lon": intel.lon,
        "location_name": intel.location_name,
        "category": intel.category.value,
        "fusion_status": intel.fusion_status,
        "high_confidence": intel.is_confirmed and intel.confidence >= 0.75,
    })

    await manager.broadcast_json(payload)
    logger.info(
        f"[BRAVO-G] [{intel.category.value.upper()}] conf={intel.confidence:.2f} "
        f"loc={intel.location_name!r} — {title[:70]}"
    )
    return payload


async def poll_gdelt():
    """
    Main coroutine for Agent BRAVO-G.
    Runs forever, polling GDELT every GDELT_POLL_INTERVAL seconds.
    """
    if not settings.ENABLE_GDELT:
        logger.info("[BRAVO-G] Agent disabled via ENABLE_GDELT")
        while True:
            await asyncio.sleep(3600)

    interval = settings.GDELT_POLL_INTERVAL
    
    logger.info(
        f"[BRAVO-G] GDELT harvester starting — poll interval {interval}s, "
        f"query: {settings.GDELT_QUERY[:50]}..."
    )

    headers = {
        "User-Agent": "ARES-OSINT-Dashboard/1.0 GDELT-Harvester",
    }

    while True:
        cycle_start = time.monotonic()
        _prune_seen()

        async with httpx.AsyncClient(headers=headers) as client:
            articles = await _fetch_gdelt(client)

        total_articles = 0
        total_ingested = 0

        if articles:
            total_articles = len(articles)
            
            for article in articles:
                try:
                    result = await _process_article(article)
                    if result:
                        total_ingested += 1
                except Exception as exc:
                    logger.error(
                        f"[BRAVO-G] Unhandled error processing article: {exc}",
                        exc_info=True,
                    )

        elapsed = time.monotonic() - cycle_start
        logger.info(
            f"[BRAVO-G] Cycle complete — {total_articles} articles fetched, "
            f"{total_ingested} new events ingested in {elapsed:.1f}s. "
            f"Next poll in {max(0, interval - elapsed):.0f}s"
        )

        sleep_for = max(0.0, interval - elapsed)
        await asyncio.sleep(sleep_for)
