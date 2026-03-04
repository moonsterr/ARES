# Project ARES — System Overview

**Autonomous Reconnaissance & Event Synthesis**
Real-time multi-source intelligence fusion dashboard for the Middle East conflict space.

---

## What It Does

ARES ingests raw signals from eleven independent data sources, fuses conflicting reports using a mathematically rigorous evidential reasoning engine, and streams the results to a 2D map dashboard in real time. The system answers one question: *given that multiple sources are reporting different things, what actually happened, where, and how confident should we be?*

---

## Architecture at a Glance

```
DATA SOURCES              FUSION ENGINE                PRESENTATION
────────────             ─────────────                ────────────
Telegram (16 ch)  ─┐
RSS (170+ feeds)  ─┤
GDELT News        ─┤   FastAPI Backend                React + Deck.gl
ACLED             ─┼─► LLM Pipeline   ─► PCR5  ─►   2D Map (MapLibre)
UCDP              ─┤   (Ollama 8B)       Fusion       Event Log Sidebar
NGA NAVAREA       ─┤                     Engine        Layer Toggles
ADSB.lol (free)  ─┤                                   MapLegend
NASA FIRMS        ─┼─►  PostgreSQL + PostGIS          Region Jump
Sentinel-2        ─┤    (spatial event store)
MarineTraffic     ─┘          │
                         WebSocket broadcast
                         (/ws/events)
```

---

## Agent Roster

### ALPHA — Telegram Harvester (optional)
Monitors 16+ public Telegram channels across all sides of the conflict using Telethon. Requires manual Telegram API credentials and channel membership.

### BRAVO-N — RSS News Harvester
Polls **170+ curated RSS feeds** (loaded from `backend/data/rss_feeds.json`) every 5 minutes. Each feed has a per-source DST reliability weight (α). Covers Al Jazeera, Reuters, BBC, AP, Times of Israel, Arab News, Iran state media, defence outlets, and many more. Deduplication via SHA-256 of URL + title.

### BRAVO-G — GDELT News Geo-Event Extractor
Polls GDELT v2 Doc API every 15 minutes for conflict-related articles. Uses the Ollama LLM to extract geographic locations from headlines. No API key required.

### BRAVO-A — ADSB.lol Military Aircraft
Polls every 10 seconds — merges global `/mil` feed with a 250 nm point-radius feed centred on Tel Aviv. Deduplicates by ICAO hex. No API key required.

### BRAVO-B — NASA FIRMS Thermal Sensor
Polls every 5 minutes for thermal hotspots. Used as ground-truth verification — a FIRMS match within 10 km promotes an event from *unverified* to **VERIFIED** and queues Sentinel-2 imagery.

### BRAVO-C — Copernicus Sentinel-2
Fetches post-strike satellite imagery for events that have been promoted to VERIFIED by FIRMS. Requires free Copernicus account.

### BRAVO-D — WebSDR HFGCS Radio (stub)
Monitors HF Global Communications System frequencies for Emergency Action Messages. Currently a stub.

### BRAVO-E — MarineTraffic AIS (optional)
Polls for naval vessels in the Red Sea, Persian Gulf, and Mediterranean. Requires a commercial MarineTraffic API key.

### CHARLIE-A — ACLED Conflict Events (optional)
Fetches real-time armed conflict events from the Armed Conflict Location & Event Data Project API. 170+ countries, with lat/lon, actors, and fatality counts. DST α = 0.80 (high reliability — cross-referenced source). Requires free ACLED registration. Disabled by default.

### CHARLIE-B — UCDP GED Events
Fetches from the Uppsala Conflict Data Program GED REST API. Academically rigorous — lower velocity than ACLED but higher precision. DST α = 0.78. No API key required. Polls every 2 hours with a 30-day lookback.

### CHARLIE-C — NGA NAVAREA Maritime Warnings
Fetches official US government NAVAREA broadcast warnings from the NGA Maritime Safety Information portal. Covers Persian Gulf (NAVAREA IX), Arabian Sea (X), Indian Ocean (XI), and others. Extracts coordinates from warning text via regex. No API key required. Polls every 30 minutes.

---

## Intelligence Processing Pipeline

Every text-based message (Telegram / RSS / GDELT) passes through:

1. **Language detection** — fasttext (<5ms); falls back to English if model not present
2. **Translation** — Ollama llama3.1:8b translates Hebrew/Arabic/Persian to English
3. **Categorization** — Regex triage assigns `EventCategory`
4. **Entity extraction** — LLM NER pulls location names, weapon systems, military units
5. **Geocoding** — local military DB (rapidfuzz fuzzy match) → Nominatim fallback
6. **DST initialisation** — source-weighted Basic Belief Assignment

Structured sources (ACLED, UCDP, NGA) skip the LLM pipeline — they arrive with coordinates and structured fields already.

---

## Confidence Engine — Dempster-Shafer PCR5

The core mathematical innovation. When multiple sources report the same event from different locations:

