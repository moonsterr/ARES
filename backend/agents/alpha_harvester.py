"""
Agent ALPHA — Telegram Harvester
Monitors 14 high-alert channels using Telethon (MTProto user client).
Translates and extracts intelligence from Hebrew/Arabic/Persian/Russian messages.

Reliability design:
- Never calls client.start() — that blocks forever without a TTY if session is invalid.
- Instead: connect → is_user_authorized() check → fail fast with a clear error.
- Startup backfill: on each connect, replay the last 30 min of messages so nothing
  is missed during restarts or brief network outages.
- Outer reconnect loop retries on disconnect with exponential back-off (cap 5 min).
- Session file is mounted from the host via docker-compose volume so it survives rebuilds.
- Re-auth: run auth_telegram.py on the host whenever the session is invalidated.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    AuthKeyUnregisteredError,
    AuthKeyDuplicatedError,
    SessionExpiredError,
    SessionRevokedError,
    UserDeactivatedError,
    UserDeactivatedBanError,
)

from ..intelligence.llm_pipeline import process_message
from ..intelligence.geocoder import resolve_location
from ..intelligence.confidence import initial_bba
from ..database import insert_event
from ..websocket_manager import manager
from ..config import settings

logger = logging.getLogger("alpha_harvester")

# Auth errors that mean the session is dead and needs manual re-auth.
# No point retrying — log clearly and park.
_DEAD_SESSION_ERRORS = (
    AuthKeyUnregisteredError,
    AuthKeyDuplicatedError,
    SessionExpiredError,
    SessionRevokedError,
    UserDeactivatedError,
    UserDeactivatedBanError,
)

# ── Watched channel list ──────────────────────────────────────────────
# Mix of IDF official, regional outlets, and OSINT aggregators.
# Non-English channels (Arabic, Hebrew, Persian, Russian) are translated
# via the Ollama pipeline before processing.
WATCHED_CHANNELS = [
    # Israeli / IDF
    "idfofficial",               # IDF verified official (173K subs)
    "kann_news",                 # Kan public broadcaster (Hebrew — translated)
    # Palestinian / resistance
    "SabrenNewss",               # Iraqi PMF / Iran-aligned (1M subs)
    "palinfo",                   # Hamas-affiliated news (Arabic)
    "QudsNen",                   # Palestine/Gaza/Houthi ops (121K subs)
    # Regional OSINT aggregators
    "intelsky",                  # IntelSky OSINT
    "militarymaps",              # Military Maps aggregator (29K subs)
    "middle_east_spectator",     # ME regional commentary (367K subs)
    "IntelSlava",                # Global conflict aggregator (404K subs)
    # Russian OSINT
    "rybar",                     # Rybar Russian OSINT (1.54M subs — translated)
    # Lebanese
    "LBCI_news",                 # LBCI Lebanese TV news (7.4K subs)
    # Iranian
    "irna_en",                   # IRNA official English (22K subs)
    # Lebanese / resistance axis
    "mehwaralmokawma",           # Mehwar Al-Mokawma resistance media (Arabic)
    # OSINT / tracking
    "OSINTdefender",             # OSINT breaking news
]

# ── Channel source reliability (α) weights ───────────────────────────
# α=1.0 means fully trusted; α=0 means ignored.
# These feed directly into the DST confidence engine.
CHANNEL_RELIABILITY: dict[str, float] = {
    "idfofficial":            0.90,   # verified IDF official
    "kann_news":              0.82,   # Israeli public broadcaster
    "SabrenNewss":            0.55,   # Iraqi PMF / Iran-aligned, known embellishment
    "palinfo":                0.50,   # Hamas-affiliated
    "QudsNen":                0.52,   # pro-resistance framing
    "intelsky":               0.78,
    "militarymaps":           0.72,   # pro-Russian framing, good raw data
    "middle_east_spectator":  0.70,   # pro-Iran bias (declared)
    "IntelSlava":             0.68,   # aggregator, mixed sourcing
    "rybar":                  0.65,   # pro-Russian framing, good raw data
    "LBCI_news":              0.72,   # established Lebanese broadcaster
    "irna_en":                0.45,   # Iranian state media
    "mehwaralmokawma":        0.58,   # resistance axis media (Arabic — translated)
    "OSINTdefender":          0.75,
}

# How far back to backfill on startup (catches messages missed during downtime)
_BACKFILL_MINUTES = 30


async def _process_and_store(raw_text: str, channel_name: str, alpha: float) -> None:
    """Run the full NLP → geocode → confidence → DB → broadcast pipeline."""
    intel = await process_message(raw_text, channel_name)

    if intel.category == "unknown" and intel.confidence < 0.3:
        return  # not conflict-related, drop

    for loc in intel.locations:
        coords = await resolve_location(loc.raw_text, loc.normalized)
        if coords:
            loc.lat, loc.lon = coords

    bba = initial_bba(intel, alpha)
    intel.bel          = bba["belief"]
    intel.pl           = bba["plausibility"]
    intel.conflict_k   = bba["conflict_k"]
    intel.source_alpha = alpha

    event_id = await insert_event(intel, source=f"telegram:{channel_name}")

    payload = intel.model_dump()
    payload["id"]     = event_id
    payload["source"] = f"telegram:{channel_name}"
    if intel.locations:
        payload["lat"]           = intel.locations[0].lat
        payload["lon"]           = intel.locations[0].lon
        payload["location_name"] = intel.locations[0].normalized
    payload["category"] = (
        intel.category.value if hasattr(intel.category, "value") else str(intel.category)
    )
    await manager.broadcast_json(payload)

    logger.info(
        f"[ALPHA] {channel_name} → {intel.category} "
        f"@ {intel.locations[0].normalized if intel.locations else 'unknown'} "
        f"conf={intel.confidence:.2f} K={intel.conflict_k:.2f}"
    )


async def _backfill(client: TelegramClient) -> None:
    """
    On startup, replay any messages posted in the last _BACKFILL_MINUTES
    that we would have missed while the backend was down.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_BACKFILL_MINUTES)
    total = 0
    for ch in WATCHED_CHANNELS:
        try:
            alpha = CHANNEL_RELIABILITY.get(ch.lower(), 0.50)
            async for msg in client.iter_messages(ch, limit=20):
                if msg.date < cutoff:
                    break
                if not msg.raw_text or len(msg.raw_text) < 20:
                    continue
                try:
                    await _process_and_store(msg.raw_text, ch, alpha)
                    total += 1
                except Exception as exc:
                    logger.warning(f"[ALPHA] Backfill error on {ch}: {exc}")
        except Exception as exc:
            logger.warning(f"[ALPHA] Backfill skipped {ch}: {exc}")
    if total:
        logger.info(f"[ALPHA] Backfill complete — replayed {total} missed messages")


