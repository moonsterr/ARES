# Project ARES — Technical Documentation

Comprehensive file-by-file reference for every module in the codebase. Covers what each file does, which modules it imports, what its key functions/classes are, and how it connects to the rest of the system.

---

## Root Directory

### `docker-compose.yml`
- **Purpose**: Defines the full-stack Docker environment
- **Services**:
  - `postgres` — PostgreSQL 15 + PostGIS 3.4, port 5432, healthcheck enabled
  - `backend` — Python FastAPI app, port 8000, mounts `./backend` for hot-reload
- **Notes**: Frontend runs locally via `npm run dev`, not containerised

### `.env` / `.env.example`
- **Purpose**: All runtime secrets and feature flags loaded by `config.py` via pydantic-settings
- **Never committed** — `.gitignore` excludes `.env`; history was purged with `git filter-branch` after an accidental early commit

---

## Backend — `backend/`

### `config.py`
- **Module**: `pydantic_settings.BaseSettings`
- **Purpose**: Single source of truth for all configuration. Reads from `.env` file and environment variables. `extra="ignore"` silently discards unknown vars.
- **Key setting groups**:
  - **Database**: `DATABASE_URL`
  - **Ollama LLM**: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - **NASA FIRMS**: `FIRMS_MAP_KEY`
  - **ADSB.lol**: `ADSB_LOL_BASE_URL`
  - **RSS**: `RSS_FEEDS` (fallback list), `RSS_POLL_INTERVAL`
  - **GDELT**: `GDELT_BASE_URL`, `GDELT_POLL_INTERVAL`, `GDELT_MODE`, `GDELT_MAX_RECORDS`, `GDELT_QUERY`
  - **ACLED**: `ACLED_API_KEY`, `ACLED_EMAIL`, `ACLED_BASE_URL`, `ACLED_MAX_RECORDS`, `ACLED_POLL_INTERVAL`, `ACLED_RELIABILITY_ALPHA`
  - **UCDP**: `UCDP_BASE_URL`, `UCDP_POLL_INTERVAL`, `UCDP_MAX_RECORDS`, `UCDP_LOOKBACK_DAYS`, `UCDP_RELIABILITY_ALPHA`
  - **NGA**: `NGA_BASE_URL`, `NGA_POLL_INTERVAL`
  - **Feature flags**: `ENABLE_TELEGRAM`, `ENABLE_RSS`, `ENABLE_GDELT`, `ENABLE_ADSB`, `ENABLE_FIRMS`, `ENABLE_SENTINEL`, `ENABLE_WEBSDR`, `ENABLE_MARINE`, `ENABLE_ACLED`, `ENABLE_UCDP`, `ENABLE_NGA`
  - **Geocoding**: `NOMINATIM_USER_AGENT`, `GEOCODE_FUZZY_THRESHOLD`
  - **Logging**: `LOG_LEVEL`

### `main.py`
- **Modules**: `fastapi`, `asyncio`, `contextlib.asynccontextmanager`, `pathlib`, `json`
- **Purpose**: FastAPI application entry point. Manages agent lifecycle and exposes all REST + WebSocket endpoints.
- **Key functions**:
  - `lifespan(app)` — async context manager: calls `init_db()` on startup, spawns all enabled agent tasks via `asyncio.create_task()`, cancels them on shutdown
  - `ws_events(websocket)` — WebSocket at `/ws/events`; delegates to `WebSocketManager`
  - `get_events(limit, category)` — `GET /api/events`
  - `health()` — `GET /api/health` — lists all 11 agent enable states
  - `agent_status()` — `GET /api/agents/status` — detailed per-agent config
  - `get_infrastructure()` — `GET /api/infrastructure` — returns all 5 GeoJSON layers
  - `get_infrastructure_layer(layer)` — `GET /api/infrastructure/{layer}`
  - `get_acled_events(limit, category)` — `GET /api/acled-events`
  - `get_ucdp_events(limit, category)` — `GET /api/ucdp-events`
  - `get_nga_warnings(limit)` — `GET /api/nga-warnings`
  - `conflict_summary()` — `GET /api/conflict/summary`
  - `_load_infrastructure_file(filename)` — internal helper to load GeoJSON from `backend/data/`
