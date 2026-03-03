"""
Agent BRAVO-A: ADSB.lol military aircraft poller
Strategy:
  1. Fetch global military-only feed  → https://api.adsb.lol/v2/mil
  2. Fetch high-precision regional feed → https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}
     centred on Tel Aviv [32.0, 34.8] at 250 nm radius.
  3. Merge both sets, de-duplicate on ICAO hex.
  4. Filter merged set to Middle East bounding box.
  5. Upsert to DB and broadcast over WebSocket.

Poll cadence: 10 s cool-down between requests (good-citizen policy; API is un-rated).
"""
import asyncio
import httpx
import logging
from ..database import upsert_aircraft
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("bravo_adsb")

# ── Middle East bounding box ───────────────────────────────────────────────────
ME_BBOX = {"lat_min": 14.0, "lat_max": 42.0, "lon_min": 25.0, "lon_max": 65.0}

# ── Regional point-radius parameters (Tel Aviv / Central region, 250 nm) ──────
ME_CENTER_LAT = 32.0
ME_CENTER_LON = 34.8
ME_RADIUS_NM  = 250

# ── Timing ────────────────────────────────────────────────────────────────────
POLL_INTERVAL_S = 10   # 10-second cool-down between full poll cycles

# ── HTTP headers ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "ARES-OSINT-Project/v1.0 (Student Project; Contact: ali@ali-pc)",
    "Accept":     "application/json",
}


def _parse_aircraft(ac: dict) -> dict | None:
    """
    Map a single ADSB.lol v2 aircraft object to the internal record schema.
    Returns None if the entry lacks a valid ICAO hex or coordinates.
    """
    icao_hex = ac.get("hex", "").strip().upper()
    if not icao_hex:
        return None

    # lat/lon may be absent for ground-only transponder squitters
    try:
        lat = float(ac["lat"])
        lon = float(ac["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    # alt_baro can be the string "ground" — treat that as 0
    raw_alt = ac.get("alt_baro", 0)
    try:
        altitude = int(raw_alt)
    except (TypeError, ValueError):
        altitude = 0

    return {
        "icao_hex":  icao_hex,
        "callsign":  ac.get("flight", "").strip() or None,
        "lat":       lat,
        "lon":       lon,
        "altitude":  altitude,
        "heading":   ac.get("track", 0) or 0,
        "speed_kts": ac.get("gs", 0) or 0,
        "type":      ac.get("t", "") or "",
        "desc":      ac.get("desc", "") or "",
        "reg":       ac.get("r", "") or "",
    }


def _in_me_bbox(record: dict) -> bool:
    return (
        ME_BBOX["lat_min"] <= record["lat"] <= ME_BBOX["lat_max"]
        and ME_BBOX["lon_min"] <= record["lon"] <= ME_BBOX["lon_max"]
    )


async def _fetch_global_mil(client: httpx.AsyncClient) -> list[dict]:
    """Fetch the global military-only feed from ADSB.lol."""
    url = f"{settings.ADSB_LOL_BASE_URL}/mil"
    try:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("ac", [])
    except httpx.HTTPStatusError as e:
        logger.error(f"[BRAVO-A] Global mil feed HTTP {e.response.status_code}: {e}")
    except Exception as e:
        logger.error(f"[BRAVO-A] Global mil feed error: {e}")
    return []


async def _fetch_regional(client: httpx.AsyncClient) -> list[dict]:
    """Fetch the point-radius feed centred on Tel Aviv at 250 nm."""
    url = (
        f"{settings.ADSB_LOL_BASE_URL}/point"
        f"/{ME_CENTER_LAT}/{ME_CENTER_LON}/{ME_RADIUS_NM}"
    )
    try:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("ac", [])
    except httpx.HTTPStatusError as e:
        logger.error(f"[BRAVO-A] Regional feed HTTP {e.response.status_code}: {e}")
    except Exception as e:
        logger.error(f"[BRAVO-A] Regional feed error: {e}")
    return []


async def poll_adsb():
    """Main polling loop for Agent BRAVO-A."""
    logger.info(
        f"[BRAVO-A] ADSB.lol poller starting — "
        f"global /mil + regional point/{ME_CENTER_LAT}/{ME_CENTER_LON}/{ME_RADIUS_NM}nm, "
        f"cool-down {POLL_INTERVAL_S}s"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            try:
                # ── 1. Fetch both sources concurrently ────────────────────────
                global_raw, regional_raw = await asyncio.gather(
                    _fetch_global_mil(client),
                    _fetch_regional(client),
                )

                # ── 2. Merge + de-duplicate on ICAO hex ───────────────────────
                seen:    set[str]  = set()
                records: list[dict] = []

                for raw_ac in (*global_raw, *regional_raw):
                    record = _parse_aircraft(raw_ac)
                    if record is None:
                        continue
                    if record["icao_hex"] in seen:
                        continue
                    seen.add(record["icao_hex"])
                    records.append(record)

                # ── 3. Filter to Middle East bounding box ─────────────────────
                me_aircraft = [r for r in records if _in_me_bbox(r)]

                # ── 4. Persist to database ────────────────────────────────────
                for record in me_aircraft:
                    await upsert_aircraft(record)

                # ── 5. Broadcast sweep to connected frontends ─────────────────
                await manager.broadcast_json({
                    "type":    "adsb_sweep",
                    "count":   len(me_aircraft),
                    "source":  "adsb.lol",
                    "aircraft": [
                        {
                            "icao_hex":  r["icao_hex"],
                            "callsign":  r["callsign"],
                            "lat":       r["lat"],
                            "lon":       r["lon"],
                            "altitude":  r["altitude"],
                            "heading":   r["heading"],
                            "speed_kts": r["speed_kts"],
                            "type":      r["type"],
                            "desc":      r["desc"],
                        }
                        for r in me_aircraft[:50]   # cap broadcast payload
                    ],
                })

                logger.info(
                    f"[BRAVO-A] ADSB.lol: {len(me_aircraft)} military AC in ME region "
                    f"(global={len(global_raw)}, regional={len(regional_raw)}, "
                    f"merged={len(records)})"
                )

            except Exception as e:
                logger.error(f"[BRAVO-A] Unexpected error in poll loop: {e}")

            # ── Cool-down (good-citizen rate limiting) ────────────────────────
            await asyncio.sleep(POLL_INTERVAL_S)
