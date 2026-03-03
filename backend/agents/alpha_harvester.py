"""
Agent ALPHA — Telegram Harvester
Monitors 15+ high-alert channels using Telethon.
Translates and extracts intelligence from Hebrew/Arabic/Persian messages.
"""
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChannelPrivateError

from ..intelligence.llm_pipeline import process_message
from ..intelligence.geocoder import resolve_location
from ..intelligence.confidence import initial_bba
from ..database import insert_event
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("alpha_harvester")

# ── Watched channel list ──────────────────────────────────────────────
# Mix of IDF official, regional outlets, and OSINT aggregators.
# See ARES_IMPLEMENTATION_PLAN.md Appendix B for full rationale.
WATCHED_CHANNELS = [
    # Israeli / IDF
    "idf_updates_english",       # Official IDF English
    "kann_news_eng",             # Kann public broadcaster
    "israeldefenseforces",       # IDF official channel
    # Palestinian / resistance
    "sabereen_news",             # Iraqi PMF / Iran-aligned
    "palinfo",                   # Hamas-affiliated news (Arabic)
    # Regional OSINT aggregators
    "intelsky",                  # IntelSky OSINT
    "militarymaps1",             # Military Maps aggregator
    "rybar_english",             # Rybar (Russian OSINT, translated)
    "middle_east_spectator",     # ME regional commentary
    # Lebanese
    "lebanese_breaking_news",    # Local Lebanese news
    "aljumhuriya_lb",            # Lebanese media
    # Iranian / regional
    "iran_briefing",             # Iran media monitor
    "irna_fa",                   # IRNA state media (Persian)
    # Yemeni
    "ansarallaheng",             # Houthi official English
    # SIGINT / tracking
    "wartranslated",             # Conflict translations
    "osint_collective",          # OSINT Collective
]

# ── Channel source reliability (α) weights ───────────────────────────
# α=1.0 means fully trusted; α=0 means ignored.
# These feed directly into the DST confidence engine.
CHANNEL_RELIABILITY: dict[str, float] = {
    "idf_updates_english":    0.88,
    "kann_news_eng":          0.82,
    "israeldefenseforces":    0.90,
    "sabereen_news":          0.55,   # state-adjacent, known embellishment
    "palinfo":                0.50,
    "intelsky":               0.78,
    "militarymaps1":          0.72,
    "rybar_english":          0.65,   # pro-Russian framing, good raw data
    "middle_east_spectator":  0.70,
    "lebanese_breaking_news": 0.68,
    "aljumhuriya_lb":         0.65,
    "iran_briefing":          0.60,
    "irna_fa":                0.45,   # state media
    "ansarallaheng":          0.48,   # official Houthi — self-serving
    "wartranslated":          0.80,
    "osint_collective":       0.85,
}


async def run_harvester():
    """
    Long-running asyncio task. Starts the Telethon client and
    registers a NewMessage handler on all watched channels.
    """
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        logger.warning(
            "[ALPHA] Telegram credentials not configured. "
            "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env to enable."
        )
        # Keep the task alive but inactive
        while True:
            await asyncio.sleep(3600)
        return

    client = TelegramClient(
        "ares_session",
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
    )
    client.flood_sleep_threshold = 60  # auto-sleep on rate limits < 60s

    @client.on(events.NewMessage(chats=WATCHED_CHANNELS))
    async def on_new_message(event_msg):
        try:
            chat = await event_msg.get_chat()
            channel_name = getattr(chat, "username", None) or chat.title
            raw_text = event_msg.raw_text

            if not raw_text or len(raw_text) < 20:
                return   # ignore very short messages / reactions

            α = CHANNEL_RELIABILITY.get(channel_name.lower(), 0.50)

            # Full NLP pipeline
            intel = await process_message(raw_text, channel_name)

            if intel.category == "unknown" and intel.confidence < 0.3:
                return   # not conflict-related, drop

            # Geocoding — resolve each extracted location
            for loc in intel.locations:
                coords = await resolve_location(loc.raw_text, loc.normalized)
                if coords:
                    loc.lat, loc.lon = coords

            # Build initial BBA for DST engine
            bba = initial_bba(intel, α)
            intel.bel = bba["belief"]
            intel.pl  = bba["plausibility"]
            intel.conflict_k  = bba["conflict_k"]
            intel.source_alpha = α

            # Persist to PostgreSQL
            event_id = await insert_event(intel, source=f"telegram:{channel_name}")

            # Broadcast to all WebSocket clients
            payload = intel.model_dump()
            payload["id"]     = event_id
            payload["source"] = f"telegram:{channel_name}"
            # Flatten locations for frontend
            if intel.locations:
                payload["lat"]           = intel.locations[0].lat
                payload["lon"]           = intel.locations[0].lon
                payload["location_name"] = intel.locations[0].normalized
            payload["category"] = intel.category.value if hasattr(intel.category, "value") else str(intel.category)
            await manager.broadcast_json(payload)

            logger.info(
                f"[ALPHA] {channel_name} → {intel.category} "
                f"@ {intel.locations[0].normalized if intel.locations else 'unknown'} "
                f"conf={intel.confidence:.2f} K={intel.conflict_k:.2f}"
            )

        except FloodWaitError as e:
            logger.warning(f"[ALPHA] FloodWait: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except ChannelPrivateError:
            channel_name_safe = locals().get("channel_name", "unknown")
            logger.error(f"[ALPHA] Cannot access {channel_name_safe} — not a member")
        except Exception as e:
            logger.exception(f"[ALPHA] Error processing message: {e}")

    await client.start(phone=settings.TELEGRAM_PHONE)
    logger.info(f"[ALPHA] Harvester active — watching {len(WATCHED_CHANNELS)} channels")
    await client.run_until_disconnected()