- **Agents launched** (in order, gated by feature flags):
  `alpha_harvester`, `poll_rss`, `poll_gdelt`, `poll_adsb`, `poll_firms`, `run_sentinel_worker`, `run_websdr_monitor`, `poll_marine`, `poll_acled`, `poll_ucdp`, `poll_nga`

### `database.py`
- **Modules**: `asyncpg`, `logging`
- **Purpose**: PostgreSQL + PostGIS interface. Manages connection pool and schema.
- **Key functions**:
  - `init_db()` — creates asyncpg pool; applies DDL (events table with spatial index)
  - `close_db()` — closes pool on shutdown
  - `insert_event(intel, source)` — inserts a `ConflictIntel` row; returns `event_id`
  - `get_recent_events(limit, category)` — SELECT with optional category filter; returns list of dicts
  - `find_nearby_events(lat, lon, radius_m)` — PostGIS `ST_DWithin` spatial query
  - `promote_to_verified(event_id, hs_source, frp)` — sets `is_confirmed=True`, stores FIRMS metadata

### `websocket_manager.py`
- **Modules**: `fastapi.WebSocket`, `asyncio`, `json`
- **Purpose**: Fan-out broadcast hub. Maintains list of active WebSocket connections.
- **Key methods**:
  - `connect(ws)` / `disconnect(ws)` — add/remove clients
  - `broadcast_json(payload)` — serialise dict and send to all connected clients; silently removes dead connections
  - `connection_count` — property for health endpoint

---

## Backend Models — `backend/models/`

### `event.py`
- **Modules**: `pydantic`, `enum`
- **Purpose**: Core event schema. All intelligence events conform to `ConflictIntel`.
- **Key classes**:
  - `EventCategory(str, Enum)` — `air_alert`, `ground_strike`, `troop_movement`, `naval_event`, `explosion`, `casualty_report`, `unknown`
  - `LocationEntity` — `raw_text`, `normalized`, `lat`, `lon`, `confidence`
  - `ConflictIntel` — full model with: `raw_text`, `translation`, `category`, `confidence`, `source_language`, `is_confirmed`, `casualty_count`, `weapon_mentions`, `unit_mentions`, `locations`, `bel`, `pl`, `conflict_k`, `source_alpha`, `fusion_status`
  - `lat` / `lon` / `location_name` — computed properties from `locations[0]`

---

## Backend Intelligence — `backend/intelligence/`

### `categorizer.py`
- **Modules**: `re`
- **Purpose**: Fast regex-based event categorisation and entity extraction
- **Key functions**:
  - `categorize_message(text)` → `(EventCategory, float)` — returns category + confidence
  - `extract_casualty_count(text)` → `Optional[int]`
  - `extract_weapon_mentions(text)` → `list[str]`
  - `extract_unit_mentions(text)` → `list[str]`

### `geocoder.py`
- **Modules**: `rapidfuzz`, `httpx`, `json`, `logging`
- **Purpose**: Two-stage location resolution
- **Key functions**:
  - `lookup_local(text, threshold)` — fuzzy match against `mideast_military_bases.json`; returns `(name, lat, lon, confidence)` or `None`
  - `resolve_location(raw_text, normalized)` — calls `lookup_local` first, then Nominatim geocoding API; returns `(lat, lon)` or `None`

### `llm_pipeline.py`
- **Modules**: `httpx`, `fasttext`, `logging`, `asyncio`
- **Purpose**: Full NLP pipeline for text-based sources
- **Key functions**:
  - `detect_language(text)` → `str` — ISO 639-1 code via fasttext; returns `"en"` on fallback
  - `translate_to_english(text, source_lang)` → `str` — Ollama API call
  - `extract_entities_llm(text)` → `dict` — NER via Ollama; extracts locations, weapons, units
  - `process_message(raw_text, channel_name)` → `ConflictIntel` — full pipeline for Telegram
  - `process_rss_entry(raw_text, feed_url)` → `ConflictIntel` — RSS variant
  - `process_gdelt_entry(raw_text, title)` → `ConflictIntel` — GDELT variant

