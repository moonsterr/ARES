"""
Agent BRAVO-B: NASA FIRMS thermal hotspot ingestion.
Polls VIIRS SNPP NRT data every 5 minutes.
Middle East bounding box: lon 25–65, lat 14–42.
"""
import asyncio
import httpx
import csv
import io
import logging
from datetime import datetime
from ..database import insert_hotspot, find_nearby_events, promote_to_verified
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("bravo_firms")

FIRMS_URL       = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
ME_BBOX         = "25,14,65,42"   # west,south,east,north
FUSION_RADIUS_M = 5000            # 5km radius for fusion validation
POLL_INTERVAL_S = 300             # poll every 5 minutes


async def poll_firms():
    if not settings.FIRMS_MAP_KEY:
        logger.warning(
            "[BRAVO-B] NASA FIRMS API key not configured. "
            "Set FIRMS_MAP_KEY in .env to enable thermal hotspot ingestion."
        )
        while True:
            await asyncio.sleep(3600)
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                for source in ["VIIRS_SNPP_NRT", "MODIS_NRT"]:
                    url = f"{FIRMS_URL}/{settings.FIRMS_MAP_KEY}/{source}/{ME_BBOX}/1"
                    resp = await client.get(url)
                    resp.raise_for_status()

                    reader  = csv.DictReader(io.StringIO(resp.text))
                    hotspots = list(reader)

                    verified_count = 0
                    for hs in hotspots:
                        if not hs.get("latitude") or not hs.get("longitude"):
                            continue

                        lat        = float(hs["latitude"])
                        lon        = float(hs["longitude"])
                        brightness = float(hs.get("bright_ti4") or hs.get("brightness") or 0)
                        confidence = hs.get("confidence", "nominal")
                        frp        = float(hs.get("frp", 0))

                        await insert_hotspot({
                            "lat":        lat,
                            "lon":        lon,
                            "source":     source,
                            "brightness": brightness,
                            "frp":        frp,
                            "confidence": confidence,
                            "detected_at": datetime.utcnow(),
                        })

                        # ── Fusion Validation ─────────────────────────────
                        # Check if any recent Telegram "strike" event is
                        # within 5km. If so, mark it as VERIFIED.
                        nearby = await find_nearby_events(lat, lon, FUSION_RADIUS_M)
                        for event_id in nearby:
                            await promote_to_verified(event_id, hs_source=source, frp=frp)
                            await manager.broadcast_json({
                                "type":        "fusion_verified",
                                "event_id":    event_id,
                                "hotspot_lat": lat,
                                "hotspot_lon": lon,
                                "frp_mw":      frp,
                                "sensor":      source,
                            })
                            verified_count += 1
                            logger.info(
                                f"[BRAVO-B] VERIFIED: event {event_id} "
                                f"confirmed by {source} hotspot (FRP={frp}MW)"
                            )

                    logger.info(
                        f"[BRAVO-B] {source}: ingested {len(hotspots)} hotspots, "
                        f"{verified_count} events verified"
                    )

            except httpx.HTTPStatusError as e:
                logger.error(f"[BRAVO-B] FIRMS HTTP error {e.response.status_code}: {e}")
            except Exception as e:
                logger.error(f"[BRAVO-B] FIRMS error: {e}")

            await asyncio.sleep(POLL_INTERVAL_S)
