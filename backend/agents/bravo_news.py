"""
Agent BRAVO-N — RSS News Harvester
====================================
Polls a configurable list of tactical RSS feeds (Al Jazeera, Jerusalem Post,
Middle East Eye, etc.) on a fixed interval, processes each entry through the
full LLM pipeline, and broadcasts structured ConflictIntel events.

Key features
------------
• SHA-256 content hash deduplication — same story polled twice never creates
  a duplicate pin or DB row.
• Geo-tag extraction — reads <geo:lat>/<geo:long> or <georss:point> if present;
  falls back to Ollama-extracted location names → local military DB → Nominatim.
• Per-feed source labelling: source field is "rss:<feed_hostname>".
• High-confidence promotion: if an RSS event's confidence >= 0.75 AND the
  geocoder returns a local-DB match (military base), set is_confirmed=True so
  the frontend can apply the high-confidence pulse animation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..database import insert_event
from ..intelligence.geocoder import resolve_location, lookup_local
from ..intelligence.llm_pipeline import process_rss_entry
from ..intelligence.confidence import initial_bba
from ..models.event import ConflictIntel, LocationEntity
from ..websocket_manager import manager

logger = logging.getLogger("bravo_news")

# ── Feed list loader ──────────────────────────────────────────────────

_RSS_FEEDS_JSON = Path(__file__).parent.parent / "data" / "rss_feeds.json"


def _load_feeds() -> tuple[list[str], dict[str, float]]:
    """
    Load feed URLs and per-source reliability weights from rss_feeds.json.
    Falls back to settings.RSS_FEEDS (3 hardcoded URLs) if the file is missing.
    Returns (feed_url_list, {source_label: reliability_alpha}).
    """
    if _RSS_FEEDS_JSON.exists():
        try:
            data = json.loads(_RSS_FEEDS_JSON.read_text())
            feeds_data = data.get("feeds", [])
            urls   = [f["url"] for f in feeds_data if f.get("url")]
            alphas = {}
            for f in feeds_data:
                url = f.get("url", "")
                rel = float(f.get("reliability", 0.65))
                try:
                    host = urlparse(url).hostname or url
                    if host.startswith("www."):
                        host = host[4:]
                    alphas[f"rss:{host}"] = rel
                except Exception:
                    pass
            logger.info(f"[BRAVO-N] Loaded {len(urls)} feeds from rss_feeds.json")
            return urls, alphas
        except Exception as exc:
            logger.warning(f"[BRAVO-N] Failed to load rss_feeds.json: {exc} — using config fallback")

    # Fallback to settings.RSS_FEEDS
    logger.info(f"[BRAVO-N] Using {len(settings.RSS_FEEDS)} feeds from config")
    return settings.RSS_FEEDS, {}

# ── XML namespaces used by geo-enabled RSS feeds ──────────────────────
_NS = {
    "geo":     "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "georss":  "http://www.georss.org/georss",
    "media":   "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
}

# ── In-process deduplication store ───────────────────────────────────
# Maps SHA-256(url + title) → unix timestamp of first ingestion.
# Cleared of entries older than 48 h on each poll cycle.
_SEEN: dict[str, float] = {}
_DEDUP_TTL_S: int = 172_800  # 48 hours


def _entry_hash(url: str, title: str) -> str:
    """Stable SHA-256 fingerprint for an RSS entry."""
    raw = f"{url.strip()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _prune_seen():
    """Remove stale entries from the in-process dedup store."""
    cutoff = time.monotonic() - _DEDUP_TTL_S
    stale = [k for k, v in _SEEN.items() if v < cutoff]
    for k in stale:
        del _SEEN[k]


# ── RSS parsing ───────────────────────────────────────────────────────

def _extract_geo(item: ET.Element) -> tuple[Optional[float], Optional[float]]:
    """
    Try to extract explicit geo-coordinates from an RSS <item>.
    Supports:
      • <geo:lat> / <geo:long>
      • <georss:point>  (space-separated "lat lon")
    Returns (lat, lon) or (None, None).
    """
    lat_el = item.find("geo:lat", _NS)
    lon_el = item.find("geo:long", _NS)
    if lat_el is not None and lon_el is not None:
        try:
            return float(lat_el.text), float(lon_el.text)
        except (TypeError, ValueError):
            pass

    point_el = item.find("georss:point", _NS)
    if point_el is not None and point_el.text:
        parts = point_el.text.strip().split()
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass

    return None, None


def _parse_feed(xml_bytes: bytes, feed_url: str) -> list[dict]:
    """
    Parse an RSS 2.0 or Atom feed and return a list of normalised entry dicts:
        {url, title, summary, geo_lat, geo_lon}
    Silently skips malformed entries.
    """
    import re
    entries: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning(f"[BRAVO-N] XML parse error for {feed_url}: {exc}")
        return entries

    # RSS 2.0
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []

    # Atom
    atom_ns = "http://www.w3.org/2005/Atom"
    if not items:
        items = root.findall(f"{{{atom_ns}}}entry")

    for item in items:
        # Use explicit is-not-None checks — ET.Element has deprecated truth-value testing
        title_el = item.find("title")
        if title_el is None:
            title_el = item.find(f"{{{atom_ns}}}title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        link_el = item.find("link")
        if link_el is None:
            link_el = item.find(f"{{{atom_ns}}}link")
        if link_el is not None:
            url = link_el.text or link_el.get("href", "")
        else:
            guid_el = item.find("guid")
            url = guid_el.text if guid_el is not None else ""
        url = (url or "").strip()

        desc_el = item.find("description")
        if desc_el is None:
            desc_el = item.find(f"{{{atom_ns}}}summary")
        if desc_el is None:
            desc_el = item.find(f"{{{atom_ns}}}content")
        if desc_el is None:
            desc_el = item.find("content:encoded", _NS)
        summary = (desc_el.text or "").strip() if desc_el is not None else ""
        if "<" in summary:
            summary = re.sub(r"<[^>]+>", " ", summary).strip()
            summary = re.sub(r"\s{2,}", " ", summary)

        if not title and not summary:
            continue

        geo_lat, geo_lon = _extract_geo(item)

        entries.append({
            "url":     url,
            "title":   title,
            "summary": summary[:1000],
            "geo_lat": geo_lat,
            "geo_lon": geo_lon,
        })

    return entries


# ── Feed fetch ────────────────────────────────────────────────────────

async def _fetch_feed(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    """Fetch a single RSS feed URL. Returns raw bytes or None on error."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.warning(f"[BRAVO-N] Failed to fetch {url}: {exc}")
        return None


