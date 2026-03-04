# Project ARES - Technical Documentation

This document provides a comprehensive technical explanation of every file in the codebase, including what modules/APIs it uses, what functions do what, and where each file is used elsewhere in the project.

---

## Root Directory Files

### `docker-compose.yml`
- **Purpose**: Defines the full stack Docker environment
- **Services**:
  - `postgres`: PostgreSQL 15 + PostGIS 3.4 (port 5432)
  - `backend`: Python FastAPI application (port 8000)
  - `frontend`: React + Vite dev server (port 5173)
- **Dependencies**: Uses environment variables from `.env`, mounts volumes for hot-reload

### `.env.example`
- **Purpose**: Template for all required environment variables

---

## Backend (`/backend`)

### `config.py`
- **Purpose**: Centralized configuration management using Pydantic Settings
- **Key Settings**:
  - Database: `DATABASE_URL`
  - Ollama: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - NASA FIRMS: `FIRMS_MAP_KEY`
  - ADSB.lol: `ADSB_LOL_BASE_URL`
  - GDELT: `GDELT_BASE_URL`, `GDELT_POLL_INTERVAL`, `GDELT_QUERY`
  - Feature flags: `ENABLE_TELEGRAM`, `ENABLE_RSS`, `ENABLE_GDELT`, `ENABLE_ADSB`, `ENABLE_FIRMS`, `ENABLE_SENTINEL`, `ENABLE_WEBSDR`, `ENABLE_MARINE`

### `main.py`
- **Purpose**: FastAPI application entry point with lifespan management
- **Key Functions**:
  - `lifespan()`: Async context manager - initializes DB on startup, launches all agents
  - `ws_events()`: WebSocket endpoint at `/ws/events`
  - `get_events()`: REST endpoint at `/api/events`
  - `health()`: Health check at `/api/health`
  - `get_infrastructure()`: Returns infrastructure GeoJSON layers
- **Agents Launched**: alpha_harvester, poll_rss, poll_gdelt, poll_adsb, poll_firms, run_sentinel_worker, run_websdr_monitor, poll_marine

### `database.py`
- **Purpose**: PostgreSQL + PostGIS database interface using asyncpg
- **Key Functions**:
  - `init_db()`: Creates connection pool and applies schema
  - `insert_event(intel, source)`: Inserts ConflictIntel to events table
  - `find_nearby_events(lat, lon, radius_m)`: Spatial query
  - `promote_to_verified(event_id, hs_source, frp)`: Marks event as verified by FIRMS

### `websocket_manager.py`
- **Purpose**: Manages WebSocket connections for real-time frontend updates

---

## Backend Models (`/backend/models`)

### `event.py`
- **Purpose**: Core event schema - all intelligence events conform to this model
- **Key Classes**:
  - `EventCategory(str, Enum)`: air_alert, ground_strike, troop_movement, naval_event, explosion, casualty_report, unknown
  - `ConflictIntel`: Main model with category, confidence, translation, locations, weapons, units, casualties, DST fields

---

## Intelligence Processing (`/backend/intelligence`)

### `categorizer.py`
- **Purpose**: Fast regex-based event categorization
- **Key Functions**:
  - `categorize_message(text)`: Returns (EventCategory, confidence_score)
  - `extract_casualty_count(text)`, `extract_weapon_mentions(text)`, `extract_unit_mentions(text)`

### `geocoder.py`
- **Purpose**: Two-stage location resolution
- **Key Functions**:
  - `lookup_local(text_fragment, threshold)`: Fuzzy match against local military base DB
  - `resolve_location(raw_text, normalized)`: Main entry point

### `llm_pipeline.py`
- **Purpose**: Complete NLP pipeline for Telegram/RSS/GDELT messages
- **Key Functions**:
  - `detect_language(text)`: Uses fasttext
  - `translate_to_english(text, source_lang)`: Ollama API call
  - `extract_entities_llm(translated_text)`: Ollama NER
  - `process_message(raw_text, channel_name)`: Main pipeline for Telegram
  - `process_rss_entry(raw_text, feed_url)`: RSS variant
  - `process_gdelt_entry(raw_text, title)`: **NEW** - GDELT variant

