"""
Agent BRAVO-F: RSS tactical news harvester.
Replaces alpha_harvester (Telegram) as the open-source text intelligence feed.

On first startup it performs a 6-hour historical backfill — any entry whose
published timestamp falls within the last 6 hours is eligible.  Subsequent
cycles only process articles newer than the last poll timestamp, preventing
re-ingestion.

For each matched article the agent also extracts the full summary/description
text and stores it in the `translation` column so the frontend can display a
human-readable explanation of the event alongside the headline.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from ..database import get_pool
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("bravo_news")

# ── Feed sources ──────────────────────────────────────────────────────────────
RSS_FEEDS: list[str] = [
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.jpost.com/rss/rssfeeds.aspx?catid=1",
    "https://www.middleeasteye.net/rss",
]

# ── Tactical keyword filter (case-insensitive) ────────────────────────────────
TACTICAL_KEYWORDS: set[str] = {
    "strike", "explosion", "airstrike", "missile",
    "drone", "intercept", "beirut", "tehran", "idf", "hezbollah",
}

# ── City → (lon, lat) mapping  (PostGIS uses lon first in ST_Point) ───────────
CITY_COORDS: dict[str, tuple[float, float]] = {
    "beirut":    (35.5018, 33.8938),
    "tehran":    (51.3890, 35.6892),
    "tel aviv":  (34.7818, 32.0853),
    "damascus":  (36.2913, 33.5138),
}
DEFAULT_COORDS: tuple[float, float] = (36.2765, 33.5102)   # Levant regional centre

POLL_INTERVAL_S: int = 300        # 5 minutes between cycles
BACKFILL_HOURS:  int = 6          # on startup, look back this many hours
NEWS_CONFIDENCE: float = 0.7

# In-process deduplication: stores article URLs already inserted this session.
_seen_urls: set[str] = set()

# Tracks the timestamp of the most-recently processed article so subsequent
# cycles only look at genuinely new entries.
_last_poll_time: datetime | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_tactical(text: str) -> bool:
    """Return True if any tactical keyword appears in the lowercased text."""
    lower = text.lower()
    return any(kw in lower for kw in TACTICAL_KEYWORDS)


def _resolve_location(text: str) -> tuple[str, float, float]:
    """
    Scan text for a known city name and return (city_label, lon, lat).
    Falls back to a Levant regional centre when nothing matches.
    """
    lower = text.lower()
    for city, (lon, lat) in CITY_COORDS.items():
        if city in lower:
            return city.title(), lon, lat
    return "Middle East (regional)", DEFAULT_COORDS[0], DEFAULT_COORDS[1]


def _parse_entry_time(entry) -> datetime | None:
    """
    Try to extract a timezone-aware published datetime from a feedparser entry.
    feedparser populates `published_parsed` (struct_time, UTC) when it can parse
    the date; fall back to the raw `published` string via email.utils otherwise.
    Returns None if no date is available.
    """
    if entry.get("published_parsed"):
        try:
            import calendar
            ts = calendar.timegm(entry.published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    raw = entry.get("published", "") or entry.get("updated", "")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass

    return None


def _clean_html(raw: str) -> str:
    """Strip HTML tags and collapse whitespace from a summary string."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_description(entry) -> str:
    """
    Pull the best available description / body text from a feedparser entry.
    Priority: content[0].value > summary > "" (empty string if nothing found).
    HTML is stripped so only plain text reaches the database.
    """
    # `content` is a list of content objects (Atom feeds)
    content_list = entry.get("content", [])
    if content_list:
        raw = content_list[0].get("value", "")
        if raw:
            return _clean_html(raw)

    summary = entry.get("summary", "") or entry.get("description", "")
    if summary:
        return _clean_html(summary)

    return ""