### `confidence.py`
- **Modules**: `math`
- **Purpose**: Dempster-Shafer Theory + PCR5 conflict redistribution
- **Key functions**:
  - `initial_bba(intel, alpha)` → `dict` — creates initial BBA from a single source with weight α; returns `{belief, plausibility, conflict_k}`
  - `combine_bbas(bba1, bba2)` → `dict` — PCR5 combination of two BBAs
  - `fuse_events(events)` → `ConflictIntel` — multi-source fusion

### `fusion.py`
- **Purpose**: Cross-source event correlation. Searches DB for nearby events within a time window, triggers PCR5 combination, promotes to VERIFIED when FIRMS hotspot matches.

---

## Backend Agents — `backend/agents/`

### `alpha_harvester.py` — Agent ALPHA
- **Modules**: `telethon`, `asyncio`
- **Purpose**: Monitors 16+ Telegram OSINT channels. Each message passes through `llm_pipeline.process_message()`.
- **Gate**: `ENABLE_TELEGRAM`

### `bravo_news.py` — Agent BRAVO-N
- **Modules**: `httpx`, `xml.etree.ElementTree`, `hashlib`, `json`, `pathlib`
- **Purpose**: RSS news harvester
- **Key functions**:
  - `_load_feeds()` — loads URLs + per-feed α weights from `backend/data/rss_feeds.json`; falls back to `settings.RSS_FEEDS` (3 hardcoded URLs) if file missing
  - `_parse_feed(xml_bytes, feed_url)` — parses RSS 2.0 and Atom; extracts `<geo:lat>/<geo:long>` and `<georss:point>` coordinates
  - `_process_entry(entry, feed_url, alpha_weights)` — dedup → LLM → geocoding → DST → DB insert → broadcast
  - `poll_rss()` — main loop; polls all feeds concurrently with `asyncio.gather`
- **Gate**: `ENABLE_RSS`
- **Dedup**: SHA-256 of `url + title`, TTL 48 hours

### `gdelt_fetcher.py` — Agent BRAVO-G
- **Modules**: `httpx`, `hashlib`
- **Purpose**: GDELT v2 Doc API news geo-event extractor
- **Key functions**:
  - `_fetch_gdelt(client)` — queries GDELT API with `GDELT_QUERY`, mode `artlist`
  - `_process_article(article)` — dedup → `process_gdelt_entry()` → geocoding → DST → DB insert → broadcast
  - `poll_gdelt()` — main loop, interval `GDELT_POLL_INTERVAL`
- **Gate**: `ENABLE_GDELT`
- **No API key required**

### `bravo_adsb.py` — Agent BRAVO-A
- **Modules**: `httpx`, `asyncio`
- **Purpose**: Military aircraft tracking via ADSB.lol v2 API
- **Polls two endpoints**: `/v2/mil` (global) + `/v2/point/{lat}/{lon}/{radius}` (regional)
- **Gate**: `ENABLE_ADSB`

### `bravo_firms.py` — Agent BRAVO-B
- **Modules**: `httpx`, `csv`
- **Purpose**: NASA FIRMS thermal hotspot ingestion. Calls `promote_to_verified()` on DB when a hotspot is within 10 km of an existing event.
- **Gate**: `ENABLE_FIRMS`

### `bravo_sentinel.py` — Agent BRAVO-C
- **Modules**: `httpx`, `asyncio`
- **Purpose**: Fetches Sentinel-2 imagery via Copernicus Dataspace API for verified events.
- **Gate**: `ENABLE_SENTINEL`

### `bravo_websdr.py` — Agent BRAVO-D
- **Purpose**: WebSDR HFGCS radio monitor. Currently a functional stub — logs but does not emit events.
- **Gate**: `ENABLE_WEBSDR`

