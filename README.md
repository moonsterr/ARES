# ARES — Autonomous Reconnaissance & Event Synthesis

A real-time, multi-source OSINT fusion dashboard for monitoring armed conflict. ARES ingests raw signals from eleven independent data sources simultaneously, fuses conflicting reports using Dempster-Shafer PCR5 evidential reasoning, and streams structured intelligence events to a live 2D map — sub-second latency, no manual refresh.

---

## What it does

Raw data comes in from RSS feeds, Telegram channels, GDELT, ADS-B transponders, NASA fire satellites, Sentinel-2 imagery, AIS vessel trackers, ACLED, UCDP, and NGA maritime warnings. Each event passes through a language detection → translation → NER → geocoding → confidence scoring pipeline. When two independent sources report the same event within 25 km and 2 hours, PCR5 merges them and emits a fused event with a mathematically derived `[Belief, Plausibility]` interval. When sources contradict each other, a `CONFLICT_ALERT` flag is raised instead of silently picking one.

The frontend shows all of this on a dark 2D map: colour-coded event pins, heatmap density, live aircraft tracks, vessel positions, thermal hotspots, and overlays for military bases, ports, pipelines, submarine cables, and nuclear sites.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Data Sources                     │
│  RSS·170+ feeds  GDELT  Telegram  ADSB.lol          │
│  NASA FIRMS  Sentinel-2  ACLED  UCDP  NGA  AIS      │
└───────────────────┬─────────────────────────────────┘
                    │  async agents (one task each)
┌───────────────────▼─────────────────────────────────┐
│                 Intelligence Pipeline               │
│  fasttext detect → Ollama translate → regex NER     │
│  → fuzzy geocoder → DST PCR5 confidence → DB insert │
└───────────────────┬─────────────────────────────────┘
                    │  WebSocket broadcast
┌───────────────────▼─────────────────────────────────┐
│            FastAPI + PostgreSQL/PostGIS             │
│       REST API · WebSocket · asyncpg pool           │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│          React + Deck.gl + MapLibre GL              │
│    9 toggleable layers · 12 region presets          │
│    EventLog sidebar · Bel/Pl confidence meter       │
└─────────────────────────────────────────────────────┘
```

---

## Agents

| Code | Agent | Source | Interval | Key |
|------|-------|--------|----------|-----|
| ALPHA | Telegram Monitor | 16+ OSINT channels | Real-time | `TELEGRAM_API_ID/HASH` |
| BRAVO-N | RSS Harvester | 170+ feeds | 5 min | None |
| BRAVO-G | GDELT Extractor | GDELT v2 Doc API | 15 min | None |
| BRAVO-A | ADS-B Tracker | ADSB.lol `/mil` + radius | 10 sec | None |
| BRAVO-B | FIRMS Hotspots | NASA FIRMS thermal CSV | 5 min | `FIRMS_MAP_KEY` |
| BRAVO-C | Sentinel-2 Imagery | Copernicus Dataspace | On demand | Copernicus account |
| BRAVO-D | WebSDR Radio | WebSDR HFGCS | — | Stub |
| BRAVO-E | AIS Vessels | MarineTraffic API | Configurable | Commercial key |
| CHARLIE-A | ACLED Conflicts | ACLED REST API (OAuth2) | 1 hour | Free registration |
| CHARLIE-B | UCDP Events | UCDP GED REST API | 2 hours | Access token |
| CHARLIE-C | NGA Warnings | NGA MSI broadcast-warn | 30 min | None |

Default-on (no credentials): BRAVO-N, BRAVO-G, BRAVO-A, BRAVO-B, BRAVO-C, CHARLIE-B, CHARLIE-C

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker + Docker Compose v2 | `docker compose` (not `docker-compose`) |
| Ollama | Must run on the **host** (GPU access). Install from [ollama.ai](https://ollama.ai) |
| `llama3.1:8b` model | `ollama pull llama3.1:8b` |
| Node.js 20+ | For running the frontend outside Docker |

---

## Quick start

```bash
# 1. Clone
git clone <repo-url> && cd ares

# 2. Copy and fill in the env file
cp .env.example .env
# Edit .env — minimum required: FIRMS_MAP_KEY (free from NASA)
# Ollama runs on host — OLLAMA_BASE_URL is pre-configured

