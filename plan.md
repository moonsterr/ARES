# Plan: Matching World Monitor (Geopolitical/Military Focus)

*Excludes production features (desktop app, PWA, localization system)*

---

## Phase 1: Data Sources (Backend)

### 1.1 ACLED Integration

| Item | Description | File to Create |
|------|-------------|----------------|
| API key setup | Get free token at acleddata.com | `.env` |
| ACLED agent | Fetch conflict events from ACLED API | `backend/agents/acled_fetcher.py` |
| Data model | Add `AcledConflictEvent` to `models/event.py` | Modify existing |
| Endpoint | REST endpoint `/api/acled-events` | Add to `main.py` |

**ACLED API Details:**
- Base URL: `https://api.acleddata.com/acled/read`
- Fields: event_type, sub_event_type, country, location, lat, lon, fatalities, actors, source
- Polling: Every 15 minutes

---

### 1.2 UCDP Integration

| Item | Description | File to Create |
|------|-------------|----------------|
| UCDP agent | Fetch from Uppsala Conflict Data Program | `backend/agents/ucdp_fetcher.py` |
| Data model | Add `UcdpConflictEvent` to models | Modify existing |
| Endpoint | REST endpoint `/api/ucdp-events` | Add to `main.py` |

**UCDP API Details:**
- Use GED JSON exports: `https://ucdp.uu.se/downloads/ged/ged221-full.json`
- Fields: conflict_id, event_type, country, location, latitude, longitude, deaths

---

### 1.3 GDELT Integration

| Item | Description | File to Create |
|------|-------------|----------------|
| GDELT service | Fetch from GDELT Project | `backend/services/gdelt_client.py` |
| GDELT translator | Use LLM to extract geo-location from headlines | Extend `llm_pipeline.py` |
| Endpoint | REST endpoint `/api/gdelt-news` | Add to `main.py` |

**GDELT Details:**
- GDELT API: `https://api.gdeltproject.org/api/v2/doc/doc`
- RSS-to-GDELT: `https://rsshub.app/gdelt/news`

---

### 1.4 NGA Maritime Warnings

| Item | Description | File to Create |
|------|-------------|----------------|
| NGA agent | Fetch NAVAREA warnings | `backend/agents/nga_warnings.py` |
| Endpoint | `/api/nga-warnings` | Add to `main.py` |

**Source:**
- URL: `https://msi.gs.mil/api/publications/broadcast-warn`

---

### 1.5 Expand RSS Feeds (170+ sources)

| Item | Description | File to Create |
|------|-------------|----------------|
| Feed config | Centralized RSS feed definitions | `backend/data/rss_feeds.json` |
| Feed agent | Enhanced RSS fetcher with language detection | Rewrite `bravo_news.py` |
| i18n feeds | Add region-specific feeds per language | Extend config |

**Feed Categories:**
- English: BBC, Reuters, AP, Al Jazeera
- Arabic: Al Arabiya, Al Mayadeen, Anadolu
- Russian: BBC Russian, Meduza, Novaya Gazeta
- Regional: Add 160+ more feeds

---

### 1.6 AIS Vessel Tracking (Enhance)

| Item | Description | File to Create |
|------|-------------|----------------|
| OpenAIS alternative | Use opensky-network.org or MarineTraffic free tier | Extend `bravo_marine.py` |
| Vessel database | Add ship type, flag, destination | New `data/vessel_types.json` |

---

## Phase 2: Frontend Map Visualization

### 2.1 Install Dependencies

```bash
cd frontend
npm install deck.gl @deck.gl/core @deck.gl/layers @deck.gl/aggregation-layers @deck.gl/mapbox maplibre-gl supercluster globe.gl three @types/three
```

### 2.2 Create Deck.gl Map Component

| Item | Description | File to Create |
|------|-------------|----------------|
| DeckGLMap | WebGL 2D map with MapLibre | `src/components/DeckGLMap.tsx` |
| MapPopup | Click popup for all layers | `src/components/MapPopup.tsx` |
| Layer configs | Define all layer types | `src/config/mapLayers.ts` |