### `bravo_marine.py` — Agent BRAVO-E
- **Modules**: `httpx`
- **Purpose**: MarineTraffic AIS vessel tracking (Red Sea, Persian Gulf, Mediterranean).
- **Gate**: `ENABLE_MARINE`; requires `MARINETRAFFIC_API_KEY`

### `acled_fetcher.py` — Agent CHARLIE-A
- **Modules**: `httpx`, `hashlib`, `urllib.parse`
- **Purpose**: Fetches armed conflict events from the ACLED REST API
- **Key functions**:
  - `_fetch_acled(client)` — requests fields `event_id_cnty|event_date|event_type|sub_event_type|country|location|latitude|longitude|fatalities|actor1|actor2|notes|source`; requires `ACLED_API_KEY` + `ACLED_EMAIL` in params
  - `_map_category(event_type, sub_event_type)` → `EventCategory` — maps ACLED taxonomy to ARES categories
  - `_process_event(ev)` — dedup by `event_id_cnty` → build `ConflictIntel` (confidence 0.85, DST α = `ACLED_RELIABILITY_ALPHA`) → DB insert → broadcast
  - `poll_acled()` — main loop; skips silently if API key not set
- **Circuit breaker**: `_cb = CircuitBreaker("acled", failure_threshold=3, recovery_timeout=300, cache_ttl=1800)`
- **Gate**: `ENABLE_ACLED`; also checks `ACLED_API_KEY` at startup
- **Countries covered**: ISR, PSE, LBN, SYR, IRQ, IRN, YEM, SAU, ARE, KWT, BHR, QAT, OMN, JOR, EGY, LBY, TUN, DZA, MAR, SDN, ETH, SOM, DJI, ERI, TUR, ARM, AZE, GEO, UKR, RUS

### `ucdp_fetcher.py` — Agent CHARLIE-B
- **Modules**: `httpx`, `hashlib`, `datetime`
- **Purpose**: Fetches georeferenced conflict events from the UCDP GED REST API
- **Key functions**:
  - `_fetch_ucdp(client)` — queries `UCDP_BASE_URL` with `StartDate` (now minus `UCDP_LOOKBACK_DAYS`), `pagesize`; returns `data["Result"]`
  - `_process_event(ev)` — maps `type_of_violence` (1=state, 2=non-state, 3=one-sided) to `EventCategory`; sums `deaths_civilians + deaths_a + deaths_b`; DST α = `UCDP_RELIABILITY_ALPHA`
  - `poll_ucdp()` — main loop, interval `UCDP_POLL_INTERVAL`
- **Circuit breaker**: `_cb = CircuitBreaker("ucdp", failure_threshold=3, recovery_timeout=600, cache_ttl=3600)`
- **Gate**: `ENABLE_UCDP`
- **No API key required**

### `nga_warnings.py` — Agent CHARLIE-C
- **Modules**: `httpx`, `re`, `hashlib`
- **Purpose**: Fetches NGA NAVAREA maritime broadcast warnings
- **Key functions**:
  - `_fetch_warnings(client)` — `GET NGA_BASE_URL?output=json&status=active`; handles both `list` and `{"broadcastWarn": [...]}` response shapes
  - `_extract_coords(text)` → `Optional[tuple[float, float]]` — regex extracts first DM coordinate pair (`°`, `'`, `N/S/E/W`) from warning text
  - `_process_warning(w)` — dedup by `msgNum`; always `EventCategory.naval_event`; confidence 0.75; DST α = 0.82
  - `poll_nga()` — main loop, interval `NGA_POLL_INTERVAL`
- **Circuit breaker**: `_cb = CircuitBreaker("nga", failure_threshold=3, recovery_timeout=300, cache_ttl=1800)`
- **Gate**: `ENABLE_NGA`
- **Regions polled**: NAVAREA I, III, IX, X, XI

---

## Backend Services — `backend/services/`

