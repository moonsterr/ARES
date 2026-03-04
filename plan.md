# Plan: ARES Feature Roadmap

*Last updated: 2026-03-04 (`acled` branch)*

This document tracks what has been built and what remains. Completed items are marked ✅. Active work is on the `acled` branch.

---

## Phase 1: Data Sources (Backend)

### 1.1 ACLED Integration ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Config vars | `backend/config.py` | ✅ `ACLED_API_KEY`, `ACLED_EMAIL`, `ACLED_BASE_URL`, `ACLED_MAX_RECORDS`, `ACLED_POLL_INTERVAL`, `ACLED_RELIABILITY_ALPHA`, `ENABLE_ACLED` |
| ACLED agent (CHARLIE-A) | `backend/agents/acled_fetcher.py` | ✅ Full REST agent, circuit breaker, DST α=0.80, SHA-256 dedup |
| REST endpoint | `backend/main.py` | ✅ `GET /api/acled-events` |
| Frontend service | `frontend/src/services/acled.js` | ✅ `fetchAcledEvents()` |

**API**: `https://api.acleddata.com/acled/read` — requires free key + email from acleddata.com
**Countries**: 30 including full Middle East, North Africa, Caucasus, Ukraine

---

### 1.2 UCDP Integration ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Config vars | `backend/config.py` | ✅ `UCDP_BASE_URL`, `UCDP_POLL_INTERVAL`, `UCDP_MAX_RECORDS`, `UCDP_LOOKBACK_DAYS`, `UCDP_RELIABILITY_ALPHA`, `ENABLE_UCDP` |
| UCDP agent (CHARLIE-B) | `backend/agents/ucdp_fetcher.py` | ✅ REST API, rolling 30-day lookback, circuit breaker, DST α=0.78 |
| REST endpoint | `backend/main.py` | ✅ `GET /api/ucdp-events` |
| Frontend service | `frontend/src/services/ucdp.js` | ✅ `fetchUcdpEvents()` |

**API**: `https://ucdpapi.pcr.uu.se/api/gedevents/24.1` — no key required

---

### 1.3 GDELT Integration ✅ COMPLETE (on `main`)

| Item | File | Status |
|------|------|--------|
| Config vars | `backend/config.py` | ✅ `GDELT_BASE_URL`, `GDELT_POLL_INTERVAL`, `GDELT_MODE`, `GDELT_MAX_RECORDS`, `GDELT_QUERY`, `ENABLE_GDELT` |
| GDELT agent (BRAVO-G) | `backend/agents/gdelt_fetcher.py` | ✅ |
| LLM integration | `backend/intelligence/llm_pipeline.py` | ✅ `process_gdelt_entry()` |

**API**: `https://api.gdeltproject.org/api/v2/doc/doc` — no key required

---

### 1.4 NGA Maritime Warnings ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Config vars | `backend/config.py` | ✅ `NGA_BASE_URL`, `NGA_POLL_INTERVAL`, `ENABLE_NGA` |
| NGA agent (CHARLIE-C) | `backend/agents/nga_warnings.py` | ✅ DMS coordinate extraction, circuit breaker |
| REST endpoint | `backend/main.py` | ✅ `GET /api/nga-warnings` |
| Frontend service | `frontend/src/services/ucdp.js` | ✅ `fetchNgaWarnings()` |

**API**: `https://msi.gs.mil/api/publications/broadcast-warn` — no key required

---

### 1.5 Expand RSS Feeds (170+ sources) ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Feed config JSON | `backend/data/rss_feeds.json` | ✅ 170+ feeds with reliability weights |
| Updated agent | `backend/agents/bravo_news.py` | ✅ `_load_feeds()` reads from JSON; per-feed DST α |

---

### 1.6 Conflict Summary Service ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Service layer | `backend/services/conflict_service.py` | ✅ `get_conflict_events()`, `get_conflict_summary()` |
| REST endpoint | `backend/main.py` | ✅ `GET /api/conflict/summary` |
| Frontend service | `frontend/src/services/ucdp.js` | ✅ `fetchConflictSummary()` |

---

### 1.7 AIS Vessel Tracking Enhancement

| Item | Status |
|------|--------|
| `bravo_marine.py` | Exists — requires commercial MarineTraffic key |
| AISHub free alternative | Not implemented |
| `data/vessel_types.json` | Not created |