# ── Source label helper ───────────────────────────────────────────────

def _source_label(feed_url: str) -> str:
    """Derive a short source label from the feed URL hostname."""
    try:
        host = urlparse(feed_url).hostname or feed_url
        if host.startswith("www."):
            host = host[4:]
        return f"rss:{host}"
    except Exception:
        return "rss:unknown"


# ── Per-entry processing ──────────────────────────────────────────────

async def _process_entry(entry: dict, feed_url: str, alpha_weights: dict[str, float] | None = None) -> Optional[dict]:
    """
    Full pipeline for a single RSS entry:
      1. Dedup check (hash)
      2. LLM pipeline (translation, NER, categorisation)
      3. Geocoding (geo-tag → local DB → Nominatim)
      4. DST confidence initialisation
      5. DB insert + WebSocket broadcast
    Returns the broadcast payload dict, or None if skipped.
    """
    title   = entry["title"]
    summary = entry["summary"]
    url     = entry["url"]

    # 1. Deduplication
    h = _entry_hash(url, title)
    if h in _SEEN:
        logger.debug(f"[BRAVO-N] Duplicate skipped: {title[:60]}")
        return None
    _SEEN[h] = time.monotonic()

    # 2. LLM pipeline
    raw_text = f"{title}. {summary}" if summary else title
    intel: ConflictIntel = await process_rss_entry(raw_text, feed_url)

    if intel.category.value == "unknown" and intel.confidence < 0.3:
        logger.debug(f"[BRAVO-N] Low-confidence unknown dropped: {title[:60]}")
        _SEEN.pop(h, None)
        return None

    # 3. Geocoding
    geo_lat: Optional[float] = entry.get("geo_lat")
    geo_lon: Optional[float] = entry.get("geo_lon")
    used_local_db = False

    if geo_lat is not None and geo_lon is not None:
        if not intel.locations:
            intel.locations.append(LocationEntity(
                raw_text=title[:80],
                lat=geo_lat,
                lon=geo_lon,
                confidence=0.9,
            ))
        else:
            intel.locations[0].lat = geo_lat
            intel.locations[0].lon = geo_lon
            intel.locations[0].confidence = 0.9
    else:
        for loc in intel.locations:
            if loc.lat is not None:
                continue
            coords = await resolve_location(loc.raw_text, loc.normalized)
            if coords:
                loc.lat, loc.lon = coords
                local_hit = lookup_local(loc.normalized or loc.raw_text)
                if local_hit:
                    loc.confidence = local_hit[3]
                    used_local_db = True

    # 4. High-confidence promotion
    if used_local_db and intel.confidence >= 0.75:
        intel.is_confirmed = True

    # 5. DST initialisation — use per-feed reliability from JSON, fallback 0.65
    source_label  = _source_label(feed_url)
    _fallback_alphas = {
        "rss:aljazeera.com":     0.72,
        "rss:jpost.com":         0.70,
        "rss:middleeasteye.net": 0.65,
    }
    _weights = alpha_weights or _fallback_alphas
    alpha = _weights.get(source_label, _fallback_alphas.get(source_label, 0.65))
    bba_result = initial_bba(intel, alpha)
    intel.bel          = bba_result["belief"]
    intel.pl           = bba_result["plausibility"]
    intel.conflict_k   = bba_result["conflict_k"]
    intel.source_alpha = alpha

    # 6. DB insert
    try:
        event_id = await insert_event(intel, source=source_label)
    except Exception as exc:
        logger.error(f"[BRAVO-N] DB insert failed for '{title[:60]}': {exc}")
        return None

    # 7. Broadcast
    payload = intel.model_dump()
    payload.update({
        "id":              event_id,
        "source":          source_label,
        "rss_url":         url,
        "lat":             intel.lat,
        "lon":             intel.lon,
        "location_name":   intel.location_name,
        "category":        intel.category.value,
        "fusion_status":   intel.fusion_status,
        "high_confidence": intel.is_confirmed and intel.confidence >= 0.75,
    })

    await manager.broadcast_json(payload)
    logger.info(
        f"[BRAVO-N] [{source_label}] {intel.category.value.upper()} "
        f"conf={intel.confidence:.2f} loc={intel.location_name!r} — {title[:70]}"
    )
    return payload


