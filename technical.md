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
- **Used by**: Developers running the full stack with `docker compose up`

### `.env.example`
- **Purpose**: Template for all required environment variables
- **Contains**: API keys for Telegram, Ollama, NASA FIRMS, Copernicus, etc.
- **Used by**: Users copying to `.env` during setup

---

## Backend (`/backend`)

### `config.py`
- **Purpose**: Centralized configuration management using Pydantic Settings
- **Key Classes/Functions**:
  - `Settings` class: Pydantic BaseSettings with env variable mappings
- **Environment Variables Parsed**:
  - Database: `DATABASE_URL`
  - Telegram: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`
  - Ollama: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - NASA FIRMS: `FIRMS_MAP_KEY`
  - ADSB.lol: `ADSB_LOL_BASE_URL`
  - Copernicus: `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`, `COPERNICUS_CLIENT_ID`
  - Feature flags: `ENABLE_TELEGRAM`, `ENABLE_ADSB`, `ENABLE_FIRMS`, `ENABLE_SENTINEL`, `ENABLE_WEBSDR`, `ENABLE_MARINE`
- **Used by**: All backend modules import `settings` for configuration access

### `main.py`
- **Purpose**: FastAPI application entry point with lifespan management
- **Key Functions**:
  - `lifespan()`: Async context manager - initializes DB on startup, launches all agents, cleans up on shutdown
  - `ws_events()`: WebSocket endpoint at `/ws/events` for real-time streaming
  - `get_events()`: REST endpoint at `/api/events` - returns recent events with filtering
  - `health()`: Health check at `/api/health` - returns agent status
  - `agent_status()`: Returns detailed agent configuration status
- **Dependencies**:
  - Imports all agents: `run_harvester`, `poll_adsb`, `poll_firms`, `run_sentinel_worker`, `run_websdr_monitor`, `poll_marine`
  - Uses `database.py`: `init_db`, `get_recent_events`
  - Uses `websocket_manager.py`: `manager`
- **Used by**: Uvicorn server (`uvicorn main:app`)

### `database.py`
- **Purpose**: PostgreSQL + PostGIS database interface using asyncpg
- **Key Functions**:
  - `init_db()`: Creates connection pool and applies schema
  - `get_pool()`: Returns asyncpg Pool singleton
  - `close_db()`: Closes connection pool
  - `insert_event(intel, source)`: Inserts ConflictIntel to events table, returns ID
  - `find_nearby_events(lat, lon, radius_m)`: Spatial query for events within radius
  - `promote_to_verified(event_id, hs_source, frp)`: Marks event as verified by FIRMS
  - `update_event_quicklook(event_id, quicklook_url)`: Attaches Sentinel-2 image
  - `insert_hotspot(data)`: Stores FIRMS thermal hotspot
  - `upsert_aircraft(data)`: Insert/update aircraft position (ICAO hex as key)
  - `upsert_vessel(data)`: Insert/update vessel AIS data (MMSI as key)
  - `get_recent_events(limit, category)`: REST fallback - fetches events
- **Schema**:
  - `events`: Main intelligence events table with PostGIS Point geometry
  - `hotspots`: NASA FIRMS thermal hotspots
  - `aircraft`: Real-time aircraft positions
  - `vessels`: AIS vessel positions
- **Indexes**: GIST spatial indexes on location columns, B-tree on timestamps
- **Used by**: All agents for persistence, `main.py` for initialization

### `websocket_manager.py`
- **Purpose**: Manages WebSocket connections for real-time frontend updates
- **Key Classes**:
  - `ConnectionManager`: Singleton class managing all connected clients
- **Key Methods**:
  - `connect(ws)`: Accepts and registers new WebSocket connection
  - `disconnect(ws)`: Removes disconnected client
  - `broadcast_json(data)`: Sends JSON to all connected clients
  - `connection_count`: Property returning active client count
- **Used by**: All agents call `manager.broadcast_json()` to push events to frontend

---

## Backend Models (`/backend/models`)

### `event.py`
- **Purpose**: Core event schema - all intelligence events conform to this model
- **Key Classes**:
  - `EventCategory(str, Enum)`: Categories - air_alert, ground_strike, troop_movement, naval_event, explosion, casualty_report, unknown
  - `LocationEntity`: Raw text, normalized name, lat/lon coordinates, confidence
  - `ConflictIntel`: Main model with category, confidence, translation, locations, weapons, units, casualties, DST fields (bel, pl, conflict_k), fusion status
- **Key Methods**:
  - `entities_json()`: Serializes entities to JSON string
  - `lat`, `lon`, `location_name`: Properties returning first location's data
- **Used by**: `llm_pipeline.py` returns `ConflictIntel` objects, `database.py` serializes them

### `aircraft.py`
- **Purpose**: Pydantic schema for ADS-B aircraft data
- **Fields**: icao_hex, callsign, lat, lon, altitude_ft, heading, speed_kts, ac_type, reg, last_seen
- **Used by**: `bravo_adsb.py` for data validation

### `vessel.py`
- **Purpose**: Pydantic schema for AIS vessel data
- **Fields**: mmsi, name, lat, lon, heading, speed_kts, vessel_type, flag, last_seen
- **Used by**: `bravo_marine.py` for data validation

### `hotspot.py`
- **Purpose**: Pydantic schema for NASA FIRMS thermal hotspots
- **Fields**: lat, lon, source (VIIRS_SNPP_NRT/MODIS_NRT), brightness, frp (Fire Radiative Power), confidence, detected_at
- **Used by**: `bravo_firms.py` for data validation

---

## Intelligence Processing (`/backend/intelligence`)

### `categorizer.py`
- **Purpose**: Fast regex-based event categorization - runs before LLM
- **Key Functions**:
  - `categorize_message(text)`: Returns (EventCategory, confidence_score)
  - `is_conflict_relevant(text)`: Quick filter - does text mention conflict keywords?
  - `extract_casualty_count(text)`: Finds casualty numbers using regex
  - `extract_weapon_mentions(text)`: Finds weapon systems (F-35, Iron Dome, HIMARS, etc.)
  - `extract_unit_mentions(text)`: Finds military units (IDF, Hamas, IRGC, etc.)
- **Patterns**: Pre-compiled regex patterns for each category stored in `_COMPILED_PATTERNS`
- **Conflict Keywords**: Composite regex for quick pre-filtering
- **Used by**: `llm_pipeline.py` calls `categorize_message()` in step 3

### `geocoder.py`
- **Purpose**: Two-stage location resolution
- **Key Functions**:
  - `lookup_local(text_fragment, threshold)`: Fuzzy match against local military base DB using rapidfuzz
  - `lookup_nominatim(location_text)`: Async Nominatim OpenStreetMap API fallback (rate-limited 1 req/s)
  - `resolve_location(raw_text, normalized)`: Main entry point - tries local first, then Nominatim
  - `reload_db()`: Hot-reloads the military base database
- **Data Source**: Local JSON file `mideast_military_bases.json` with ~63 curated sites
- **Rate Limiting**: Enforces 1 second between Nominatim calls
- **Used by**: `alpha_harvester.py` calls `resolve_location()` for each extracted location

### `llm_pipeline.py`
- **Purpose**: Complete NLP pipeline for Telegram messages
- **Key Functions**:
  - `detect_language(text)`: Uses fasttext (lid.176.bin model) to detect language (<5ms)
  - `translate_to_english(text, source_lang)`: Ollama API call for Hebrew/Arabic/Persian translation
  - `extract_entities_llm(translated_text)`: Ollama NER - extracts locations, weapons, units, casualties
  - `classify_category_llm(text)`: Ollama category refinement for low-confidence regex cases
  - `_call_ollama(prompt, max_tokens)`: Internal - makes HTTP request to Ollama API
  - `process_message(raw_text, channel_name)`: Main pipeline - runs all steps
- **Pipeline Steps**:
  1. Language detection (fasttext)
  2. Translation if needed (Ollama)
  3. Regex categorization + entity extraction
  4. LLM refinement if regex confidence < 0.6
  5. Geocoding (done separately by caller)
- **Model**: Uses `llama3.1:8b` via Ollama API at `OLLAMA_BASE_URL`
- **Used by**: `alpha_harvester.py` calls `process_message()` for each Telegram message

### `confidence.py`
- **Purpose**: Dempster-Shafer Theory + PCR5 fusion confidence engine
- **Key Functions**:
  - `discount_bba(bba, alpha)`: Reliability discounting (Shafer 1976) - transfers mass to universal set based on source reliability α
  - `pcr5_combine(m1, m2)`: PCR5 combination of two Basic Belief Assignments - returns (combined_bba, conflict_factor_K)
  - `belief(bba, hypothesis)`: Bel(A) = Σ m(B) for all B ⊆ A
  - `plausibility(bba, hypothesis)`: Pl(A) = Σ m(B) for all B where B ∩ A ≠ ∅
  - `location_to_bba(lat, lon, location_name, base_confidence)`: Converts geocoded location to BBA
  - `initial_bba(intel, alpha)`: Creates initial BBA for single Telegram message
  - `fuse_two_sources(...)`: Main fusion function - combines two location reports using PCR5
  - `haversine_km(lat1, lon1, lat2, lon2)`: Distance calculation between coordinates
- **PCR5 Logic**:
  - K < 0.3: Sources agree → emit fused coordinate
  - K 0.3-0.5: Uncertain → display both candidates in amber
  - K ≥ 0.5: Conflict → refuse to fuse, report both in purple
- **Used by**: `alpha_harvester.py` calls `initial_bba()`, `fusion.py` calls `fuse_two_sources()`

### `fusion.py`
- **Purpose**: Cross-source event correlation and fusion
- **Key Functions**:
  - `find_correlating_events(pool, lat, lon, category, event_id, time_window_hours, radius_km)`: Spatial-temporal query for matching events
  - `apply_fusion(pool, new_event, correlated_event)`: Applies PCR5 fusion, updates DB
  - `run_fusion_check(...)`: Entry point - checks for correlations after event insert, broadcasts results
- **Correlation Criteria**:
  - Spatial: Within 25km (configurable)
  - Temporal: Within 2 hours (configurable)
  - Category: Compatible categories defined in `COMPATIBLE_CATEGORIES` dict
- **Used by**: Called from agents after new event insertion

---

## Agents (`/backend/agents`)

### `alpha_harvester.py`
- **Purpose**: Telegram channel monitoring using Telethon
- **Key Components**:
  - `WATCHED_CHANNELS`: List of 16 Telegram channel usernames to monitor
  - `CHANNEL_RELIABILITY`: Dict mapping channel → α weight (0.45-0.90)
- **Key Functions**:
  - `run_harvester()`: Main async task - starts Telethon client, registers NewMessage handler
- **Workflow**:
  1. Receives new message from watched channel
  2. Gets α weight from channel name
  3. Calls `llm_pipeline.process_message()` for NLP
  4. Calls `geocoder.resolve_location()` for each location
  5. Calls `confidence.initial_bba()` to compute DST fields
  6. Calls `database.insert_event()` to persist
  7. Calls `manager.broadcast_json()` to push to frontend
- **Error Handling**: Catches FloodWaitError (auto-sleep), ChannelPrivateError (not a member)
- **Used by**: Launched by `main.py` lifespan when `ENABLE_TELEGRAM=true`

### `bravo_adsb.py`
- **Purpose**: Military aircraft tracking via ADSB.lol API
- **Key Constants**:
  - `ME_BBOX`: Middle East bounding box (lat 14-42, lon 25-65)
  - `ME_CENTER_LAT`, `ME_CENTER_LON`: Tel Aviv coordinates for regional feed
  - `ME_RADIUS_NM`: 250 nautical miles for regional query
  - `POLL_INTERVAL_S`: 10 seconds between polls
- **Key Functions**:
  - `_parse_aircraft(ac)`: Maps ADSB.lol v2 response to internal schema
  - `_in_me_bbox(record)`: Filters to Middle East bounding box
  - `_fetch_global_mil(client)`: Fetches `/mil` global military feed
  - `_fetch_regional(client)`: Fetches `/point/{lat}/{lon}/{radius}` regional feed
  - `poll_adsb()`: Main polling loop - merges both feeds, deduplicates by ICAO hex
- **Workflow**:
  1. Fetches global + regional feeds concurrently
  2. Merges and deduplicates by ICAO hex
  3. Filters to ME bounding box
  4. Upserts to `aircraft` table
  5. Broadcasts sweep (first 50 aircraft) over WebSocket
- **Used by**: Launched by `main.py` when `ENABLE_ADSB=true`

### `bravo_firms.py`
- **Purpose**: NASA FIRMS thermal hotspot ingestion for fusion validation
- **Key Constants**:
  - `FIRMS_URL`: NASA FIRMS CSV API endpoint
  - `ME_BBOX`: "25,14,65,42" (west,south,east,north)
  - `FUSION_RADIUS_M`: 5000m - events within this radius get verified
  - `POLL_INTERVAL_S`: 300 seconds (5 minutes)
- **Key Functions**:
  - `poll_firms()`: Main polling loop
- **Workflow**:
  1. Polls VIIRS_SNPP_NRT and MODIS_NRT sources
  2. Parses CSV response to hotspot records
  3. Inserts to `hotspots` table
  4. Calls `find_nearby_events()` to find Telegram strikes within 5km
  5. Calls `promote_to_verified()` to mark matching events as VERIFIED
  6. Broadcasts fusion_verified over WebSocket
- **Used by**: Launched by `main.py` when `ENABLE_FIRMS=true`

### `bravo_sentinel.py`
- **Purpose**: Fetches Sentinel-2 satellite imagery for verified events
- **Key Components**:
  - `_imagery_queue`: asyncio.Queue of (event_id, lat, lon) tuples
  - `TOKEN_URL`: Copernicus OAuth2 token endpoint
- **Key Functions**:
  - `get_access_token()`: Obtains OAuth2 token from Copernicus
  - `fetch_sentinel_quicklook(lat, lon, event_id)`: Searches for recent cloud-free Sentinel-2 scene
  - `enqueue_imagery_request(event_id, lat, lon)`: Adds event to fetch queue
  - `run_sentinel_worker()`: Background worker processing queue
  - `_fetch_sync(...)`: Synchronous wrapper for thread pool execution
- **Workflow**:
  1. Worker waits on queue for verified events
  2. Queries Copernicus catalogue API for MSIL2A scenes
  3. Filters to <20% cloud cover, last 7 days
  4. Gets QUICKLOOK asset download link
  5. Updates event with quicklook URL
  6. Broadcasts satellite_imagery over WebSocket
- **Used by**: Called from `bravo_firms.py` when events are promoted to VERIFIED

### `bravo_websdr.py`
- **Purpose**: WebSDR HFGCS radio monitoring (stub implementation)
- **Key Constants**:
  - `WEBSDR_HOST`: "http://websdr.ewi.utwente.nl:8901"
  - `HFGCS_FREQS`: [8992, 11175] kHz
  - `POLL_INTERVAL_S`: 600 seconds (10 minutes)
- **Key Functions**:
  - `monitor_hfgcs_freq(freq_khz, duration_s)`: Captures audio from WebSDR
  - `is_eam_traffic(text)`: Checks for Emergency Action Message patterns
  - `run_websdr_monitor()`: Main polling loop
- **Note**: Whisper integration is TODO - audio captured but not transcribed
- **Used by**: Launched by `main.py` when `ENABLE_WEBSDR=true`

### `bravo_marine.py`
- **Purpose**: MarineTraffic AIS vessel tracking
- **Key Constants**:
  - `MARITIME_REGIONS`: Bounding boxes for red_sea, persian_gulf, mediterranean, gulf_of_oman
  - `MT_VESSELS_URL`: MarineTraffic API endpoint
  - `POLL_INTERVAL_S`: 300 seconds (5 minutes)
- **Key Functions**:
  - `_in_region(lat, lon)`: Checks if position is in tracked region
  - `poll_marine()`: Main polling loop
- **Workflow**:
  1. Polls each maritime region separately
  2. Filters to cargo/tanker/naval vessel types
  3. Upserts to `vessels` table
  4. Broadcasts ais_sweep summary
- **Note**: Requires paid MarineTraffic API key - disabled by default
- **Used by**: Launched by `main.py` when `ENABLE_MARINE=true`

---

## Frontend (`/frontend`)

### `index.html`
- **Purpose**: HTML entry point
- **Contains**: Root div, loads main.jsx as module

### `main.jsx`
- **Purpose**: React application bootstrap
- **Code**: Uses createRoot to render App with StrictMode

### `App.jsx`
- **Purpose**: Root React component - layout orchestration
- **Key Components**:
  - `StatusBar`: Top bar with connection status, event count, agent indicators
  - `MapContainer`: CesiumJS 3D globe
  - `EventLog`: Sidebar with event feed
- **Hooks Used**:
  - `useWebSocket('/ws/events', handleNewEvent)`: Manages WebSocket connection
  - `useEventStore()`: Manages event state
- **State**:
  - `selectedEvent`: Currently selected event for detail view

### `vite.config.js`
- **Purpose**: Vite build configuration
- **Plugins**:
  - `@vitejs/plugin-react`: React JSX support
  - `vite-plugin-cesium`: Handles CesiumJS asset bundling
- **Proxy**: Rewrites `/api` → `http://localhost:8000`, WebSocket to same

