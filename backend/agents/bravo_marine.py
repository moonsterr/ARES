"""
Agent BRAVO-E: Marine AIS vessel tracker.
Tracks naval vessels in Red Sea, Persian Gulf, and Mediterranean.

Primary source: MarineTraffic / Kpler AIS (requires commercial contract).
Free alternative: AISHub data sharing (research tier).

Set MARINETRAFFIC_API_KEY in .env to enable.
Leave blank to disable (agent will sleep silently).
"""
import asyncio
import httpx
import logging
from ..database import upsert_vessel
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("bravo_marine")

# Maritime regions of strategic interest
MARITIME_REGIONS = {
    "red_sea":       {"lat_min": 12.5, "lat_max": 30.0, "lon_min": 32.0, "lon_max": 43.5},
    "persian_gulf":  {"lat_min": 22.0, "lat_max": 30.0, "lon_min": 48.0, "lon_max": 60.0},
    "mediterranean": {"lat_min": 30.0, "lat_max": 36.5, "lon_min": 25.0, "lon_max": 37.0},
    "gulf_of_oman":  {"lat_min": 22.0, "lat_max": 26.5, "lon_min": 56.0, "lon_max": 65.0},
}

POLL_INTERVAL_S = 300   # 5 minutes

# MarineTraffic API endpoint for fleet/vessel positions
MT_VESSELS_URL = "https://services.marinetraffic.com/api/exportvessels/v:8"


def _in_region(lat: float, lon: float) -> str | None:
    """Return the region name if the position is in any tracked region."""
    for region_name, bbox in MARITIME_REGIONS.items():
        if (bbox["lat_min"] <= lat <= bbox["lat_max"] and
                bbox["lon_min"] <= lon <= bbox["lon_max"]):
            return region_name
    return None


async def poll_marine():
    """
    Poll MarineTraffic for vessel positions.
    Falls back gracefully if API key is not configured.
    """
    if not settings.MARINETRAFFIC_API_KEY:
        logger.info(
            "[BRAVO-E] MarineTraffic API key not configured. "
            "Set MARINETRAFFIC_API_KEY in .env to enable AIS tracking. "
            "Free alternative: AISHub (https://www.aishub.net)"
        )
        while True:
            await asyncio.sleep(3600)
        return

    if not settings.ENABLE_MARINE:
        logger.info("[BRAVO-E] Marine tracking disabled (ENABLE_MARINE=false).")
        while True:
            await asyncio.sleep(3600)
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                # Poll each maritime region of interest
                for region_name, bbox in MARITIME_REGIONS.items():
                    params = {
                        "v":           "8",
                        "KEY":         settings.MARINETRAFFIC_API_KEY,
                        "protocol":    "jsono",
                        "msgtype":     "simple",
                        "minlat":      bbox["lat_min"],
                        "maxlat":      bbox["lat_max"],
                        "minlon":      bbox["lon_min"],
                        "maxlon":      bbox["lon_max"],
                        "vessel_type": "6,7,8,9",   # cargo, tanker, high-speed, naval
                    }
                    resp = await client.get(MT_VESSELS_URL, params=params)
                    resp.raise_for_status()
                    vessels = resp.json()

                    region_count = 0
                    for v in vessels:
                        try:
                            lat = float(v.get("LAT", 0))
                            lon = float(v.get("LON", 0))
                            if not lat or not lon:
                                continue

                            record = {
                                "mmsi":        str(v.get("MMSI", "")),
                                "name":        v.get("SHIPNAME", ""),
                                "lat":         lat,
                                "lon":         lon,
                                "heading":     float(v.get("HEADING", 0) or 0),
                                "speed_kts":   float(v.get("SPEED", 0) or 0) / 10,
                                "vessel_type": v.get("SHIPTYPE", ""),
                                "flag":        v.get("FLAG", ""),
                            }
                            if record["mmsi"]:
                                await upsert_vessel(record)
                                region_count += 1
                        except Exception:
                            pass

                    if region_count:
                        logger.info(f"[BRAVO-E] AIS: {region_count} vessels in {region_name}")

                # Broadcast a vessel sweep summary
                await manager.broadcast_json({
                    "type":    "ais_sweep",
                    "regions": list(MARITIME_REGIONS.keys()),
                })

            except httpx.HTTPStatusError as e:
                logger.error(f"[BRAVO-E] MarineTraffic HTTP error {e.response.status_code}: {e}")
            except Exception as e:
                logger.error(f"[BRAVO-E] AIS error: {e}")

            await asyncio.sleep(POLL_INTERVAL_S)