### `confidence.py`
- **Purpose**: Dempster-Shafer Theory + PCR5 fusion confidence engine

### `fusion.py`
- **Purpose**: Cross-source event correlation and fusion

---

## Agents (`/backend/agents`)

### `alpha_harvester.py`
- **Purpose**: Telegram channel monitoring using Telethon

### `bravo_news.py`
- **Purpose**: RSS News Harvester
- **Features**: SHA-256 deduplication, geo-tag extraction, per-feed source labelling

### `gdelt_fetcher.py` **NEW**
- **Purpose**: GDELT v2 News Geo-Event Extractor
- **Key Functions**:
  - `poll_gdelt()`: Main polling loop (every 15 minutes)
  - `_fetch_gdelt(client)`: Fetches articles from GDELT API
  - `_process_article(article)`: Full pipeline: dedup → LLM → geocoding → DB insert → broadcast
- **Config**: `GDELT_QUERY`, `GDELT_MAX_RECORDS`, `GDELT_MODE`

### `bravo_adsb.py`
- **Purpose**: Military aircraft tracking via ADSB.lol API

### `bravo_firms.py`
- **Purpose**: NASA FIRMS thermal hotspot ingestion for fusion validation

### `bravo_sentinel.py`
- **Purpose**: Fetches Sentinel-2 satellite imagery for verified events

### `bravo_websdr.py`
- **Purpose**: WebSDR HFGCS radio monitoring (stub)

### `bravo_marine.py`
- **Purpose**: MarineTraffic AIS vessel tracking

---

## Frontend (`/frontend`)

### `App.jsx`
- **Purpose**: Root React component - layout orchestration
- **Key Components**:
  - `DeckGLMap`: **NEW** - Deck.gl 2D map replacing CesiumJS
  - `EventLog`: Intelligence feed sidebar
  - `StatusBar`: Connection status
- **State**:
  - `layerVisibility`: Toggle state for each map layer
  - `selectedEvent`: Currently selected event

### `vite.config.js`
- **Purpose**: Vite build configuration
- **Plugins**: `@vitejs/plugin-react`
- **Note**: Removed `vite-plugin-cesium` - CesiumJS no longer used

### `package.json`
- **Dependencies**:
  - `deck.gl@^9.2.10` - **NEW**
  - `maplibre-gl@^5.19.0` - **NEW**
  - `supercluster@^8.0.1` - **NEW**
  - `react@^18.3.1`, `react-dom@^18.3.1`
- **Removed**: `cesium`, `vite-plugin-cesium`

---

## Frontend Components (`/frontend/src/components`)

### `DeckGLMap.jsx` **NEW**
- **Purpose**: Deck.gl 2D map rendering with MapLibre
- **Key Features**:
  - Multiple layer types: ScatterplotLayer, IconLayer, PathLayer, HeatmapLayer
  - Layer visibility toggles
  - Click popups for all layers
  - Integration with useEventStore
- **Layers**:
  - Conflicts (ScatterplotLayer)
  - Aircraft (IconLayer)
  - Vessels (IconLayer)
  - Hotspots (ScatterplotLayer)
  - Heatmap (HeatmapLayer)
  - Cables (PathLayer)
  - Pipelines (PathLayer)
  - Military Bases (IconLayer)
  - Ports (IconLayer)

### `MapPopup.jsx` **NEW**
- **Purpose**: Click popup for map entity details
- **Displays**: Event info, aircraft details, vessel details, infrastructure details

### `MapContainer.jsx` (legacy)
- **Purpose**: Old CesiumJS 3D globe - still present but not used

### `EventLog.jsx`
- **Purpose**: Intelligence feed sidebar

### `EventCard.jsx`
- **Purpose**: Individual event display in sidebar

### `StatusBar.jsx`
- **Purpose**: Top status bar with connection info