### `package.json`
- **Dependencies**:
  - `cesium@^1.138.0`: 3D globe library
  - `react@^18.3.1`, `react-dom@^18.3.1`: UI framework
- **DevDependencies**:
  - `@vitejs/plugin-react@^4.3.4`: React plugin
  - `vite@^5.4.10`: Build tool
  - `vite-plugin-cesium@^1.2.23`: Cesium integration

---

## Frontend Components (`/frontend/src/components`)

### `MapContainer.jsx`
- **Purpose**: CesiumJS 3D globe rendering
- **Key Functions**:
  - Initializes Viewer with dark theme, terrain, no UI chrome
  - `upsertEntity(viewer, entityMap, event)`: Creates/updates Cesium entities
- **Cesium APIs Used**:
  - `Viewer`: Main globe widget
  - `Ion.defaultAccessToken`: Sets Cesium Ion token
  - `Terrain.fromWorldTerrain()`: 3D terrain
  - `Cartesian3.fromDegrees()`: Coordinate conversion
  - `Entity`: Point + label entities
  - `ScreenSpaceEventHandler`: Click detection
  - `NearFarScalar`, `DistanceDisplayCondition`: Visibility scaling
- **Workflow**:
  1. Creates Viewer with dark styling
  2. Sets Middle East initial camera view
  3. On event update, creates colored point at lat/lon
  4. Click handler retrieves event data from entity properties