### `conflict_service.py`
- **Modules**: `database.get_recent_events`
- **Purpose**: Unified query layer over `get_recent_events()` for REST endpoints
- **Key functions**:
  - `get_conflict_events(limit, source, category, min_confidence, verified_only)` — filters events post-DB-fetch; source matching strips prefix (e.g. `"rss:aljazeera.com"` matches `source="rss"`)
  - `get_conflict_summary()` — aggregates counts by source key and category from last 500 events; returns `{total_events, verified_events, by_source, by_category}`

---

## Backend Utils — `backend/utils/`

### `circuit_breaker.py`
- **Modules**: `asyncio`, `enum`, `time`, `functools`, `logging`
- **Purpose**: Generic async circuit breaker wrapping external API calls
- **States**: `CircuitState.CLOSED` → `OPEN` → `HALF_OPEN` → `CLOSED`
- **Key class**: `CircuitBreaker(name, failure_threshold, recovery_timeout, cache_ttl)`
  - `call(fn)` → wrapped async callable — increments failure count on exception; trips to OPEN after `failure_threshold` failures; serves cached response while OPEN; resets on first successful HALF_OPEN call
  - `state` property — current `CircuitState`
  - Cache keyed by function + args; expired after `cache_ttl` seconds

---

## Backend Data Files — `backend/data/`

### `rss_feeds.json`
- **Purpose**: Curated list of 170+ RSS feeds with metadata
- **Schema per entry**: `{url, lang, region, reliability, category}`
- **`reliability`**: float 0.0–1.0, used as DST α weight in `bravo_news.py`
- **Regions**: ME, IL, TR, IR, UA, global, and others
- **Categories**: news, wire, military, analysis, state

### `cables.geojson`
- **Format**: GeoJSON FeatureCollection, LineString features
- **Properties per feature**: `name`, `owners`, `length_km`, `status`

### `pipelines.geojson`
- **Format**: GeoJSON FeatureCollection, LineString features
- **Properties per feature**: `name`, `type` (oil/gas), `country`, `status`

### `ports.geojson`
- **Format**: GeoJSON FeatureCollection, Point features (~29 ports)
- **Properties per feature**: `name`, `country`, `type`

### `military_bases.geojson`
- **Format**: GeoJSON FeatureCollection, Point features (63 installations)
- **Generated from** `mideast_military_bases.json` via Python one-liner
- **Properties per feature**: `name`, `country`, `type`, `operator`

### `nuclear_sites.geojson`
- **Format**: GeoJSON FeatureCollection, Point features (15 facilities)
- **Source**: Open-source IAEA, NTI, and academic publications
- **Properties per feature**: `name`, `country`, `type` (enrichment / power_plant / reactor_research / plutonium_production / military_suspected / nuclear_storage / disaster_site / research), `status`, `operator`, `notes`
- **Sites include**: Natanz, Fordow, Bushehr, Isfahan, Arak, Parchin (Iran); Dimona, Soreq (Israel); Deir ez-Zor (Syria, destroyed); Barakah (UAE); Incirlik NATO storage (Turkey); Zaporizhzhia, Chernobyl (Ukraine)

### `mideast_military_bases.json`
- **Purpose**: Local geocoding database for `geocoder.py`; ~63 sites with name variants, lat/lon, confidence scores
- **Used by**: `lookup_local()` in `geocoder.py`

### `channel_reliability.json`
- **Purpose**: Per-channel reliability weights for Telegram agent (ALPHA)

---

## Frontend — `frontend/`

### `package.json`
- **Key dependencies**:
  - `react@^18.3.1`, `react-dom@^18.3.1`
  - `deck.gl@^9.2.10` — WebGL map layers
  - `@deck.gl/aggregation-layers` — HeatmapLayer
  - `maplibre-gl@^5.19.0` — map rendering, dark basemap
  - `supercluster@^8.0.1` — spatial marker clustering
  - `vite@^6.3.5` — build tool
- **Removed**: `cesium`, `vite-plugin-cesium`

### `vite.config.js`
- **Plugins**: `@vitejs/plugin-react` only — `vite-plugin-cesium` removed

---

## Frontend Components — `frontend/src/components/`