---

## Frontend Hooks (`/frontend/src/hooks`)

### `useWebSocket.js`
- **Purpose**: Manages WebSocket connection with auto-reconnect

### `useEventStore.js` **UPDATED**
- **Purpose**: In-memory event state management
- **New State**:
  - `layerVisibility`: Object mapping layer IDs to boolean
  - `infrastructure`: Infrastructure GeoJSON data
- **New Functions**:
  - `toggleLayer(layerId)`: Toggle a layer's visibility
  - `setLayerVisible(layerId, visible)`: Set specific visibility
  - `setInfrastructureData(data)`: Store infrastructure GeoJSON

---

## Frontend Config (`/frontend/src/config`)

### `mapLayers.js` **NEW**
- **Purpose**: Layer definitions and configuration
- **Exports**:
  - `MAP_STYLE`: MapLibre dark style URL
  - `INITIAL_VIEW_STATE`: Default map position (Middle East)
  - `LAYER_CONFIG`: Configuration for each layer type
  - `LAYER_ORDER`: Rendering order of layers

---

## Frontend Services (`/frontend/src/services`)

### `infrastructure.js` **NEW**
- **Purpose**: Fetch infrastructure GeoJSON from backend
- **Functions**:
  - `fetchInfrastructure()`: Fetch all layers
  - `fetchInfrastructureLayer(layer)`: Fetch specific layer

---

## Backend Data Files (`/backend/data`)

### `cables.geojson` **NEW**
- **Purpose**: Submarine cable routes
- **Format**: GeoJSON LineString features

### `pipelines.geojson` **NEW**
- **Purpose**: Oil and gas pipelines
- **Format**: GeoJSON LineString features with type property (oil/gas)

### `ports.geojson` **NEW**
- **Purpose**: Major Middle East shipping ports
- **Format**: GeoJSON Point features (~29 ports)

### `military_bases.geojson` **NEW**
- **Purpose**: Military base locations
- **Format**: GeoJSON Point features (63 bases converted from JSON)

### `mideast_military_bases.json`
- **Purpose**: Local geocoding database (~63 sites)

---

## Summary: Data Flow

```
Telegram/RSS/GDELT message
    ↓
llm_pipeline.py (language, translation, NER)
    ↓
categorizer.py (regex categorization)
    ↓
geocoder.py (location resolution)
    ↓
confidence.py (initial BBA)
    ↓
database.py (insert_event)
    ↓
websocket_manager.py (broadcast)
    ↓
fusion.py (correlation check)
    ↓
bravo_firms.py (promote to VERIFIED)
    ↓
bravo_sentinel.py (attach imagery)
```

```
ADSB.lol API
    ↓
bravo_adsb.py (poll every 10s)
    ↓
database.py (upsert_aircraft)
    ↓
websocket_manager.py (broadcast sweep)

NASA FIRMS API
    ↓
bravo_firms.py (poll every 5 min)
    ↓
database.py (insert_hotspot)
    ↓
Fusion validation → promote_to_verified
```

```
GDELT v2 API (NEW)
    ↓
gdelt_fetcher.py (poll every 15 min)
    ↓
llm_pipeline.py (process_gdelt_entry)
    ↓
geocoder.py (location resolution)
    ↓
confidence.py (initial BBA)
    ↓
database.py (insert_event)
    ↓
websocket_manager.py (broadcast)
```

---

## Key Dependencies

### Backend
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **telethon**: Telegram client
- **asyncpg**: Async PostgreSQL driver
- **httpx**: Async HTTP client
- **pydantic**: Data validation
- **fasttext-wheel**: Language detection
- **rapidfuzz**: Fuzzy string matching

### Frontend
- **react**: UI framework
- **deck.gl**: WebGL map layers
- **maplibre-gl**: Map rendering
- **supercluster**: Clustering
- **vite**: Build tool

---

*Project ARES v2.0 — Technical Documentation — 2026-03-04 — Updated for Deck.gl + MapLibre and GDELT agent*
