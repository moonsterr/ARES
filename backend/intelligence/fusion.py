"""
Cross-Source Event Fusion Engine
=================================
Correlates events across different data sources (Telegram, ADS-B, FIRMS)
and applies PCR5 confidence fusion when the same event is reported by
multiple sources.

Event correlation criteria:
  - Spatial: within configurable radius (default 25km)
  - Temporal: within configurable time window (default 2 hours)
  - Category: matching or compatible event categories

When a correlation is detected:
  - Fetch both events from DB
  - Apply PCR5 fusion
  - Update the higher-confidence event with the fusion result
  - Broadcast a fusion_update WebSocket message
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional

from .confidence import fuse_two_sources, haversine_km

logger = logging.getLogger("fusion")

# ── Correlation thresholds ────────────────────────────────────────────
SPATIAL_RADIUS_KM  = 25.0   # events within 25km are considered potentially the same
TEMPORAL_WINDOW_H  = 2.0    # events within 2 hours
COMPATIBLE_CATEGORIES = {
    "air_alert":       {"air_alert", "explosion", "ground_strike"},
    "ground_strike":   {"ground_strike", "explosion", "air_alert"},
    "explosion":       {"explosion", "ground_strike", "air_alert"},
    "troop_movement":  {"troop_movement"},
    "naval_event":     {"naval_event"},
    "casualty_report": {"casualty_report", "ground_strike", "explosion"},
    "unknown":         set(),  # unknown events don't correlate
}


async def find_correlating_events(
    pool,
    lat: float,
    lon: float,
    category: str,
    event_id: int,
    time_window_hours: float = TEMPORAL_WINDOW_H,
    radius_km: float = SPATIAL_RADIUS_KM,
) -> list[dict]:
    """
    Search for existing events that spatially and temporally correlate
    with the given new event.

    Returns list of event dicts (id, category, lat, lon, confidence, sources, etc.)
    """
    compatible = COMPATIBLE_CATEGORIES.get(category, set())
    if not compatible:
        return []

    # Convert category set to SQL array
    cat_list = list(compatible)
    cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
    radius_m = radius_km * 1000.0

    rows = await pool.fetch(
        """SELECT id, category,
                  ST_Y(location::geometry) AS lat,
                  ST_X(location::geometry) AS lon,
                  confidence, bel, pl, conflict_k, source_alpha, sources,
                  location_name, fusion_status
           FROM events
           WHERE id != $1
             AND category = ANY($2::text[])
             AND created_at > $3
             AND location IS NOT NULL
             AND ST_DWithin(
                 location::geography,
                 ST_MakePoint($4, $5)::geography,
                 $6
             )
           ORDER BY created_at DESC
           LIMIT 5""",
        event_id, cat_list, cutoff, lon, lat, radius_m
    )
    return [dict(r) for r in rows]


async def apply_fusion(
    pool,
    new_event: dict,
    correlated_event: dict,
) -> Optional[dict]:
    """
    Apply PCR5 fusion between two correlated events.
    Updates the database with fusion results.
    Returns the fusion result dict.
    """
    try:
        result = fuse_two_sources(
            loc1_name=new_event.get("location_name") or "Location A",
            lat1=float(new_event.get("lat") or 0),
            lon1=float(new_event.get("lon") or 0),
            conf1=float(new_event.get("confidence") or 0.5),
            alpha1=float(new_event.get("source_alpha") or 0.5),
            loc2_name=correlated_event.get("location_name") or "Location B",
            lat2=float(correlated_event.get("lat") or 0),
            lon2=float(correlated_event.get("lon") or 0),
            conf2=float(correlated_event.get("confidence") or 0.5),
            alpha2=float(correlated_event.get("source_alpha") or 0.5),
        )

        # Update the correlated event with fusion results
        await pool.execute(
            """UPDATE events
               SET conflict_k = $1,
                   bel = $2,
                   pl = $3,
                   fusion_status = $4,
                   sources = array_cat(sources, $5::text[])
               WHERE id = $6""",
            result["conflict_k"],
            result["source1"]["bel"],
            result["source1"]["pl"],
            result["status"],
            new_event.get("sources", []),
            correlated_event["id"],
        )

        logger.info(
            f"[Fusion] Events {new_event.get('id')} ↔ {correlated_event['id']}: "
            f"K={result['conflict_k']:.3f} status={result['status']} "
            f"dist={result['distance_between_reports_km']:.1f}km"
        )
        return result

    except Exception as e:
        logger.error(f"[Fusion] Error fusing events: {e}")
        return None


async def run_fusion_check(
    pool,
    new_event_id: int,
    new_event_lat: float,
    new_event_lon: float,
    new_event_category: str,
    new_event_confidence: float,
    new_event_alpha: float,
    new_event_location_name: str,
    broadcast_fn,
) -> None:
    """
    Entry point called after each new event is inserted.
    Checks for correlating events and applies fusion if found.
    Broadcasts fusion results via WebSocket.
    """
    if not new_event_lat or not new_event_lon:
        return

    correlating = await find_correlating_events(
        pool=pool,
        lat=new_event_lat,
        lon=new_event_lon,
        category=new_event_category,
        event_id=new_event_id,
    )

    for corr_event in correlating:
        new_event_dict = {
            "id":            new_event_id,
            "lat":           new_event_lat,
            "lon":           new_event_lon,
            "category":      new_event_category,
            "confidence":    new_event_confidence,
            "source_alpha":  new_event_alpha,
            "location_name": new_event_location_name,
            "sources":       [],
        }
        fusion_result = await apply_fusion(pool, new_event_dict, corr_event)
        if fusion_result:
            await broadcast_fn({
                "type":                "fusion_update",
                "event_id":            corr_event["id"],
                "correlated_with":     new_event_id,
                "fusion_status":       fusion_result["status"],
                "conflict_k":          fusion_result["conflict_k"],
                "distance_km":         fusion_result["distance_between_reports_km"],
                "location1": {
                    "name": fusion_result["source1"]["name"],
                    "bel":  fusion_result["source1"]["bel"],
                    "pl":   fusion_result["source1"]["pl"],
                },
                "location2": {
                    "name": fusion_result["source2"]["name"],
                    "bel":  fusion_result["source2"]["bel"],
                    "pl":   fusion_result["source2"]["pl"],
                },
            })