# ── Main poll loop ────────────────────────────────────────────────────

async def poll_rss():
    """
    Main coroutine for Agent BRAVO-N.
    Runs forever, polling all configured RSS feeds every RSS_POLL_INTERVAL seconds.
    Feed list and per-source reliability weights are loaded from
    backend/data/rss_feeds.json (170+ sources) with a fallback to settings.RSS_FEEDS.
    """
    # Load feeds from rss_feeds.json (or config fallback)
    feeds, alpha_weights = _load_feeds()
    interval = settings.RSS_POLL_INTERVAL

    if not feeds:
        logger.warning("[BRAVO-N] No RSS feeds configured — agent idle")
        while True:
            await asyncio.sleep(3600)

    logger.info(
        f"[BRAVO-N] RSS harvester starting — {len(feeds)} feed(s), "
        f"poll interval {interval}s"
    )

    headers = {
        "User-Agent": "ARES-OSINT-Dashboard/1.0 RSS-Harvester",
        "Accept":     "application/rss+xml, application/xml, text/xml, */*",
    }

    while True:
        cycle_start = time.monotonic()
        _prune_seen()

        async with httpx.AsyncClient(headers=headers) as client:
            raw_feeds = await asyncio.gather(
                *[_fetch_feed(client, url) for url in feeds],
                return_exceptions=False,
            )

        total_entries  = 0
        total_ingested = 0

        for feed_url, xml_bytes in zip(feeds, raw_feeds):
            if xml_bytes is None:
                continue

            entries = _parse_feed(xml_bytes, feed_url)
            total_entries += len(entries)

            for entry in entries:
                try:
                    result = await _process_entry(entry, feed_url, alpha_weights=alpha_weights)
                    if result:
                        total_ingested += 1
                except Exception as exc:
                    logger.error(
                        f"[BRAVO-N] Unhandled error processing entry "
                        f"from {feed_url}: {exc}",
                        exc_info=True,
                    )

        elapsed = time.monotonic() - cycle_start
        logger.info(
            f"[BRAVO-N] Cycle complete — {total_entries} entries fetched, "
            f"{total_ingested} new events ingested in {elapsed:.1f}s. "
            f"Next poll in {max(0, interval - elapsed):.0f}s"
        )

        sleep_for = max(0.0, interval - elapsed)
        await asyncio.sleep(sleep_for)
