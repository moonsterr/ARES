"""
Agent BRAVO-D: WebSDR HFGCS radio monitor.
Connects to a public HF WebSDR and captures audio on HFGCS frequencies.
Feeds to Whisper for speech-to-text detection of EAM traffic.

NOTE: This is a passive SIGINT capability. Audio is not stored.
Only transcribed text summaries are logged.
"""
import asyncio
import logging
import httpx
from ..config import settings

logger = logging.getLogger("bravo_websdr")

WEBSDR_HOST  = "http://websdr.ewi.utwente.nl:8901"
HFGCS_FREQS  = [8992, 11175]   # kHz — most active HFGCS frequencies
POLL_INTERVAL_S = 600           # capture every 10 minutes

# EAM (Emergency Action Message) pattern — 3-char phonetic prefix
EAM_PATTERN_PREFIXES = [
    "FOXTROT FOXTROT",
    "VICTOR VICTOR",
    "ROMEO ROMEO",
]


async def monitor_hfgcs_freq(freq_khz: int, duration_s: int = 30) -> bytes:
    """Capture `duration_s` seconds of audio from a WebSDR node."""
    params = {
        "freq":        freq_khz,
        "mode":        "usb",
        "passband_lo": 300,
        "passband_hi": 3000,
    }
    chunks = []
    max_bytes = 128 * 1024 * duration_s // 8  # rough estimate at 128kbps MP3

    async with httpx.AsyncClient(timeout=duration_s + 5) as client:
        try:
            async with client.stream("GET", f"{WEBSDR_HOST}/audio", params=params) as r:
                async for chunk in r.aiter_bytes(chunk_size=4096):
                    chunks.append(chunk)
                    if sum(len(c) for c in chunks) >= max_bytes:
                        break
        except Exception as e:
            logger.debug(f"[BRAVO-D] Audio stream error @ {freq_khz}kHz: {e}")
    return b"".join(chunks)


def is_eam_traffic(text: str) -> bool:
    """Check if transcribed text contains EAM pattern indicators."""
    text_upper = text.upper()
    return any(prefix in text_upper for prefix in EAM_PATTERN_PREFIXES)


async def run_websdr_monitor():
    """
    Periodic HFGCS monitor. Captures 30-second clips every 10 minutes.
    If Whisper (or an Ollama transcription) detects EAM-pattern text,
    broadcasts a SIGINT alert.

    NOTE: WebSDR integration is marked as secondary in the plan.
    Set ENABLE_WEBSDR=true in .env to activate.
    """
    if not settings.ENABLE_WEBSDR:
        logger.info("[BRAVO-D] WebSDR monitor disabled (ENABLE_WEBSDR=false). Skipping.")
        while True:
            await asyncio.sleep(3600)
        return

    logger.info(f"[BRAVO-D] WebSDR HFGCS monitor active — watching {HFGCS_FREQS} kHz")
    while True:
        for freq in HFGCS_FREQS:
            try:
                audio = await monitor_hfgcs_freq(freq, duration_s=30)
                if audio:
                    # TODO: pipe `audio` bytes to Whisper via subprocess or API
                    # Example Whisper integration (requires whisper package):
                    #
                    # import tempfile, whisper
                    # with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    #     f.write(audio)
                    #     tmp_path = f.name
                    # model = whisper.load_model("base")
                    # result = model.transcribe(tmp_path)
                    # transcript = result["text"]
                    # if is_eam_traffic(transcript):
                    #     from ..websocket_manager import manager
                    #     await manager.broadcast_json({
                    #         "type": "sigint_alert",
                    #         "freq_khz": freq,
                    #         "transcript": transcript,
                    #         "eam_detected": True,
                    #     })
                    logger.debug(f"[BRAVO-D] Captured {len(audio)} bytes @ {freq}kHz")
                else:
                    logger.debug(f"[BRAVO-D] No audio captured @ {freq}kHz")

            except Exception as e:
                logger.warning(f"[BRAVO-D] WebSDR error on {freq}kHz: {e}")

        await asyncio.sleep(POLL_INTERVAL_S)
