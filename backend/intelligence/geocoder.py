"""
Geocoder
========
Two-stage location resolution:
  1. Local fuzzy match against mideast_military_bases.json (~200 sites, <10ms)
  2. Fallback to OpenStreetMap Nominatim (async HTTP, rate-limited to 1 req/s)

Returns (lat, lon) tuples or None if resolution fails.
"""
from __future__ import annotations
import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger("geocoder")

# ── Load local military base database ────────────────────────────────
_DB_PATH = Path(__file__).parent.parent / "data" / "mideast_military_bases.json"
_DB: list[dict] = []
_INDEX: list[tuple[dict, str]] = []   # (site_dict, name_variant)
_LAST_NOMINATIM_CALL = 0.0            # unix timestamp — enforce 1 req/s


def _load_db():
    global _DB, _INDEX
    if _DB_PATH.exists():
        try:
            with open(_DB_PATH, encoding="utf-8") as f:
                _DB = json.load(f)
            _INDEX = [
                (site, name)
                for site in _DB
                for name in [site["canonical"]] + site.get("alt_names", [])
            ]
            logger.info(f"[Geocoder] Loaded {len(_DB)} military sites, {len(_INDEX)} name variants")
        except Exception as e:
            logger.warning(f"[Geocoder] Failed to load military base DB: {e}")
    else:
        logger.warning(f"[Geocoder] Military base DB not found at {_DB_PATH}")


_load_db()


def lookup_local(text_fragment: str, threshold: int = 78) -> Optional[tuple[float, float, str, float]]:
    """
    Fuzzy match a location text fragment against the local military base database.
    Returns (lat, lon, canonical_name, confidence_score) or None.

    Uses rapidfuzz for fast fuzzy matching. Falls back gracefully if not installed.
    """
    if not _INDEX or not text_fragment:
        return None

    try:
        from rapidfuzz import process, fuzz
        names = [pair[1] for pair in _INDEX]
        result = process.extractOne(
            text_fragment,
            names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if result:
            match_name, score, idx = result
            site = _INDEX[idx][0]
            return site["lat"], site["lon"], site["canonical"], score / 100.0
    except ImportError:
        # rapidfuzz not available — fall back to simple substring matching
        text_lower = text_fragment.lower()
        for site, name in _INDEX:
            if text_lower in name.lower() or name.lower() in text_lower:
                return site["lat"], site["lon"], site["canonical"], 0.75

    return None


async def lookup_nominatim(location_text: str) -> Optional[tuple[float, float, str]]:
    """
    Async Nominatim geocoding for location names not in the local database.
    Rate-limited to 1 request per second per Nominatim ToS.
    Searches globally — no bounding box restriction.
    Returns (lat, lon, display_name) or None.
    """
    global _LAST_NOMINATIM_CALL

    if not location_text:
        return None

    # Enforce 1 req/s rate limit
    elapsed = time.monotonic() - _LAST_NOMINATIM_CALL
    if elapsed < 1.0:
        await asyncio.sleep(1.0 - elapsed)

    # Global search — no viewbox/bounded so "Sri Lanka", "Russia", etc. all resolve
    params = {
        "q":               location_text,
        "format":          "json",
        "limit":           1,
        "accept-language": "en",
    }
    headers = {
        "User-Agent": "ARES-OSINT-Dashboard/1.0 (https://github.com/ares-dashboard)"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            _LAST_NOMINATIM_CALL = time.monotonic()
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                r = results[0]
                return float(r["lat"]), float(r["lon"]), r.get("display_name", location_text)
    except Exception as e:
        logger.warning(f"[Geocoder] Nominatim error for '{location_text}': {e}")

    return None


async def resolve_location(
    raw_text: str,
    normalized: Optional[str] = None,
) -> Optional[tuple[float, float]]:
    """
    Main geocoding entry point.
    First tries local fuzzy match; falls back to Nominatim.
    Returns (lat, lon) or None.
    """
    query = normalized or raw_text
    if not query:
        return None

    # Stage 1: local military base lookup (fast)
    local_result = lookup_local(query)
    if local_result:
        lat, lon, name, score = local_result
        logger.debug(f"[Geocoder] Local match: '{query}' → {name} ({score:.2f}) @ {lat},{lon}")
        return lat, lon

    # Stage 2: Nominatim fallback
    nominatim_result = await lookup_nominatim(query)
    if nominatim_result:
        lat, lon, display_name = nominatim_result
        logger.debug(f"[Geocoder] Nominatim: '{query}' → {display_name} @ {lat},{lon}")
        return lat, lon

    logger.debug(f"[Geocoder] Failed to resolve: '{query}'")
    return None


async def resolve_location_from_ollama_name(
    ollama_location_name: str,
    threshold: int = 70,
) -> Optional[tuple[float, float, str, float]]:
    """
    Resolve a location name extracted by Ollama NER when the RSS feed carries
    no explicit geo-tags.  Strategy:

      1. Try local military DB fuzzy match at a slightly relaxed threshold
         (default 70 vs normal 78) because Ollama may not return the exact
         canonical spelling (e.g. "T4 Airbase" vs "Tiyas Air Base / T-4").
      2. If local match found → return immediately with high confidence.
      3. If no local match → fall back to Nominatim (global search).

    Returns (lat, lon, canonical_name, confidence) or None.
    """
    if not ollama_location_name:
        return None

    from ..config import settings as _settings
    eff_threshold = min(threshold, _settings.GEOCODE_FUZZY_THRESHOLD)

    # Stage 1: local military base DB (fast, <10 ms)
    local_result = lookup_local(ollama_location_name, threshold=eff_threshold)
    if local_result:
        lat, lon, name, score = local_result
        logger.debug(
            f"[Geocoder] Ollama-name local hit: '{ollama_location_name}' "
            f"→ {name} (score={score:.2f}) @ {lat},{lon}"
        )
        return lat, lon, name, score

    # Stage 2: Nominatim fallback
    nominatim_result = await lookup_nominatim(ollama_location_name)
    if nominatim_result:
        lat, lon, display_name = nominatim_result
        logger.debug(
            f"[Geocoder] Ollama-name Nominatim: '{ollama_location_name}' "
            f"→ {display_name} @ {lat},{lon}"
        )
        return lat, lon, display_name, 0.55  # Nominatim confidence is moderate

    logger.debug(f"[Geocoder] Ollama-name unresolved: '{ollama_location_name}'")
    return None


def reload_db():
    """Reload the military base database from disk (for hot-updates)."""
    _load_db()
