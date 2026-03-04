"""
ARES FastAPI Application
Starts all agents via lifespan context manager.
Exposes REST + WebSocket endpoints.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db, close_db, get_recent_events
from .websocket_manager import manager
from .agents.alpha_harvester import run_harvester
from .agents.bravo_adsb import poll_adsb
from .agents.bravo_firms import poll_firms
from .agents.bravo_news import poll_rss
from .agents.bravo_websdr import run_websdr_monitor
from .agents.bravo_marine import poll_marine
from .agents.bravo_sentinel import run_sentinel_worker
from .agents.gdelt_fetcher import poll_gdelt
from .config import settings

import json
from pathlib import Path

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ares.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB and launch all agent tasks."""
    await init_db()
    logger.info("[ARES] Database initialized")

    tasks = []

    if settings.ENABLE_TELEGRAM:
        tasks.append(asyncio.create_task(run_harvester(), name="alpha_harvester"))

    if settings.ENABLE_RSS:
        tasks.append(asyncio.create_task(poll_rss(), name="bravo_news"))

    if settings.ENABLE_GDELT:
        tasks.append(asyncio.create_task(poll_gdelt(), name="bravo_gdelt"))

    if settings.ENABLE_ADSB:
        tasks.append(asyncio.create_task(poll_adsb(), name="bravo_adsb"))

    if settings.ENABLE_FIRMS:
        tasks.append(asyncio.create_task(poll_firms(), name="bravo_firms"))

    if settings.ENABLE_SENTINEL:
        tasks.append(asyncio.create_task(run_sentinel_worker(), name="bravo_sentinel"))

    if settings.ENABLE_WEBSDR:
        tasks.append(asyncio.create_task(run_websdr_monitor(), name="bravo_websdr"))

    if settings.ENABLE_MARINE:
        tasks.append(asyncio.create_task(poll_marine(), name="bravo_marine"))

    logger.info(f"[ARES] {len(tasks)} agent tasks launched")
    yield

    # Shutdown: cancel all tasks cleanly
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await close_db()
    logger.info("[ARES] All agents stopped, database closed")


app = FastAPI(
    title="Project ARES",
    description="Autonomous Reconnaissance & Event Synthesis — Middle East Conflict Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── WebSocket endpoint ────────────────────────────────────────────────

@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client sends pings
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


# ── REST endpoints ────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events(
    limit: int = Query(default=100, ge=1, le=500),
    category: str | None = Query(default=None),
):
    """REST fallback for initial page load — returns last N events."""
    return await get_recent_events(limit=limit, category=category)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status":  "operational",
        "version": "1.0.0",
        "agents": {
            "alpha_telegram": settings.ENABLE_TELEGRAM,
            "bravo_news":     settings.ENABLE_RSS,
            "bravo_adsb":     settings.ENABLE_ADSB,
            "bravo_firms":    settings.ENABLE_FIRMS,
            "bravo_sentinel": settings.ENABLE_SENTINEL,
            "bravo_websdr":   settings.ENABLE_WEBSDR,
            "bravo_marine":   settings.ENABLE_MARINE,
        },
        "ws_clients": manager.connection_count,
    }


@app.get("/api/agents/status")
async def agent_status():
    """Returns the current status of each configured agent."""
    return {
        "alpha_harvester": {
            "enabled":     settings.ENABLE_TELEGRAM,
            "configured":  bool(settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH),
            "description": "Telegram channel monitor (15+ OSINT channels)",
        },
        "bravo_news": {
            "enabled":          settings.ENABLE_RSS,
            "configured":       bool(settings.RSS_FEEDS),
            "feed_count":       len(settings.RSS_FEEDS),
            "poll_interval_s":  settings.RSS_POLL_INTERVAL,
            "description":      "RSS news harvester — Al Jazeera, JPost, MEE (Ollama NER)",
        },
        "bravo_adsb": {
            "enabled":     settings.ENABLE_ADSB,
            "configured":  True,  # ADSB.lol v2 is keyless
            "description": "ADSB.lol v2 military aircraft tracker (no API key required)",
        },
        "bravo_firms": {
            "enabled":     settings.ENABLE_FIRMS,
            "configured":  bool(settings.FIRMS_MAP_KEY),
            "description": "NASA FIRMS thermal hotspot sensor (fusion validation)",
        },
        "bravo_sentinel": {
            "enabled":     settings.ENABLE_SENTINEL,
            "configured":  bool(settings.COPERNICUS_USERNAME),
            "description": "Copernicus Sentinel-2 post-strike imagery",
        },
        "bravo_websdr": {
            "enabled":     settings.ENABLE_WEBSDR,
            "configured":  True,
            "description": "WebSDR HFGCS radio monitor (EAM detection)",
        },
        "bravo_marine": {
            "enabled":     settings.ENABLE_MARINE,
            "configured":  bool(settings.MARINETRAFFIC_API_KEY),
            "description": "MarineTraffic AIS naval vessel tracker",
        },
        "bravo_gdelt": {
            "enabled":     settings.ENABLE_GDELT,
            "configured":  True,
            "poll_interval_s": settings.GDELT_POLL_INTERVAL,
            "description": "GDELT v2 news geo-event extractor",
        },
    }


# ── Infrastructure data endpoints ────────────────────────────────────────

def _load_infrastructure_file(filename: str):
    """Load a GeoJSON file from backend/data/ directory."""
    data_dir = Path(__file__).parent / "data"
    file_path = data_dir / filename
    if file_path.exists():
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[MAIN] Failed to load {filename}: {e}")
    return None


@app.get("/api/infrastructure")
async def get_infrastructure():
    """
    Returns all infrastructure overlay data (cables, pipelines, ports, military bases).
    GeoJSON format for use with Deck.gl PathLayer and IconLayer.
    """
    return {
        "cables": _load_infrastructure_file("cables.geojson"),
        "pipelines": _load_infrastructure_file("pipelines.geojson"),
        "ports": _load_infrastructure_file("ports.geojson"),
        "military_bases": _load_infrastructure_file("military_bases.geojson"),
    }


@app.get("/api/infrastructure/{layer}")
async def get_infrastructure_layer(layer: str):
    """
    Returns a specific infrastructure layer.
    Valid layers: cables, pipelines, ports, military_bases
    """
    valid_layers = ["cables", "pipelines", "ports", "military_bases"]
    if layer not in valid_layers:
        return {"error": f"Invalid layer. Valid: {valid_layers}"}, 404
    
    filename = f"{layer}.geojson"
    data = _load_infrastructure_file(filename)
    if data is None:
        return {"error": f"Layer {layer} not found"}, 404
    return data