**Layers to Implement:**
- `ScatterplotLayer` — Conflict dots, fires, earthquakes
- `GeoJsonLayer` — Country boundaries, conflict zones, DMZ
- `ArcLayer` — Trade routes, migration paths
- `HeatmapLayer` — Event density
- `IconLayer` — Military bases, ports, airports
- `PolygonLayer` — CII heatmap, country risk

### 2.3 Implement Globe.gl Component (Alternative View)

| Item | Description | File to Create |
|------|-------------|----------------|
| GlobeMap | 3D globe with globe.gl + Three.js | `src/components/GlobeMap.tsx` |
| Atmosphere shader | Fresnel limb-glow effect | Part of GlobeMap |
| Auto-rotation | Pause on interaction, resume after 60s | Part of GlobeMap |

### 2.4 Map Layer System

| Layer | Data Source | Implementation |
|-------|-------------|----------------|
| Conflicts | ACLED, UCDP, Telegram | ScatterplotLayer, red dots |
| Military bases | Static geoJSON | IconLayer, triangles |
| Military flights | ADSB.lol | IconLayer, aircraft icons |
| Naval vessels | AIS | IconLayer, ship icons |
| Fires | NASA FIRMS | ScatterplotLayer, orange/red |
| Protests/Unrest | ACLED, RSS | ScatterplotLayer, yellow |
| Hotspots | Signal service | PolygonLayer, gradient |
| Cables | Static geoJSON | PathLayer, blue lines |
| Pipelines | Static geoJSON | PathLayer, colored by type |
| Ports | Static geoJSON | IconLayer, port icons |
| Nuclear sites | Static geoJSON | IconLayer, radiation icons |

### 2.5 Smart Clustering (Supercluster)

| Item | Description | File to Create |
|------|-------------|----------------|
| Cluster utils | Wrapper around supercluster | `src/utils/clustering.ts` |
| Apply to layers | Cluster markers at low zoom | Integrate into DeckGLMap |

---

## Phase 3: Data Services (Frontend)

### 3.1 Conflict Service

| Item | Description | File to Create |
|------|-------------|----------------|
| ACLED client | Fetch ACLED via backend | `src/services/acled.ts` |
| UCDP client | Fetch UCDP via backend | `src/services/ucdp.ts` |
| Conflict store | Manage conflict state | Extend `useEventStore` |

### 3.2 Infrastructure Services

| Item | Description | File to Create |
|------|-------------|----------------|
| Military bases | Static data + updates | `src/services/military-bases.ts` |
| Cables | Submarine cable geojson | `src/services/cables.ts` |
| Pipelines | Oil/gas pipeline geojson | `src/services/pipelines.ts` |
| Ports | Shipping port data | `src/services/ports.ts` |
| Nuclear sites | Nuclear facility locations | `src/services/nuclear.ts` |

### 3.3 Enhanced News Service

| Item | Description | File to Create |
|------|-------------|----------------|
| Multi-source news | Aggregate 170+ RSS feeds | Rewrite `src/services/news.ts` |
| Translation pipeline | Use Ollama for translation | `src/services/translation.ts` |
| Geo-extraction | Extract lat/lon from headlines | Extend LLM pipeline |

---

## Phase 4: UI Components

### 4.1 New Panels

| Panel | Description | File to Create |
|-------|-------------|----------------|
| ConflictPanel | Live conflict events with filters | `src/components/ConflictPanel.tsx` |
| MilitaryPanel | Military bases, flights, vessels | `src/components/MilitaryPanel.tsx` |
| NewsPanel | Aggregated news with categories | `src/components/NewsPanel.tsx` |
| UnrestPanel | Protests and civil unrest | `src/components/UnrestPanel.tsx` |

### 4.2 Enhanced Map Controls

| Item | Description | File to Create |
|------|-------------|----------------|
| Layer toggles | 45+ layer visibility controls | Add to `App.tsx` or new component |
| Day/night overlay | Terminator line based on UTC | Part of DeckGLMap |
| Zoom controls | Fit-to-layer buttons | Part of map components |
| Legend | Layer symbol explanations | `src/components/MapLegend.tsx` |