async def run_harvester():
    """
    Long-running asyncio task. Connects to Telegram, backfills recent messages,
    then listens for new messages on all watched channels indefinitely.
    Reconnects automatically on transient network errors with exponential back-off.
    Fails fast and clearly on session invalidation.
    """
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        logger.warning(
            "[ALPHA] Telegram credentials not configured. "
            "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env to enable."
        )
        while True:
            await asyncio.sleep(3600)

    retry_delay = 5   # seconds — doubles on each transient failure, capped at 300
    attempt     = 0

    while True:
        client = TelegramClient(
            "ares_session",
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH,
        )
        client.flood_sleep_threshold = 60  # auto-sleep on Telegram rate limits < 60s

        try:
            # ── 1. Connect (no blocking TTY prompt) ──────────────────────
            await client.connect()

            # ── 2. Verify the session is authorised ──────────────────────
            if not await client.is_user_authorized():
                logger.error(
                    "[ALPHA] SESSION NOT AUTHORIZED — session file exists but is not "
                    "logged in. Run auth_telegram.py on the host to re-authenticate, "
                    "then restart the backend."
                )
                await client.disconnect()
                while True:
                    await asyncio.sleep(3600)

            me = await client.get_me()
            logger.info(
                f"[ALPHA] Authenticated as {me.first_name} "
                f"(@{me.username or 'no-username'}, +{me.phone})"
            )

            # ── 3. Backfill messages missed during downtime ───────────────
            await _backfill(client)

            # ── 4. Register live message handler ─────────────────────────
            @client.on(events.NewMessage(chats=WATCHED_CHANNELS))
            async def on_new_message(event_msg):
                try:
                    chat = await event_msg.get_chat()
                    channel_name = getattr(chat, "username", None) or chat.title
                    raw_text = event_msg.raw_text

                    if not raw_text or len(raw_text) < 20:
                        return

                    alpha = CHANNEL_RELIABILITY.get(channel_name.lower(), 0.50)
                    await _process_and_store(raw_text, channel_name, alpha)

                except FloodWaitError as e:
                    logger.warning(f"[ALPHA] FloodWait: sleeping {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except ChannelPrivateError:
                    ch = locals().get("channel_name", "unknown")
                    logger.error(
                        f"[ALPHA] Cannot access @{ch} — account is not a member. "
                        "Join the channel on your Telegram account to fix this."
                    )
                except Exception as exc:
                    logger.exception(f"[ALPHA] Error processing message: {exc}")

            # ── 5. Run until disconnected ─────────────────────────────────
            attempt = 0
            retry_delay = 5
            logger.info(f"[ALPHA] Harvester active — watching {len(WATCHED_CHANNELS)} channels")
            await client.run_until_disconnected()

            logger.warning("[ALPHA] Disconnected from Telegram — reconnecting in 10s...")
            await asyncio.sleep(10)

        except _DEAD_SESSION_ERRORS as exc:
            logger.error(
                f"[ALPHA] FATAL SESSION ERROR: {type(exc).__name__} — {exc}. "
                "The session has been revoked or the account is banned. "
                "Run auth_telegram.py on the host to re-authenticate, then restart."
            )
            try:
                await client.disconnect()
            except Exception:
                pass
            while True:
                await asyncio.sleep(3600)

        except Exception as exc:
            attempt += 1
            logger.warning(
                f"[ALPHA] Connection error (attempt {attempt}): {exc}. "
                f"Retrying in {retry_delay}s..."
            )
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)