- Each source gets a reliability weight **α** (configured per agent)
- Each report is converted to a Basic Belief Assignment (BBA): `{θ: α, Θ: 1−α}`
- BBAs are combined using **PCR5** (Proportional Conflict Redistribution)
- **K < 0.3** → sources agree → emit fused coordinate
- **K 0.3–0.5** → uncertain → display both candidates
- **K ≥ 0.5** → conflict alert → refuse to fuse, flag for human review

Every event stores a `[Bel, Pl]` interval — displayed as an uncertainty bar in the event log.

### Source reliability weights (α)

| Source | α | Rationale |
|---|---|---|
| NGA NAVAREA | 0.82 | Official government publication |
| Reuters / BBC | 0.82–0.85 | Major wire services |
| ACLED | 0.80 | Cross-referenced conflict database |
| UCDP | 0.78 | Academic, peer-reviewed |
| Al Jazeera | 0.72 | Reputable ME regional outlet |
| Jerusalem Post | 0.70 | Established Israeli outlet |
| GDELT | 0.65 | Aggregator — varies by source article |
| Iran state media | 0.45 | State-controlled, lower credibility |

---

## Circuit Breaker

All external API calls in CHARLIE-A/B/C and BRAVO-G are wrapped in `backend/utils/circuit_breaker.py`:

- **Closed** (normal) → calls pass through
- **Open** (3 consecutive failures) → calls blocked; last successful response served from cache
- **Half-open** (after recovery timeout) → single trial call; if it succeeds, resets to Closed
- Cache TTL prevents stale data from persisting indefinitely

---

## Infrastructure Overlays

Static GeoJSON layers served from `backend/data/`:

| Layer | File | Contents |
|---|---|---|
| Submarine cables | `cables.geojson` | Fiber optic cable routes |
| Oil/gas pipelines | `pipelines.geojson` | Regional energy infrastructure |
| Shipping ports | `ports.geojson` | Major ports with name/country |
| Military bases | `military_bases.geojson` | 63 installations |
| Nuclear sites | `nuclear_sites.geojson` | 15 verified facilities (IAEA/NTI sources) |

All layers are served by `/api/infrastructure` and individually by `/api/infrastructure/{layer}`.

---

## REST API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/events` | Recent conflict events (limit, category filters) |
| `GET /api/acled-events` | ACLED-sourced events only |
| `GET /api/ucdp-events` | UCDP-sourced events only |
| `GET /api/nga-warnings` | NGA NAVAREA maritime warnings |
| `GET /api/conflict/summary` | Event counts by source and category |
| `GET /api/infrastructure` | All infrastructure GeoJSON layers |
| `GET /api/infrastructure/{layer}` | Single infrastructure layer |
| `GET /api/health` | Agent enable/disable status |
| `GET /api/agents/status` | Detailed per-agent config and status |
| `WS /ws/events` | Real-time event broadcast |

---

## Frontend

- **Deck.gl + MapLibre GL** — Dark CARTO basemap, Middle East default view
- **Layer system** — Toggle 9+ layers: conflicts, heatmap, aircraft, vessels, cables, pipelines, military bases, ports, hotspots
- **MapLegend** — Collapsible legend with event category colours, infrastructure symbols, and source list
- **Region jump** — 12 named regions (`regions.js`): Middle East, Levant, Gaza, Persian Gulf, Red Sea, Yemen, Iran, Eastern Mediterranean, North Africa, Horn of Africa, Ukraine, Caucasus
- **Supercluster** — Marker clustering at low zoom (wrapper in `src/utils/clustering.js`)
- **Intelligence feed sidebar** — Glassmorphism event log
- **WebSocket streaming** — Sub-second latency via `/ws/events`

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend framework | React 18 + Vite 5 |
| 2D map | Deck.gl 9.x + MapLibre GL |
| Marker clustering | Supercluster 8.x |
| Styling | Vanilla CSS, glassmorphism |
| Backend | Python 3.12, FastAPI |
| ASGI server | Uvicorn |
| Telegram client | Telethon |
| Database | PostgreSQL 15 + PostGIS 3.4 |
| DB driver | asyncpg (fully async) |
| HTTP client | httpx (async) |
| Local LLM | Ollama llama3.1:8b |
| Language detection | fasttext |
| Infrastructure | Docker Compose 2.x |

---

## Known Limitations

- **Ollama LLM speed** on CPU-only hardware: ~30 seconds per translation. High message volume may cause queue buildup.
- **Telegram** requires joining channels manually from your registered account.
- **MarineTraffic** requires a commercial API key.
- **ACLED** has ~2-week lag on some regions; real-time coverage varies by country.
- **α weights** are heuristic estimates — not yet auto-calibrated from historical accuracy.
- **Circuit breakers** use in-process state; a backend restart resets all breakers to Closed.

---

*Project ARES v3.0 — 2026-03-04 — 11 agents: ALPHA + BRAVO ×7 + CHARLIE ×3*
