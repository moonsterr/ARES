"""
ARES Application Settings
Loaded from environment variables / .env file via pydantic-settings.
"""
from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://ares:ares_secret@localhost:5432/ares_db",
        description="asyncpg-compatible PostgreSQL connection URL"
    )

    # ── Telegram ──────────────────────────────────────────────────────
    TELEGRAM_API_ID: int = Field(default=0, description="From my.telegram.org")
    TELEGRAM_API_HASH: str = Field(default="", description="32-char hex from my.telegram.org")
    TELEGRAM_PHONE: str = Field(default="", description="Your phone with country code")

    # ── Ollama LLM ────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.1:8b")

    # ── NASA FIRMS ────────────────────────────────────────────────────
    FIRMS_MAP_KEY: str = Field(default="", description="From firms.modaps.eosdis.nasa.gov")

    # ── ADSB.lol ──────────────────────────────────────────────────────
    ADSB_LOL_BASE_URL: str = Field(
        default="https://api.adsb.lol/v2",
        description="Base URL for the ADSB.lol v2 API (no trailing slash)"
    )

    # ── Copernicus / Sentinel-2 ───────────────────────────────────────
    COPERNICUS_USERNAME: str = Field(default="")
    COPERNICUS_PASSWORD: str = Field(default="")
    COPERNICUS_CLIENT_ID: str = Field(default="cdse-public")
    COPERNICUS_CLIENT_SECRET: str = Field(default="")

    # ── MarineTraffic (optional) ──────────────────────────────────────
    MARINETRAFFIC_API_KEY: str = Field(default="")

    # ── Broadcastify (optional) ───────────────────────────────────────
    BROADCASTIFY_API_KEY: str = Field(default="")

    # ── CORS / WebSocket ──────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # ── RSS News Harvester ────────────────────────────────────────────
    RSS_FEEDS: list[str] = Field(
        default=[
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://www.jpost.com/rss/rssfeedsheadlines.aspx",
            "https://www.middleeasteye.net/rss",
        ],
        description="List of RSS feed URLs to poll for conflict intelligence"
    )
    RSS_POLL_INTERVAL: int = Field(
        default=300,
        description="Seconds between RSS poll cycles (default 5 minutes)"
    )

    # ── Agent feature flags ───────────────────────────────────────────
    ENABLE_TELEGRAM: bool = Field(default=False)
    ENABLE_RSS: bool = Field(default=True)
    ENABLE_ADSB: bool = Field(default=True)
    ENABLE_FIRMS: bool = Field(default=True)
    ENABLE_SENTINEL: bool = Field(default=True)
    ENABLE_WEBSDR: bool = Field(default=False)
    ENABLE_MARINE: bool = Field(default=False)

    # ── Geocoding ─────────────────────────────────────────────────────
    NOMINATIM_USER_AGENT: str = Field(default="ARES-OSINT-Dashboard/1.0")
    GEOCODE_FUZZY_THRESHOLD: int = Field(default=78)

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")


settings = Settings()
