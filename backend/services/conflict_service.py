"""
Conflict Service
================
Unified service layer for querying conflict events across all sources:
ACLED, UCDP, GDELT, RSS, Telegram.

Used by REST endpoints to aggregate and filter cross-source conflict data.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..database import get_recent_events

logger = logging.getLogger("conflict_service")


async def get_conflict_events(
    limit: int = 200,
    source: Optional[str] = None,
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    verified_only: bool = False,
) -> list[dict]:
    """
    Fetch conflict events with optional filtering.

    Parameters
    ----------
    limit           : Max events to return
    source          : Filter by source (acled, ucdp, gdelt, rss:*, telegram)
    category        : Filter by EventCategory value
    min_confidence  : Minimum confidence threshold
    verified_only   : Only return FIRMS-verified events
    """
    events = await get_recent_events(limit=limit * 2, category=category)

    filtered = []
    for ev in events:
        if source and ev.get("source", "").split(":")[0] != source.split(":")[0]:
            continue
        if ev.get("confidence", 0) < min_confidence:
            continue
        if verified_only and not ev.get("verified", False):
            continue
        filtered.append(ev)
        if len(filtered) >= limit:
            break

    return filtered


async def get_conflict_summary() -> dict:
    """
    Return a summary of conflict activity by source and category.
    """
    events = await get_recent_events(limit=500)

    sources: dict[str, int] = {}
    categories: dict[str, int] = {}
    verified_count = 0
    total = len(events)

    for ev in events:
        src = ev.get("source", "unknown")
        src_key = src.split(":")[0] if ":" in src else src
        sources[src_key] = sources.get(src_key, 0) + 1

        cat = ev.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

        if ev.get("verified"):
            verified_count += 1

    return {
        "total_events":   total,
        "verified_events": verified_count,
        "by_source":      sources,
        "by_category":    categories,
    }
