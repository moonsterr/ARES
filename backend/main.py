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
from .agents.bravo_websdr import run_websdr_monitor
from .agents.bravo_marine import poll_marine
from .agents.bravo_sentinel import run_sentinel_worker
from .config import settings

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
            "alpha_telegram":  settings.ENABLE_TELEGRAM,
            "bravo_adsb":      settings.ENABLE_ADSB,
            "bravo_firms":     settings.ENABLE_FIRMS,
            "bravo_sentinel":  settings.ENABLE_SENTINEL,
            "bravo_websdr":    settings.ENABLE_WEBSDR,
            "bravo_marine":    settings.ENABLE_MARINE,
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
        "bravo_adsb": {
            "enabled":     settings.ENABLE_ADSB,
            "configured":  bool(settings.ADSB_RAPIDAPI_KEY),
            "description": "ADS-B Exchange military aircraft tracker",
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
            "configured":  True,  # no key needed
            "description": "WebSDR HFGCS radio monitor (EAM detection)",
        },
        "bravo_marine": {
            "enabled":     settings.ENABLE_MARINE,
            "configured":  bool(settings.MARINETRAFFIC_API_KEY),
            "description": "MarineTraffic AIS naval vessel tracker",
        },
    }