async def _insert_news_event(
    pool,
    title: str,
    description: str,
    url: str,
    location_name: str,
    lon: float,
    lat: float,
    published_at: datetime | None,
) -> int | None:
    """
    Write a single news event into the PostGIS events table.
    - raw_text    → article headline
    - translation → article body/summary (the "explanation" of the event)
    - created_at  → article's own published timestamp (or now() as fallback)
    Returns the new row id, or None on failure.
    """
    sql = """
        INSERT INTO events (
            category,
            location,
            location_name,
            confidence,
            sources,
            raw_text,
            translation,
            created_at
        ) VALUES (
            'kinetic',
            ST_SetSRID(ST_Point($1, $2), 4326),
            $3,
            $4,
            $5,
            $6,
            $7,
            $8
        )
        RETURNING id
    """
    created = published_at or datetime.now(timezone.utc)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                lon,
                lat,
                location_name,
                NEWS_CONFIDENCE,
                [url],
                title,
                description or None,   # NULL if empty — cleaner than empty string
                created,
            )
            return row["id"] if row else None
    except Exception as exc:
        logger.error(f"[BRAVO-F] DB insert failed: {exc}")
        return None


def _should_process(entry_time: datetime | None, cutoff: datetime) -> bool:
    """
    Return True if the entry is new enough to process.
    Entries with no timestamp are always processed (we can't tell their age).
    """
    if entry_time is None:
        return True
    return entry_time >= cutoff


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_news_harvester() -> None:
    """
    Infinite asyncio loop: poll RSS feeds every 5 minutes.

    First cycle:  backfill the last 6 hours (cutoff = now − 6h).
    Subsequent:   only process entries newer than the previous cycle start.
    """
    global _last_poll_time
    logger.info("[BRAVO-F] RSS news harvester starting up — backfilling last 6 hours")

    while True:
        now     = datetime.now(timezone.utc)
        # On first run use the 6-hour backfill window; after that use the
        # timestamp of the previous cycle so nothing is missed or double-counted.
        cutoff  = _last_poll_time if _last_poll_time else (now - timedelta(hours=BACKFILL_HOURS))
        pool    = await get_pool()
        inserted_count = 0

        for feed_url in RSS_FEEDS:
            try:
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

                if feed.bozo and not feed.entries:
                    logger.warning(
                        f"[BRAVO-F] Feed parse error for {feed_url}: {feed.bozo_exception}"
                    )
                    continue

                for entry in feed.entries:
                    title: str = entry.get("title", "").strip()
                    url: str   = entry.get("link", "").strip()

                    if not title or not url:
                        continue

                    # ── Time filter ───────────────────────────────────────────
                    entry_time = _parse_entry_time(entry)
                    if not _should_process(entry_time, cutoff):
                        continue

                    # ── Deduplication ─────────────────────────────────────────
                    if url in _seen_urls:
                        continue

                    # ── Keyword filter (title + description) ──────────────────
                    description = _extract_description(entry)
                    combined    = f"{title} {description}"
                    if not _is_tactical(combined):
                        continue

                    _seen_urls.add(url)

                    location_name, lon, lat = _resolve_location(combined)
                    event_id = await _insert_news_event(
                        pool, title, description, url,
                        location_name, lon, lat, entry_time
                    )

                    if event_id is not None:
                        inserted_count += 1
                        logger.info(
                            f"[BRAVO-F] Inserted event {event_id}: "
                            f'"{title[:80]}" → {location_name}'
                        )
                        await manager.broadcast_json({
                            "type":          "news_event",
                            "event_id":      event_id,
                            "category":      "kinetic",
                            "raw_text":      title,
                            "description":   description,
                            "location_name": location_name,
                            "lat":           lat,
                            "lon":           lon,
                            "confidence":    NEWS_CONFIDENCE,
                            "sources":       [url],
                            "published_at":  entry_time.isoformat() if entry_time else None,
                        })

            except Exception as exc:
                logger.error(f"[BRAVO-F] Error processing feed {feed_url}: {exc}")

        _last_poll_time = now
        logger.info(
            f"[BRAVO-F] Cycle complete — {inserted_count} new tactical events inserted "
            f"(cutoff: {cutoff.strftime('%H:%M UTC')})"
        )
        await asyncio.sleep(POLL_INTERVAL_S)