**Recommendation**: Evaluate AISHub (https://www.aishub.net/) as a keyless alternative.

---

## Phase 2: Frontend Map Visualization

### 2.1 Deck.gl Map Component ✅ COMPLETE (on `main`)

| Item | File | Status |
|------|------|--------|
| DeckGLMap | `frontend/src/components/DeckGLMap.jsx` | ✅ |
| MapPopup | `frontend/src/components/MapPopup.jsx` | ✅ |
| Layer config | `frontend/src/config/mapLayers.js` | ✅ |

**Layers implemented**: conflicts (ScatterplotLayer), heatmap (HeatmapLayer), aircraft (IconLayer), vessels (IconLayer), military bases (IconLayer), ports (IconLayer), cables (PathLayer), pipelines (PathLayer), hotspots (ScatterplotLayer)

---

### 2.2 Nuclear Sites Layer ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Static GeoJSON | `backend/data/nuclear_sites.geojson` | ✅ 15 facilities (IAEA/NTI sources) |
| API endpoint | `backend/main.py` | ✅ included in `/api/infrastructure` |

---

### 2.3 Globe.gl 3D View

| Item | Status |
|------|--------|
| `GlobeMap.jsx` component | Not implemented |
| Mode toggle (2D/3D) | Not implemented |

**Priority**: Low — 2D Deck.gl map is working well.

---

### 2.4 Smart Clustering (Supercluster) ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Clustering wrapper | `frontend/src/utils/clustering.js` | ✅ `buildIndex()`, `getClusters()`, `expandCluster()`, `getClusterExpansionZoom()` |

**Not yet wired** into `DeckGLMap.jsx` — utility is ready; integration pending.

---

## Phase 3: Data Services (Frontend) ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| ACLED client | `frontend/src/services/acled.js` | ✅ |
| UCDP client | `frontend/src/services/ucdp.js` | ✅ |
| NGA warnings | `frontend/src/services/ucdp.js` | ✅ `fetchNgaWarnings()` |
| Conflict summary | `frontend/src/services/ucdp.js` | ✅ `fetchConflictSummary()` |
| Infrastructure | `frontend/src/services/infrastructure.js` | ✅ |

Infrastructure services for cables, pipelines, ports, military bases, nuclear sites are all served through the unified `/api/infrastructure` endpoint — separate service files are not needed.

---

## Phase 4: UI Components

### 4.1 MapLegend ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Collapsible legend | `frontend/src/components/MapLegend.jsx` | ✅ Categories, infra symbols, source list |

---

### 4.2 Regional Views ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Region bounds | `frontend/src/config/regions.js` | ✅ 12 named regions + `DEFAULT_REGION` |
| Region selector UI | Not yet wired into App.jsx | ❌ |

---

### 4.3 Additional Panels

| Panel | File | Status |
|-------|------|--------|
| `ConflictPanel.jsx` | Not created | ❌ |
| `MilitaryPanel.jsx` | Not created | ❌ |
| `NewsPanel.jsx` | Not created | ❌ |
| `UnrestPanel.jsx` | Not created | ❌ |

Current `EventLog.jsx` / `EventCard.jsx` covers the basic use case. These panels would add source/category filters and tabbed views.

---

### 4.4 Day/Night Terminator Overlay

| Item | Status |
|------|--------|
| Terminator line | Not implemented |

Would use `suncalc` npm package and a `PathLayer` or `PolygonLayer` updating every minute.

---

## Phase 5: Architecture

### 5.1 Circuit Breaker ✅ COMPLETE

| Item | File | Status |
|------|------|--------|
| Circuit breaker | `backend/utils/circuit_breaker.py` | ✅ CLOSED/OPEN/HALF_OPEN states, cache, recovery |
| Applied to ACLED | `acled_fetcher.py` | ✅ |
| Applied to UCDP | `ucdp_fetcher.py` | ✅ |
| Applied to NGA | `nga_warnings.py` | ✅ |
| Applied to GDELT | `gdelt_fetcher.py` | Not yet wrapped |

---

### 5.2 Backend Service Structure ✅ COMPLETE

```
backend/
├── agents/
│   ├── alpha_harvester.py      ✅
│   ├── bravo_adsb.py           ✅
│   ├── bravo_firms.py          ✅
│   ├── bravo_marine.py         ✅ (keyless AIS not yet implemented)
│   ├── bravo_news.py           ✅ 170+ feeds from JSON
│   ├── bravo_sentinel.py       ✅
│   ├── bravo_websdr.py         ✅ (stub)
│   ├── gdelt_fetcher.py        ✅
│   ├── acled_fetcher.py        ✅ CHARLIE-A
│   ├── ucdp_fetcher.py         ✅ CHARLIE-B
│   └── nga_warnings.py         ✅ CHARLIE-C
├── services/
│   └── conflict_service.py     ✅
├── utils/
│   └── circuit_breaker.py      ✅
└── data/
    ├── rss_feeds.json           ✅ 170+ feeds
    ├── cables.geojson           ✅
    ├── pipelines.geojson        ✅
    ├── ports.geojson            ✅
    ├── military_bases.geojson   ✅ 63 bases
    └── nuclear_sites.geojson    ✅ 15 facilities
```

---

## What Remains (Prioritised)

### High value / low effort
1. **Wire `clustering.js` into `DeckGLMap.jsx`** — utility exists, just needs integration
2. **Wire `regions.js` into `App.jsx`** — region-jump selector UI (dropdown or button strip)
3. **Wrap GDELT in circuit breaker** — currently unprotected external call
4. **Add `nuclear_sites` layer to `mapLayers.js` + `DeckGLMap.jsx`** — data exists, not rendered yet

### Medium value / medium effort
5. **`ConflictPanel.jsx`** — tabbed sidebar with ACLED/UCDP/NGA filters
6. **`MapLegend.jsx` wired into `App.jsx`** — component exists but may not be imported yet
7. **AISHub free AIS** — replace MarineTraffic dependency

### Low value / high effort
8. **Globe.gl 3D view** — nice to have, not operationally necessary
9. **Day/night terminator overlay** — useful context but cosmetic
10. **Additional panel components** (MilitaryPanel, NewsPanel, UnrestPanel)

---

## What's NOT in Scope

- Desktop app (Tauri / Electron)
- PWA with offline support
- Full i18n localization system (21 languages)
- Proto-first API contracts (gRPC/protobuf)
- Vercel / cloud deployment configs
- GPU-optimized rendering settings
- PWA service worker

---

*Project ARES — Feature Plan v3.0 — 2026-03-04*
*Phase 1 (data sources): complete | Phase 2 (map): mostly complete | Phase 5 (architecture): complete*