### `DeckGLMap.jsx`
- **Modules**: `deck.gl` (DeckGL, ScatterplotLayer, IconLayer, PathLayer), `@deck.gl/aggregation-layers` (HeatmapLayer), `maplibre-gl`, `react`
- **Purpose**: Main 2D map component. Renders all Deck.gl layers over a MapLibre dark basemap.
- **Layers rendered**:
  - `ScatterplotLayer` — conflict events (colour-coded by category + conflict-K)
  - `HeatmapLayer` — event density heatmap
  - `IconLayer` — aircraft, vessels, military bases, ports
  - `PathLayer` — submarine cables, pipelines
  - `ScatterplotLayer` — NASA FIRMS hotspots
- **Props**: `layerVisibility`, `events`, `aircraft`, `vessels`, `infrastructure`, `onEventClick`

### `MapPopup.jsx`
- **Purpose**: Floating info popup shown on layer click
- **Displays**: event details (category, confidence, Bel/Pl, source), aircraft fields (ICAO, type, altitude, heading), vessel fields (MMSI, flag, speed), infrastructure metadata

### `MapLegend.jsx`
- **Purpose**: Collapsible overlay in the bottom-left corner
- **Sections**: Event category colour dots, infrastructure layer symbols, data source list with α-weighted credibility hint
- **State**: `collapsed` (useState) — click header to toggle
- **Styling**: Inline styles matching ARES dark theme; glassmorphism background

### `EventLog.jsx`
- **Purpose**: Intelligence feed sidebar showing recent events in reverse-chronological order

### `EventCard.jsx`
- **Purpose**: Single event row in the sidebar; shows category badge, confidence bar, location, source, Bel/Pl interval

### `StatusBar.jsx`
- **Purpose**: Top status bar — brand name, WebSocket status (LIVE / CONNECTING / RECONNECTING), event count, ALPHA/BRAVO agent indicators

---

## Frontend Hooks — `frontend/src/hooks/`

### `useWebSocket.js`
- **Purpose**: Manages WebSocket connection to `/ws/events` with exponential back-off reconnect
- **Returns**: `{ status, lastMessage }` — status is `"open"` / `"connecting"` / `"closed"` / `"error"`

### `useEventStore.js`
- **Purpose**: In-memory state store for all map and event data
- **State**:
  - `events` — array of conflict events
  - `aircraft` — array of military aircraft positions
  - `vessels` — array of naval vessel positions
  - `hotspots` — array of FIRMS thermal detections
  - `infrastructure` — all GeoJSON infrastructure layers
  - `layerVisibility` — `{layerId: boolean}` map
- **Key functions**:
  - `addEvent(event)` / `addAircraft(ac)` / `addVessel(v)` / `addHotspot(hs)`
  - `toggleLayer(layerId)` — flip visibility boolean
  - `setLayerVisible(layerId, visible)` — set specific value
  - `setInfrastructureData(data)` — store infrastructure GeoJSON from API

---

## Frontend Config — `frontend/src/config/`

### `mapLayers.js`
- **Exports**:
  - `MAP_STYLE` — MapLibre CARTO dark-matter style URL
  - `INITIAL_VIEW_STATE` — `{longitude: 42.5, latitude: 30.0, zoom: 4}`
  - `MIDDLE_EAST_BOUNDS` — `{west: 25, south: 14, east: 65, north: 42}`
  - `LAYER_CONFIG` — per-layer rendering config (type, colour callbacks, radius, icon atlas)
  - `LAYER_ORDER` — render order array (heatmap bottom, vessels top)

### `regions.js`
- **Purpose**: Named map view-states for region-jump controls
- **Exports**:
  - `REGIONS` — object mapping region key → `{label, longitude, latitude, zoom, pitch, bearing}`
  - `REGION_LIST` — ordered array of region keys (most relevant first)
  - `DEFAULT_REGION` — `'middle_east'`
- **Regions**: `middle_east`, `levant`, `gaza`, `persian_gulf`, `red_sea`, `yemen`, `iran`, `eastern_med`, `north_africa`, `horn_of_africa`, `ukraine`, `caucasus`