- **Used by**: `App.jsx`

### `EventLog.jsx`
- **Purpose**: Intelligence feed sidebar
- **Key Functions**:
  - Sorts events newest-first
  - Renders EventCard for each event
- **Used by**: `App.jsx`

### `EventCard.jsx`
- **Purpose**: Individual event display in sidebar
- **Components**:
  - `ConfidenceMeter`: DST interval visualization
- **Displays**:
  - Category badge (color-coded)
  - Verified badge if satellite-confirmed
  - Relative timestamp
  - Location name + coordinates
  - Translation text
  - Source attribution
- **Interactions**: Click to select, shows on globe
- **Used by**: `EventLog.jsx`

### `StatusBar.jsx`
- **Purpose**: Top status bar with connection info
- **Displays**:
  - Project ARES branding
  - WebSocket status (LIVE/CONNECTING/ERROR)
  - Event count
  - ALPHA/BRAVO agent indicators (always on - not real status)
- **Used by**: `App.jsx`

### `ConfidenceMeter.jsx`
- **Purpose**: Visualizes DST belief/plausibility interval
- **Visual**:
  - Left grey segment: ignorance (0 → Bel)
  - Colored segment: belief (Bel → Pl)
  - Right grey segment: uncertainty (Pl → 1.0)
- **Logic**:
  - Green if Pl > 0.7 (high confidence)
  - Amber if lower
  - Purple if conflict K > 0.4
