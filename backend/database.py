"""
PostGIS database interface using asyncpg.
All spatial operations use EPSG:4326 (WGS84) geometry.
"""
import asyncpg
import logging
from .config import settings

logger = logging.getLogger("database")
_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("[DB] Connection pool initialized, schema applied")


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _pool


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] Connection pool closed")


# ── Schema DDL ────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- for text similarity search

CREATE TABLE IF NOT EXISTS events (
    id             BIGSERIAL PRIMARY KEY,
    category       TEXT NOT NULL,
    location       GEOMETRY(Point, 4326),
    location_name  TEXT,
    confidence     FLOAT DEFAULT 0.5,
    bel            FLOAT DEFAULT 0.0,    -- DST belief lower bound
    pl             FLOAT DEFAULT 1.0,    -- DST plausibility upper bound
    conflict_k     FLOAT DEFAULT 0.0,    -- DST conflict factor
    source_alpha   FLOAT DEFAULT 0.5,    -- source reliability weight
    sources        TEXT[],
    raw_text       TEXT,
    translation    TEXT,
    entities       JSONB DEFAULT '{}',
    verified       BOOLEAN DEFAULT FALSE,
    verified_by    TEXT,
    fusion_status  TEXT DEFAULT 'SINGLE_SOURCE',
    satellite_quicklook TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS events_location_gist  ON events USING GIST(location);
CREATE INDEX IF NOT EXISTS events_created_at_idx ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS events_category_idx   ON events(category);
CREATE INDEX IF NOT EXISTS events_verified_idx   ON events(verified);

CREATE TABLE IF NOT EXISTS hotspots (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT,
    location    GEOMETRY(Point, 4326),
    brightness  FLOAT,
    frp         FLOAT,
    confidence  TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS hotspots_location_gist ON hotspots USING GIST(location);
CREATE INDEX IF NOT EXISTS hotspots_detected_idx  ON hotspots(detected_at DESC);

CREATE TABLE IF NOT EXISTS aircraft (
    id          BIGSERIAL PRIMARY KEY,
    icao_hex    TEXT UNIQUE NOT NULL,
    callsign    TEXT,
    location    GEOMETRY(Point, 4326),
    altitude_ft INT,
    heading     FLOAT,
    speed_kts   FLOAT,
    ac_type     TEXT,
    reg         TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS aircraft_location_gist ON aircraft USING GIST(location);
CREATE INDEX IF NOT EXISTS aircraft_hex_idx       ON aircraft(icao_hex);

CREATE TABLE IF NOT EXISTS vessels (
    id          BIGSERIAL PRIMARY KEY,
    mmsi        TEXT UNIQUE NOT NULL,
    name        TEXT,
    location    GEOMETRY(Point, 4326),
    heading     FLOAT,
    speed_kts   FLOAT,
    vessel_type TEXT,
    flag        TEXT,
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS vessels_location_gist ON vessels USING GIST(location);
"""


# ── Insert / Upsert helpers ───────────────────────────────────────────

async def insert_event(intel, source: str) -> int:
    """
    Persist a ConflictIntel object to the events table.
    Returns the newly created event id.
    """
    pool = await get_pool()
    loc = intel.locations[0] if intel.locations else None
    point = (
        f"SRID=4326;POINT({loc.lon} {loc.lat})"
        if loc and loc.lat is not None and loc.lon is not None else None
    )
    row = await pool.fetchrow(
        """INSERT INTO events
           (category, location, location_name, confidence, bel, pl, conflict_k,
            source_alpha, sources, raw_text, translation, entities, fusion_status)
           VALUES ($1, ST_GeomFromEWKT($2), $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
           RETURNING id""",
        intel.category.value if hasattr(intel.category, 'value') else str(intel.category),
        point,
        loc.normalized if loc else None,
        intel.confidence,
        getattr(intel, 'bel', 0.0),
        getattr(intel, 'pl', 1.0),
        getattr(intel, 'conflict_k', 0.0),
        getattr(intel, 'source_alpha', 0.5),
        [source],
        intel.raw_text,
        intel.translation,
        intel.entities_json(),
        getattr(intel, 'fusion_status', 'SINGLE_SOURCE'),
    )
    return row["id"]


async def find_nearby_events(lat: float, lon: float, radius_m: float) -> list[int]:
    """Find recent unverified strike events within radius_m meters."""
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id FROM events
           WHERE category IN ('ground_strike', 'explosion', 'air_alert')
           AND verified = FALSE
           AND created_at > NOW() - INTERVAL '2 hours'
           AND ST_DWithin(
               location::geography,
               ST_MakePoint($1, $2)::geography,
               $3
           )""",
        lon, lat, radius_m,
    )
    return [r["id"] for r in rows]


async def promote_to_verified(event_id: int, hs_source: str, frp: float):
    """Mark an event as satellite-verified and boost its confidence."""
    pool = await get_pool()
    await pool.execute(
        """UPDATE events
           SET verified = TRUE,
               verified_by = $1,
               confidence = LEAST(confidence + 0.25, 1.0)
           WHERE id = $2""",
        f"{hs_source}(FRP={frp:.1f}MW)",
        event_id,
    )


async def update_event_quicklook(event_id: int, quicklook_url: str):
    """Attach a Sentinel-2 quicklook URL to an existing event."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE events SET satellite_quicklook = $1 WHERE id = $2",
        quicklook_url, event_id,
    )


async def insert_hotspot(data: dict):
    """Insert a NASA FIRMS hotspot record."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO hotspots (source, location, brightness, frp, confidence, detected_at)
           VALUES ($1, ST_GeomFromEWKT($2), $3, $4, $5, $6)
           ON CONFLICT DO NOTHING""",
        data["source"],
        f"SRID=4326;POINT({data['lon']} {data['lat']})",
        data["brightness"],
        data["frp"],
        data["confidence"],
        data["detected_at"],
    )


async def upsert_aircraft(data: dict):
    """Insert or update an aircraft position record."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO aircraft
           (icao_hex, callsign, location, altitude_ft, heading, speed_kts, ac_type, reg, last_seen)
           VALUES ($1,$2,ST_GeomFromEWKT($3),$4,$5,$6,$7,$8,NOW())
           ON CONFLICT (icao_hex) DO UPDATE SET
               callsign=EXCLUDED.callsign, location=EXCLUDED.location,
               altitude_ft=EXCLUDED.altitude_ft, heading=EXCLUDED.heading,
               speed_kts=EXCLUDED.speed_kts, last_seen=NOW()""",
        data["icao_hex"],
        data.get("callsign", ""),
        f"SRID=4326;POINT({data['lon']} {data['lat']})",
        int(data.get("altitude", 0) or 0),
        float(data.get("heading", 0) or 0),
        float(data.get("speed_kts", 0) or 0),
        data.get("type", ""),
        data.get("reg", ""),
    )


async def upsert_vessel(data: dict):
    """Insert or update a vessel AIS record."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO vessels
           (mmsi, name, location, heading, speed_kts, vessel_type, flag, last_seen)
           VALUES ($1,$2,ST_GeomFromEWKT($3),$4,$5,$6,$7,NOW())
           ON CONFLICT (mmsi) DO UPDATE SET
               name=EXCLUDED.name, location=EXCLUDED.location,
               heading=EXCLUDED.heading, speed_kts=EXCLUDED.speed_kts,
               last_seen=NOW()""",
        data["mmsi"],
        data.get("name", ""),
        f"SRID=4326;POINT({data['lon']} {data['lat']})",
        float(data.get("heading", 0) or 0),
        float(data.get("speed_kts", 0) or 0),
        data.get("vessel_type", ""),
        data.get("flag", ""),
    )


async def get_recent_events(limit: int = 100, category: str | None = None) -> list[dict]:
    """Fetch recent events for the REST fallback endpoint."""
    pool = await get_pool()
    if category:
        rows = await pool.fetch(
            """SELECT id, category,
                      ST_Y(location::geometry) AS lat,
                      ST_X(location::geometry) AS lon,
                      location_name, confidence, bel, pl, conflict_k,
                      sources, translation, raw_text, entities,
                      verified, verified_by, fusion_status,
                      satellite_quicklook, created_at
               FROM events
               WHERE category = $1
               ORDER BY created_at DESC LIMIT $2""",
            category, limit
        )
    else:
        rows = await pool.fetch(
            """SELECT id, category,
                      ST_Y(location::geometry) AS lat,
                      ST_X(location::geometry) AS lon,
                      location_name, confidence, bel, pl, conflict_k,
                      sources, translation, raw_text, entities,
                      verified, verified_by, fusion_status,
                      satellite_quicklook, created_at
               FROM events
               ORDER BY created_at DESC LIMIT $1""",
            limit
        )
    return [dict(r) for r in rows]