### 4.3 Regional Views

| Item | Description | File to Create |
|------|-------------|----------------|
| Region selector | Middle East, Africa, Asia, Europe, Americas | Add to App |
| Region bounds | Predefined camera positions | `src/config/regions.ts` |

---

## Phase 5: Architecture Changes

### 5.1 Circuit Breaker Pattern (Recommended)

| Item | Description | File to Create |
|------|-------------|----------------|
| Circuit breaker utils | Wrapper with cache + retry logic | `backend/utils/circuit_breaker.py` |
| Apply to agents | Wrap all external API calls | Modify agents |

### 5.2 Backend Service Structure

```
backend/
├── agents/
│   ├── acled_fetcher.py      # NEW
│   ├── ucdp_fetcher.py       # NEW
│   ├── gdelt_fetcher.py     # NEW
│   ├── nga_warnings.py      # NEW
│   └── ...existing...
├── services/
│   ├── conflict_service.py   # NEW - unified conflict data
│   ├── gdelt_client.py      # NEW
│   └── ...existing...
├── utils/
│   └── circuit_breaker.py   # NEW
└── data/
    ├── rss_feeds.json        # NEW - 170+ feeds
    ├── military_bases.json   # ENHANCE - 220+ bases
    ├── cables.json           # NEW
    ├── pipelines.json        # NEW
    └── ports.json            # NEW
```

---

## Summary: Files to Create/Modify

### New Backend Files (~12 files)

- `backend/agents/acled_fetcher.py`
- `backend/agents/ucdp_fetcher.py`
- `backend/agents/gdelt_fetcher.py`
- `backend/agents/nga_warnings.py`
- `backend/services/conflict_service.py`
- `backend/services/gdelt_client.py`
- `backend/utils/circuit_breaker.py`
- `backend/data/rss_feeds.json`
- `backend/data/cables.json`
- `backend/data/pipelines.json`
- `backend/data/ports.json`

### New Frontend Files (~20 files)

- `src/components/DeckGLMap.tsx`
- `src/components/GlobeMap.tsx`
- `src/components/MapPopup.tsx`
- `src/components/ConflictPanel.tsx`
- `src/components/MilitaryPanel.tsx`
- `src/components/NewsPanel.tsx`
- `src/components/UnrestPanel.tsx`
- `src/components/MapLegend.tsx`
- `src/services/acled.ts`
- `src/services/ucdp.ts`
- `src/services/military-bases.ts`
- `src/services/cables.ts`
- `src/services/pipelines.ts`
- `src/services/ports.ts`
- `src/services/nuclear.ts`
- `src/config/mapLayers.ts`
- `src/config/regions.ts`
- `src/utils/clustering.ts`

### Modified Files (~8 files)

- `backend/config.py` — Add new env vars
- `backend/main.py` — Add new endpoints
- `backend/models/event.py` — Add new event types
- `frontend/package.json` — Add dependencies
- `frontend/src/App.tsx` — Integrate new components
- `frontend/src/components/MapContainer.jsx` — Could replace or keep Cesium
- `frontend/src/styles/globe.css` — Add new map styles

---

## Estimated Effort

| Phase | Complexity | Time Estimate |
|-------|------------|---------------|
| Phase 1: Data Sources | High | 2-3 weeks |
| Phase 2: Map Visualization | High | 2-3 weeks |
| Phase 3: Data Services | Medium | 1-2 weeks |
| Phase 4: UI Components | Medium | 1-2 weeks |
| Phase 5: Architecture | Low | 3-5 days |

**Total: ~6-10 weeks for core functionality**

---

## What's NOT Included (Production Features)

- Desktop app (Tauri)
- PWA with offline support
- Full i18n localization system (21 languages)
- Localization lazy-loading
- Proto-first API contracts
- Vercel deployment configs
- Desktop-optimized GPU settings
- PWA service worker