- **Used by**: `EventCard.jsx`

### `SatellitePanel.jsx`
- **Purpose**: Displays Sentinel-2 quicklook for verified events
- **Shows**:
  - Event location name
  - "SENTINEL-2 CONFIRMED" badge
  - Quicklook image
  - Source attribution (Copernicus/ESA)
- **Used by**: Currently unused (planned for high-zoom overlay)

---

## Frontend Hooks (`/frontend/src/hooks`)

### `useWebSocket.js`
- **Purpose**: Manages WebSocket connection with auto-reconnect
- **Key Functions**:
  - `connect()`: Creates WebSocket, sets up handlers
- **Features**:
  - Auto-reconnect with exponential backoff (max 10 attempts)
  - 30-second keepalive ping
  - Parses JSON messages, calls `onMessage` callback
- **Returns**: `{ status }` - connecting/open/closed/error
- **Used by**: `App.jsx`

### `useEventStore.js`
- **Purpose**: In-memory event state management
- **Key Functions**:
  - `addEvent(incoming)`: Adds new event, caps at 500
  - Handles `fusion_verified` type for marking events verified
  - Updates existing events by ID (deduplication)
- **Used by**: `App.jsx`

### `useCesiumEntities.js`
- **Purpose**: Manages Cesium entity lifecycle (currently unused - logic is in MapContainer)
- **Key Functions**:
  - `upsertEntity(event)`: Creates/updates Cesium entity
  - `removeEntity(eventId)`: Removes entity
  - `clearAll()`: Removes all entities
