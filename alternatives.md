# Alternative & Future Data Sources

This document tracks data sources that were planned as future additions. Items that have since been implemented are marked accordingly.

---

## ACLED (Armed Conflict Location & Event Data)

**Status**: IMPLEMENTED (`backend/agents/acled_fetcher.py` — Agent CHARLIE-A)
**Feature flag**: `ENABLE_ACLED` (default `false` — requires free registration)

### What was built
- Full REST API agent polling `https://api.acleddata.com/acled/read`
- Both `ACLED_API_KEY` and `ACLED_EMAIL` passed in every request (ACLED requirement)
- Covers ISR, PSE, LBN, SYR, IRQ, IRN, YEM, SAU, ARE, KWT, BHR, QAT, OMN, JOR, EGY, LBY, TUN, DZA, MAR, SDN, ETH, SOM, DJI, ERI, TUR, ARM, AZE, GEO, UKR, RUS
- Category mapping: ACLED `event_type` / `sub_event_type` → `EventCategory`
- DST α = 0.80 (high reliability; cross-referenced source)
- SHA-256 deduplication by `event_id_cnty`, TTL 24 hours
- Circuit breaker: 3 failures → open for 5 minutes, cache TTL 30 minutes
- Fatality count → `casualty_count`; if fatalities > 0 → `is_confirmed = True`
- Frontend service: `frontend/src/services/acled.js` → `fetchAcledEvents()`
- REST endpoint: `GET /api/acled-events`

### Notes
- ACLED has a ~2-week lag on some lower-priority regions
- Register free at https://acleddata.com/register/ (instant approval)
- Both key AND email are required per request — missing either causes the agent to sleep

---

## UCDP (Uppsala Conflict Data Program)

**Status**: IMPLEMENTED (`backend/agents/ucdp_fetcher.py` — Agent CHARLIE-B)
**Feature flag**: `ENABLE_UCDP` (default `true` — no credentials required)

### What was built
- REST API agent polling `https://ucdpapi.pcr.uu.se/api/gedevents/24.1`
- Rolling lookback window — queries events from last `UCDP_LOOKBACK_DAYS` (default 30) days
- `type_of_violence` mapping: 1 (state-based) → `ground_strike`, 2 (non-state) → `ground_strike`, 3 (one-sided/civilian) → `casualty_report`
- Total deaths = `deaths_civilians + deaths_a + deaths_b`
- DST α = 0.78 (academically peer-reviewed; lower velocity than ACLED)
- SHA-256 deduplication by UCDP `id`, TTL 48 hours
- Circuit breaker: 3 failures → open for 10 minutes, cache TTL 1 hour
- Frontend service: `frontend/src/services/ucdp.js` → `fetchUcdpEvents()`
- REST endpoint: `GET /api/ucdp-events`

### Notes
- Previous docs said UCDP was static JSON dump — this is incorrect; UCDP has had a live REST API since v22+
- The REST API endpoint is `ucdpapi.pcr.uu.se`, not the download page at `ucdp.uu.se/downloads`

---

## NGA Maritime Warnings (NAVAREA)

**Status**: IMPLEMENTED (`backend/agents/nga_warnings.py` — Agent CHARLIE-C)
**Feature flag**: `ENABLE_NGA` (default `true` — no credentials required)

### What was built
- REST API agent polling `https://msi.gs.mil/api/publications/broadcast-warn?output=json&status=active`
- Handles both response shapes: plain `list` and `{"broadcastWarn": [...]}`
- Coordinate extraction via regex from warning text — DMS format (`°`, `'`, `N/S/E/W`)
- Always emits `EventCategory.naval_event`
- Confidence 0.75, DST α = 0.82 (official government source)
- SHA-256 deduplication by `msgNum`, TTL 24 hours
- Circuit breaker: 3 failures → open for 5 minutes, cache TTL 30 minutes
- REST endpoint: `GET /api/nga-warnings`
- Included in `frontend/src/services/ucdp.js` → `fetchNgaWarnings()`