# 3. Build and start postgres + backend
docker compose up postgres backend -d --build

# 4. Run the frontend (hot-reload)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The backend API is at `http://localhost:8000`. WebSocket at `ws://localhost:8000/ws/events`.

---

## Environment variables

Copy `.env.example` to `.env`. Variables marked **required** must be set for the corresponding agent to function. All others have sane defaults.

### Core

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql://ares:ares_secret@localhost:5432/ares_db` | asyncpg connection string (overridden in Docker) |
| `OLLAMA_BASE_URL` | Yes | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Model for translation + NER |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

### Telegram (ALPHA agent)

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_API_ID` | `0` | Integer from [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_API_HASH` | `""` | 32-char hex from my.telegram.org |
| `TELEGRAM_PHONE` | `""` | Your phone number with country code |
| `ENABLE_TELEGRAM` | `false` | Set `true` to activate |

### NASA FIRMS (BRAVO-B)

| Variable | Default | Description |
|----------|---------|-------------|
| `FIRMS_MAP_KEY` | `""` | Free from [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| `ENABLE_FIRMS` | `true` | Disable if no key |

### Copernicus / Sentinel-2 (BRAVO-C)

| Variable | Default | Description |
|----------|---------|-------------|
| `COPERNICUS_USERNAME` | `""` | [Copernicus Dataspace](https://dataspace.copernicus.eu) account email |
| `COPERNICUS_PASSWORD` | `""` | Copernicus Dataspace password |
| `COPERNICUS_CLIENT_ID` | `cdse-public` | Leave as default |
| `ENABLE_SENTINEL` | `true` | Disable if no account |

### ACLED (CHARLIE-A)

| Variable | Default | Description |
|----------|---------|-------------|
| `ACLED_EMAIL` | `""` | [ACLED](https://acleddata.com/register/) account email |
| `ACLED_PASSWORD` | `""` | ACLED account password (used for OAuth2 token fetch) |
| `ACLED_TOKEN_URL` | `https://acleddata.com/oauth/token` | OAuth2 token endpoint |
| `ACLED_BASE_URL` | `https://acleddata.com/api/acled/read` | Data endpoint |
| `ACLED_MAX_RECORDS` | `200` | Events per poll cycle |
| `ACLED_POLL_INTERVAL` | `3600` | Seconds between polls |
| `ACLED_RELIABILITY_ALPHA` | `0.80` | DST source reliability weight |
| `ENABLE_ACLED` | `true` | Set `false` if no credentials |

### UCDP (CHARLIE-B)

| Variable | Default | Description |
|----------|---------|-------------|
| `UCDP_ACCESS_TOKEN` | `""` | Register at [ucdpapi.pcr.uu.se](https://ucdpapi.pcr.uu.se) |
| `UCDP_BASE_URL` | `https://ucdpapi.pcr.uu.se/api/gedevents/24.1` | GED API endpoint |
| `UCDP_POLL_INTERVAL` | `7200` | Seconds between polls |
| `UCDP_LOOKBACK_DAYS` | `30` | Days of history to query |
| `UCDP_RELIABILITY_ALPHA` | `0.78` | DST source reliability weight |
| `ENABLE_UCDP` | `true` | Disable if no token |

### NGA Maritime (CHARLIE-C)

| Variable | Default | Description |
|----------|---------|-------------|
| `NGA_BASE_URL` | `https://msi.gs.mil/api/publications/broadcast-warn` | NGA MSI endpoint |
| `NGA_POLL_INTERVAL` | `1800` | Seconds between polls |
| `ENABLE_NGA` | `false` | Geo-blocked outside the US — disable unless behind a US proxy |

### MarineTraffic AIS (BRAVO-E)

| Variable | Default | Description |
|----------|---------|-------------|
| `MARINETRAFFIC_API_KEY` | `""` | Commercial key from MarineTraffic |
| `ENABLE_MARINE` | `false` | Set `true` once you have a key |

### RSS / GDELT

| Variable | Default | Description |
|----------|---------|-------------|
| `RSS_POLL_INTERVAL` | `300` | Seconds between RSS cycles |
| `GDELT_POLL_INTERVAL` | `900` | Seconds between GDELT cycles |
| `GDELT_MAX_RECORDS` | `50` | Articles per GDELT cycle |
| `GDELT_QUERY` | `(military OR strike OR ...)` | GDELT search query |
| `ENABLE_RSS` | `true` | Toggle RSS agent |
| `ENABLE_GDELT` | `true` | Toggle GDELT agent |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_WS_URL` | `ws://localhost:8000/ws/events` | WebSocket endpoint |
| `VITE_CESIUM_ION_TOKEN` | `""` | Optional Cesium Ion token (unused currently) |

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/events?limit=N&category=X` | Recent events (default 200) |
| `GET` | `/api/acled-events` | ACLED-sourced events only |
| `GET` | `/api/ucdp-events` | UCDP-sourced events only |
| `GET` | `/api/nga-warnings` | NGA NAVAREA maritime warnings |
| `GET` | `/api/conflict/summary` | Event counts by source and category |
| `GET` | `/api/infrastructure` | All 5 GeoJSON infrastructure layers |
| `GET` | `/api/infrastructure/{layer}` | Single layer: `cables`, `pipelines`, `ports`, `military_bases`, `nuclear_sites` |
| `GET` | `/api/health` | Agent enable states + WebSocket client count |
| `GET` | `/api/agents/status` | Per-agent config details |
| `WS`  | `/ws/events` | Real-time event stream |

### WebSocket message types

All messages are JSON objects. The `category` field identifies the type:

| Type | Description |
|------|-------------|
| Standard event | Has `id`, `category`, `lat`, `lon`, `bel`, `pl`, `sources[]` |
| `adsb_sweep` | Array of aircraft: `icao_hex`, `callsign`, `altitude_ft`, `heading` |
| `ais_sweep` | Array of vessels: `mmsi`, `name`, `heading`, `speed_kts` |
| `fusion_verified` | Event promoted to VERIFIED by FIRMS hotspot match |
| `fusion_update` | DST `bel`/`pl` updated after cross-source PCR5 |
| `satellite_imagery` | Sentinel-2 quicklook URL attached to an event |

---

## Confidence scoring

Every event carries a `[Bel, Pl]` Dempster-Shafer uncertainty interval.

- **Belief (Bel)** — lower bound: minimum probability the event occurred, given the evidence
- **Plausibility (Pl)** — upper bound: maximum probability consistent with the evidence
- **Conflict K** — degree of contradiction between sources (0 = full agreement, 1 = full contradiction)

Source reliability weights (α):

| Source | α |
|--------|---|
| Reuters / BBC | 0.82–0.85 |
| NGA NAVAREA | 0.82 |
| ACLED | 0.80 |
| UCDP | 0.78 |
| Al Jazeera / NYT | 0.72–0.80 |
| GDELT | 0.65 |
| Iran state media | 0.45 |

**Fusion outcomes**:

| K value | `fusion_status` | Action |
|---------|-----------------|--------|
| K < 0.3 | `FUSED` | Sources agree — merge to weighted centroid |
| 0.3 ≤ K < 0.5 | `UNCERTAIN` | Display both candidate locations |
| K ≥ 0.5 | `CONFLICT_ALERT` | Flag for human review, do not fuse |

---

## Map layers

| Layer | Default | Data |
|-------|---------|------|
| Conflict events | On | All ingested events, colour-coded by category |
| Heatmap | Off | Confidence-weighted density |
| ADS-B aircraft | On | Live military aircraft positions + heading |
| AIS vessels | On | Live vessel positions |
| FIRMS hotspots | Off | NASA thermal detections |
| Military bases | Off | 63 installations (GeoJSON) |
| Ports | Off | 29 major shipping ports |
| Pipelines | Off | Oil (red) and gas (green) routes |
| Submarine cables | Off | Fibre optic cable routes |

**Event colour coding**: verified=green, high-conflict=purple, air_alert=red, ground_strike=orange, troop_movement=blue, naval_event=cyan, explosion=yellow, casualty_report=pink, unknown=grey

**12 named regions**: Middle East, Levant, Gaza, Persian Gulf, Red Sea, Yemen, Iran, Eastern Mediterranean, North Africa, Horn of Africa, Ukraine, Caucasus

---

## Database schema

PostgreSQL 15 + PostGIS 3.4. All tables are created automatically on first startup.

**`events`** — primary intelligence store

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL PK | |
| `category` | TEXT | EventCategory value |
| `location` | GEOMETRY(Point, 4326) | WGS84 |
| `location_name` | TEXT | Human-readable place name |
| `confidence` | FLOAT | 0–1 overall confidence |
| `bel` | FLOAT | DST belief lower bound |
| `pl` | FLOAT | DST plausibility upper bound |
| `conflict_k` | FLOAT | DST conflict factor |
| `sources` | TEXT[] | Source identifiers |
| `raw_text` | TEXT | Original text |
| `translation` | TEXT | English translation |
| `entities` | JSONB | Weapons, units, casualties, language |
| `verified` | BOOLEAN | Confirmed by FIRMS hotspot |
| `fusion_status` | TEXT | SINGLE_SOURCE / FUSED / UNCERTAIN / CONFLICT_ALERT |
| `satellite_quicklook` | TEXT | Sentinel-2 image URL |
| `created_at` | TIMESTAMPTZ | UTC |

**`hotspots`** — NASA FIRMS thermal detections (`source`, `location`, `brightness`, `frp`, `confidence`, `detected_at`)

**`aircraft`** — ADS-B positions, upserted by `icao_hex` (`callsign`, `location`, `altitude_ft`, `heading`, `speed_kts`, `ac_type`, `last_seen`)

**`vessels`** — AIS positions, upserted by `mmsi` (`name`, `location`, `heading`, `speed_kts`, `vessel_type`, `flag`, `last_seen`)

---

## Project structure

```
ares/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py              # All settings via pydantic-settings
│   ├── main.py                # FastAPI app + agent startup
│   ├── database.py            # asyncpg pool + DDL + helpers
│   ├── websocket_manager.py   # Fan-out broadcast hub
│   ├── agents/                # 11 data source agents
│   ├── intelligence/          # LLM pipeline, geocoder, DST engine, fusion
│   ├── models/                # ConflictIntel, EventCategory, LocationEntity
│   ├── services/              # conflict_service (REST query helpers)
│   ├── utils/                 # Circuit breaker
│   └── data/
│       ├── rss_feeds.json         # 170+ feeds with per-source reliability weights
│       ├── military_bases.geojson # 63 installations
│       ├── nuclear_sites.geojson  # 15 verified nuclear facilities
│       ├── ports.geojson          # 29 major shipping ports
│       ├── pipelines.geojson      # Oil and gas pipeline routes
│       ├── cables.geojson         # Submarine fibre optic cables
│       └── mideast_military_bases.json  # Local geocoding DB (312 name variants)
└── frontend/
    ├── Dockerfile
    ├── vite.config.js         # Proxies /api + /ws to :8000
    └── src/
        ├── App.jsx            # Root: layout, data fetching, WS wiring
        ├── components/        # DeckGLMap, EventLog, StatusBar, MapPopup, etc.
        ├── config/            # Layer config, region presets
        ├── hooks/             # useWebSocket, useEventStore
        ├── services/          # API fetch helpers
        └── utils/             # Supercluster wrapper
```

---

## Troubleshooting

**Backend crashes on startup**

Check `.env` for any integer fields that have comment text as their value:
```
TELEGRAM_API_ID=0   # not: TELEGRAM_API_ID= # comment
```

**ACLED returns 403 Access Denied**

Your account is authenticated (token is acquired) but doesn't have data API access yet. Log in at [acleddata.com](https://acleddata.com), go to your account dashboard, and request API data access. Approval is typically same-day.

**GDELT returns 429 Too Many Requests**

Normal on startup if the backend was restarted recently. GDELT rate-limits aggressive polling. The circuit breaker will recover automatically on the next cycle (~15 minutes).

**NGA agent fails / times out**

`msi.gs.mil` is geo-blocked outside the US. Set `ENABLE_NGA=false` in `.env`.

**UCDP returns 401 Unauthorized**

UCDP now requires an access token. Register at [ucdpapi.pcr.uu.se](https://ucdpapi.pcr.uu.se), then set `UCDP_ACCESS_TOKEN=your_token` in `.env` and restart the backend.

**Ollama translation not working**

Ensure Ollama is running on the host (not in Docker) and the model is pulled:
```bash
ollama serve       # if not running
ollama pull llama3.1:8b
```

**Frontend `vite: not found`**

```bash
cd frontend && npm install
```

**RSS XML parse errors in logs**

Harmless — `feedparser` handles malformed XML gracefully and skips bad entries. The WARNING log is informational only.
