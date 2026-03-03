"""
Agent BRAVO-C: Copernicus Sentinel-2 imagery fetcher.
When a VERIFIED event is created, schedule a Sentinel-2 scene search
over that location to look for post-strike visual changes.
"""
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from ..config import settings
from ..database import update_event_quicklook
from ..websocket_manager import manager

logger = logging.getLogger("bravo_sentinel")

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)

# Queue of (event_id, lat, lon) tuples awaiting imagery retrieval
_imagery_queue: asyncio.Queue = asyncio.Queue()


def get_access_token() -> str:
    """Obtain a short-lived OAuth2 access token from Copernicus Data Space."""
    r = requests.post(TOKEN_URL, data={
        "client_id":  settings.COPERNICUS_CLIENT_ID or "cdse-public",
        "grant_type": "password",
        "username":   settings.COPERNICUS_USERNAME,
        "password":   settings.COPERNICUS_PASSWORD,
    }, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


async def fetch_sentinel_quicklook(lat: float, lon: float, event_id: int) -> Optional[str]:
    """
    Search for a recent cloud-free Sentinel-2 L2A scene over the
    given coordinates. Return the quicklook thumbnail URL if found.
    """
    if not settings.COPERNICUS_USERNAME or not settings.COPERNICUS_PASSWORD:
        return None

    try:
        token = get_access_token()
        delta   = 0.1  # ~11km bbox
        bbox_wkt = (
            f"POLYGON(({lon-delta} {lat-delta},{lon+delta} {lat-delta},"
            f"{lon+delta} {lat+delta},{lon-delta} {lat+delta},{lon-delta} {lat-delta}))"
        )
        end   = datetime.utcnow()
        start = end - timedelta(days=7)

        query = (
            f"Collection/Name eq 'SENTINEL-2' and "
            f"contains(Name,'MSIL2A') and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{bbox_wkt}') and "
            f"ContentDate/Start gt {start.strftime('%Y-%m-%dT%H:%M:%SZ')} and "
            f"ContentDate/Start lt {end.strftime('%Y-%m-%dT%H:%M:%SZ')} and "
            f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/OData.CSC.DoubleAttribute/Value le 20.00)"
        )
        r = requests.get(
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
            params={
                "$filter":  query,
                "$orderby": "ContentDate/Start desc",
                "$top":     1,
                "$expand":  "Assets",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        r.raise_for_status()
        products = r.json().get("value", [])
        if not products:
            return None

        assets = products[0].get("Assets", [])
        for asset in assets:
            if asset.get("Type") == "QUICKLOOK":
                quicklook_url = asset["DownloadLink"]
                logger.info(f"[BRAVO-C] Sentinel-2 quicklook found for event {event_id}: {quicklook_url}")
                return quicklook_url

    except Exception as e:
        logger.error(f"[BRAVO-C] Sentinel error for event {event_id}: {e}")
    return None


async def enqueue_imagery_request(event_id: int, lat: float, lon: float):
    """
    Add an event to the imagery fetch queue.
    Called when an event is promoted to VERIFIED status.
    """
    await _imagery_queue.put((event_id, lat, lon))


async def run_sentinel_worker():
    """
    Background worker that processes the imagery fetch queue.
    Throttled to avoid overwhelming Copernicus API.
    """
    if not settings.COPERNICUS_USERNAME:
        logger.warning(
            "[BRAVO-C] Copernicus credentials not configured. "
            "Set COPERNICUS_USERNAME/PASSWORD in .env for Sentinel-2 imagery."
        )
        while True:
            await asyncio.sleep(3600)
        return

    logger.info("[BRAVO-C] Sentinel-2 worker ready")
    while True:
        try:
            event_id, lat, lon = await asyncio.wait_for(
                _imagery_queue.get(), timeout=60.0
            )
        except asyncio.TimeoutError:
            continue

        try:
            quicklook_url = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _fetch_sync(lat, lon, event_id)
            )
            if quicklook_url:
                await update_event_quicklook(event_id, quicklook_url)
                await manager.broadcast_json({
                    "type":              "satellite_imagery",
                    "event_id":          event_id,
                    "quicklook_url":     quicklook_url,
                    "satellite":         "Sentinel-2 L2A",
                })
                logger.info(f"[BRAVO-C] Imagery attached to event {event_id}")
            else:
                logger.debug(f"[BRAVO-C] No imagery found for event {event_id}")

        except Exception as e:
            logger.error(f"[BRAVO-C] Worker error for event {event_id}: {e}")

        # Throttle: 1 request per 5 seconds
        await asyncio.sleep(5)


def _fetch_sync(lat: float, lon: float, event_id: int) -> Optional[str]:
    """Synchronous wrapper for fetch_sentinel_quicklook (runs in thread pool)."""
    import asyncio as _asyncio
    try:
        loop = _asyncio.new_event_loop()
        result = loop.run_until_complete(fetch_sentinel_quicklook(lat, lon, event_id))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"[BRAVO-C] Sync fetch error: {e}")
        return None