- **Note**: Logic duplicated in MapContainer.jsx - could be refactored to use this

---

## Frontend Libraries (`/frontend/src/lib`)

### `cesiumColors.js`
- **Purpose**: Color constants for event categories
- **Exports**:
  - `EVENT_COLORS`: Hex colors for each EventCategory
  - `EVENT_GLOW_COLORS`: RGBA glow variants
  - `CATEGORY_CSS_VARS`: CSS custom property references
- **Colors**:
  - air_alert: #ef4444 (red)
  - ground_strike: #f97316 (orange)
  - troop_movement: #3b82f6 (blue)
  - naval_event: #06b6d4 (cyan)
  - explosion: #eab308 (amber)
  - casualty_report: #e879f9 (pink)
  - verified: #22c55e (green)
  - conflict: #a855f7 (purple)
- **Used by**: `MapContainer.jsx`, `useCesiumEntities.js`

### `formatters.js`
- **Purpose**: Utility functions for displaying data
- **Key Functions**:
  - `formatRelativeTime(timestamp)`: "2 min ago", "just now", etc.
  - `formatAbsoluteTime(timestamp)`: ISO format
  - `formatCoords(lat, lon)`: "31.5000°N 34.5000°E"
  - `formatConfidence(value)`: "75.0%"
  - `formatBelPl(bel, pl)`: "[75%, 90%]"
  - `truncateText(text, maxLength)`: Adds ellipsis
