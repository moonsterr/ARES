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

    # ── GDELT ──────────────────────────────────────────────────────────
    GDELT_BASE_URL: str = Field(
        default="https://api.gdeltproject.org/api/v2/doc/doc",
        description="GDELT v2 Doc API base URL"
    )
    GDELT_POLL_INTERVAL: int = Field(
        default=900,
        description="Seconds between GDELT poll cycles (default 15 minutes)"
    )
    GDELT_MODE: str = Field(
        default="artlist",
        description="GDELT mode: artlist (articles), timelineraw (timeline)"
    )
    GDELT_MAX_RECORDS: int = Field(
        default=50,
        description="Maximum GDELT articles to fetch per cycle"
    )
    GDELT_QUERY: str = Field(
        default="(military OR strike OR attack OR conflict OR war OR bomb OR explosion OR Israel OR Gaza OR Lebanon OR Iran OR Syria OR Yemen OR Ukraine)",
        description="GDELT search query for conflict-related articles"
    )

    # ── ACLED ─────────────────────────────────────────────────────────
    ACLED_API_KEY: str = Field(
        default="",
        description="ACLED API key — register free at https://acleddata.com/register/"
    )
    ACLED_EMAIL: str = Field(
        default="",
        description="Email used when registering for ACLED (required alongside key)"
    )
    ACLED_BASE_URL: str = Field(
        default="https://api.acleddata.com/acled/read",
        description="ACLED v2 read endpoint"
    )
    ACLED_MAX_RECORDS: int = Field(
        default=200,
        description="Maximum events to fetch per ACLED poll cycle"
    )
    ACLED_POLL_INTERVAL: int = Field(
        default=3600,
        description="Seconds between ACLED poll cycles (default 1 hour)"
    )
    ACLED_RELIABILITY_ALPHA: float = Field(
        default=0.80,
        description="DST source reliability weight for ACLED (0–1)"
    )

    # ── UCDP ──────────────────────────────────────────────────────────
    UCDP_BASE_URL: str = Field(
        default="https://ucdpapi.pcr.uu.se/api/gedevents/24.1",
        description="UCDP GED REST API endpoint (no key required)"
    )
    UCDP_POLL_INTERVAL: int = Field(
        default=7200,
        description="Seconds between UCDP poll cycles (default 2 hours)"
    )
    UCDP_MAX_RECORDS: int = Field(
        default=100,
        description="Max events per UCDP page request"
    )
    UCDP_LOOKBACK_DAYS: int = Field(
        default=30,
        description="How many days back to query UCDP for new events"
    )
    UCDP_RELIABILITY_ALPHA: float = Field(
        default=0.78,
        description="DST source reliability weight for UCDP (0–1)"
    )

    # ── NGA Maritime Safety Information ───────────────────────────────
    NGA_BASE_URL: str = Field(
        default="https://msi.gs.mil/api/publications/broadcast-warn",
        description="NGA MSI broadcast warnings API (no key required)"
    )
    NGA_POLL_INTERVAL: int = Field(
        default=1800,
        description="Seconds between NGA NAVAREA poll cycles (default 30 minutes)"
    )

    # ── Agent feature flags ───────────────────────────────────────────
    ENABLE_TELEGRAM: bool = Field(default=False)
    ENABLE_RSS: bool = Field(default=True)
    ENABLE_GDELT: bool = Field(default=True)
    ENABLE_ADSB: bool = Field(default=True)
    ENABLE_FIRMS: bool = Field(default=True)
    ENABLE_SENTINEL: bool = Field(default=True)
    ENABLE_WEBSDR: bool = Field(default=False)
    ENABLE_MARINE: bool = Field(default=False)
    ENABLE_ACLED: bool = Field(default=False, description="Enable ACLED agent (requires API key + email)")
    ENABLE_UCDP: bool = Field(default=True, description="Enable UCDP agent (no key required)")
    ENABLE_NGA: bool = Field(default=True, description="Enable NGA NAVAREA warnings agent (no key required)")

    # ── Geocoding ─────────────────────────────────────────────────────
    NOMINATIM_USER_AGENT: str = Field(default="ARES-OSINT-Dashboard/1.0")
    GEOCODE_FUZZY_THRESHOLD: int = Field(default=78)

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")


settings = Settings()