---

## Frontend Services — `frontend/src/services/`

### `infrastructure.js`
- **Exports**:
  - `fetchInfrastructure()` → all 5 layers (`cables`, `pipelines`, `ports`, `military_bases`, `nuclear_sites`)
  - `fetchInfrastructureLayer(layer)` → single named layer

### `acled.js`
- **Exports**:
  - `fetchAcledEvents({limit, category})` → array of ACLED-sourced events from `/api/acled-events`

### `ucdp.js`
- **Exports**:
  - `fetchUcdpEvents({limit, category})` → array from `/api/ucdp-events`
  - `fetchNgaWarnings(limit)` → array from `/api/nga-warnings`
  - `fetchConflictSummary()` → `{total_events, verified_events, by_source, by_category}` from `/api/conflict/summary`

All services read `VITE_API_URL` env var and fall back to `http://localhost:8000`.

---

## Frontend Utils — `frontend/src/utils/`

### `clustering.js`
- **Modules**: `supercluster`
- **Purpose**: Spatial marker clustering for conflict event dots at low zoom levels
- **Exports**:
  - `buildIndex(events, options)` → `Supercluster` — converts ARES event array to GeoJSON features and loads index
  - `getClusters(index, viewport)` → array of `{type: 'cluster', count, lat, lon, clusterId}` or `{type: 'event', data: <event>}`
  - `expandCluster(index, clusterId)` → children array
  - `getClusterExpansionZoom(index, clusterId)` → zoom level at which cluster splits
- **Defaults**: `radius=60`, `maxZoom=10`, `minPoints=3`

---

## Data Flow — Summary Diagrams

### Text-based sources (Telegram / RSS / GDELT)
```
Raw message arrives
    ↓
bravo_news / gdelt_fetcher / alpha_harvester
    ↓
llm_pipeline.py
  detect_language() → translate_to_english() → extract_entities_llm()
    ↓
categorizer.py → EventCategory
    ↓
geocoder.py → (lat, lon)
    ↓
confidence.py → initial_bba(intel, α) → {bel, pl, conflict_k}
    ↓
database.insert_event()
    ↓
websocket_manager.broadcast_json()
    ↓
fusion.py → cross-source correlation check
    ↓
bravo_firms.py match? → promote_to_verified() → bravo_sentinel.py
```

### Structured sources (ACLED / UCDP / NGA)
```
API response arrives
    ↓
acled_fetcher / ucdp_fetcher / nga_warnings
  circuit_breaker.call(fetch_fn)
    ↓
_process_event() / _process_warning()
  dedup check (SHA-256)
    ↓
Build ConflictIntel directly (no LLM — coords already present)
    ↓
confidence.py → initial_bba(intel, α)
    ↓
database.insert_event()
    ↓
websocket_manager.broadcast_json()
```

### Aircraft / vessels
```
ADSB.lol / MarineTraffic API
    ↓
bravo_adsb / bravo_marine
    ↓
database.upsert_aircraft() / upsert_vessel()
    ↓
websocket_manager.broadcast_json()
```

---

## Key Backend Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `telethon` | Telegram MTProto client |
| `asyncpg` | Async PostgreSQL driver |
| `httpx` | Async HTTP client (all external API calls) |
| `pydantic` / `pydantic-settings` | Data validation + config |
| `fasttext-wheel` | Language detection |
| `rapidfuzz` | Fuzzy geocoder string matching |

## Key Frontend Dependencies

| Package | Purpose |
|---|---|
| `react` | UI framework |
| `deck.gl` | WebGL 2D map layers |
| `@deck.gl/aggregation-layers` | HeatmapLayer |
| `maplibre-gl` | Map rendering + basemap |
| `supercluster` | Spatial marker clustering |
| `vite` | Build tool |

---

*Project ARES v3.0 — Technical Documentation — 2026-03-04*
*Agents: ALPHA + BRAVO×7 + CHARLIE×3 | Circuit breaker | 170+ RSS feeds | 5 infrastructure layers | 12 map regions*