- **Used by**: Various components

---

## Frontend Styles (`/frontend/src/styles`)

### `global.css`
- **Purpose**: Root styles, CSS variables, layout
- **CSS Variables**:
  - Colors: `--color-bg`, `--color-surface`, `--color-text-primary`, category colors
  - Glassmorphism: `--glass-bg`, `--glass-blur`, `--glass-border`
  - Typography: `--font-mono`
- **Layout**:
  - Grid: `grid-template-columns: 1fr 380px` (globe + sidebar)
  - Status bar height: 36px
- **Used by**: `App.jsx` (imported in main)

### `globe.css`
- **Purpose**: CesiumJS viewer overrides
- **Hides**: Default Cesium UI (toolbar, credits, bottom bar)
- **Loading**: Spinner animation for initial load
- **Used by**: `MapContainer.jsx`

### `sidebar.css`
- **Purpose**: Event log sidebar styling
- **Features**:
  - Glassmorphism background
  - Scrollbar styling
  - Empty state messaging
- **Used by**: `EventLog.jsx`

### `cards.css`
- **Purpose**: Event card and confidence meter styles
- **Event Card**:
  - Category-colored left border
  - Hover effects
  - Badge styling
- **Confidence Meter**:
  - Segmented bar visualization
  - Color transitions
- **Satellite Panel**:
  - Sentinel-2 quicklook display
- **Used by**: `EventCard.jsx`, `ConfidenceMeter.jsx`, `SatellitePanel.jsx`

---

## Data Files (`/backend/data`)

### `mideast_military_bases.json`
- **Purpose**: Local geocoding database (~63 curated military sites)
- **Structure**: Array of objects with `canonical` name, `lat`, `lon`, `alt_names` array
- **Used by**: `geocoder.py` for fast local lookup

### `channel_reliability.json`
- **Purpose**: Per-channel α reliability weights (planned use - currently hardcoded in alpha_harvester.py)
- **Used by**: Not currently imported (placeholder for future)

### `build_military_db.py`
- **Purpose**: Script to expand military base database using GeoNames data
- **Fetches**: GeoNames military features for 16 Middle East countries
- **Merges**: With existing curated entries without duplication

---

## Summary: Data Flow

```
Telegram Message
    ↓
alpha_harvester.py (receives via Telethon)
    ↓
llm_pipeline.py (language detection, translation, NER)
    ↓
categorizer.py (regex categorization)
    ↓
geocoder.py (location resolution)
    ↓
confidence.py (initial BBA computation)
    ↓
database.py (insert_event)
    ↓
websocket_manager.py (broadcast to frontend)
    ↓
fusion.py (checks for correlations with existing events)
    ↓
bravo_firms.py (promotes to VERIFIED if FIRMS hotspot matches)
    ↓
bravo_sentinel.py (attaches satellite imagery)
```

```
ADSB.lol API
    ↓
bravo_adsb.py (polls every 10s)
    ↓
database.py (upsert_aircraft)
    ↓
websocket_manager.py (broadcast sweep)

NASA FIRMS API
    ↓
bravo_firms.py (polls every 5 min)
    ↓
database.py (insert_hotspot)
    ↓
Fusion validation → promote_to_verified
    ↓
bravo_sentinel.py (fetch imagery)
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
- **requests**: Sync HTTP (Copernicus)

### Frontend
- **react**: UI framework
- **cesium**: 3D globe
- **vite**: Build tool
- **vite-plugin-cesium**: Cesium integration