---

## RSS Feed Expansion (170+ sources)

**Status**: IMPLEMENTED (`backend/data/rss_feeds.json` + updated `bravo_news.py`)

### What was built
- `backend/data/rss_feeds.json`: 170+ feeds with `{url, lang, region, reliability, category}` per entry
- `bravo_news._load_feeds()`: loads URLs + per-feed reliability α from JSON; falls back to 3 hardcoded feeds in `settings.RSS_FEEDS` if file missing
- Per-feed DST α weights loaded from `"reliability"` field — replaces the old 3-entry hardcoded dict
- Feed coverage: EN wire services (Reuters, AP, BBC), Israeli outlets (Haaretz, ToI, Ynet), ME regional (Al Jazeera, Arab News, Al Arabiya), Turkish (Daily Sabah, AA), Iranian state (IRNA, PressTV — α 0.45), Russian/Ukrainian, defence trade press (Janes, Defense News, Breaking Defense), and 100+ more

---

## Future: Globe.gl 3D View

**Status**: Not implemented
**Priority**: Low — the Deck.gl 2D map is working well; 3D globe adds complexity without clear intelligence value

### What would be needed
- `npm install globe.gl three @types/three`
- `frontend/src/components/GlobeMap.jsx` — Three.js based sphere + atmosphere shader
- Mode toggle between 2D (DeckGLMap) and 3D (GlobeMap) in App.jsx
- Arc layers for trade routes / missile trajectories (stretch goal)

---

## Future: AIS Enhancement

**Status**: Partial — `bravo_marine.py` exists but requires commercial MarineTraffic key

### Free alternatives worth evaluating
- **AISHub** (https://www.aishub.net/) — free tier, crowd-sourced AIS, API key available
- **MarineTraffic free tier** — limited to 100 credits/month; not suitable for continuous polling
- **VesselFinder** — similar to MarineTraffic, limited free tier
- **OpenCPN / gpsd** — receive AIS directly from a hardware SDR dongle (no API, no cost)

If implementing AISHub:
- `bravo_marine.py`: change base URL to `https://data.aishub.net/ws.php`
- Add `AISHUB_API_KEY` to `config.py`
- Filter to Red Sea + Persian Gulf bounding boxes

---

## Future: OpenSky Network (Aircraft)

**Status**: Not needed — ADSB.lol (keyless) already covers military transponders adequately

### Notes
- OpenSky requires account registration and has stricter rate limits than ADSB.lol
- ADSB.lol's `/v2/mil` feed specifically targets military ICAO blocks — better fit for ARES

---

## Future: Additional Panel Components

**Status**: Not implemented
**From original `plan.md`**:

| Panel | Purpose |
|---|---|
| `ConflictPanel.jsx` | Live ACLED/UCDP events with source/category filters |
| `MilitaryPanel.jsx` | Military bases, live flights, vessels in one view |
| `NewsPanel.jsx` | Aggregated news feed with language/region filter |
| `UnrestPanel.jsx` | Protest and civil unrest events |

These would be sidebar tabs or collapsible drawers. The current `EventLog.jsx` / `EventCard.jsx` serves this purpose in a simpler form.

---

## Future: Day/Night Terminator Overlay

**Status**: Not implemented

A solar terminator line (day/night boundary) can be drawn on the map using the current UTC time and a great circle calculation. Useful for judging air-raid timing and satellite pass windows.

Implementation: add a `PolygonLayer` or `PathLayer` in `DeckGLMap.jsx` that computes the terminator boundary every minute using the [SunCalc](https://github.com/mourner/suncalc) library (already a common Deck.gl example).

---

*Project ARES — Alternatives & Future Sources — 2026-03-04*
*ACLED / UCDP / NGA / 170+ RSS feeds: all implemented on `acled` branch*
