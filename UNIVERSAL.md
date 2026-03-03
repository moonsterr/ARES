# Project ARES — System Overview

**Autonomous Reconnaissance & Event Synthesis**
Real-time multi-source intelligence fusion dashboard for the Middle East conflict space.

---

## What It Does

ARES ingests raw signals from six independent data sources, fuses conflicting reports using a mathematically rigorous evidential reasoning engine, and streams the results to a 3D globe dashboard in real time. The system answers one question: *given that multiple sources are reporting different things, what actually happened, where, and how confident should we be?*

---

## Architecture at a Glance

```
DATA SOURCES          FUSION ENGINE              PRESENTATION
─────────────         ─────────────              ────────────
Telegram (16 ch) ─┐
ADSB.lol (free)  ─┤   FastAPI Backend            React + CesiumJS
NASA FIRMS       ─┼─► LLM Pipeline   ─► PCR5 ─► 3D Globe
Sentinel-2       ─┤   (Ollama 8B)       Fusion   Event Log Sidebar
WebSDR HFGCS     ─┤                     Engine   Confidence Meters
MarineTraffic    ─┘        │
                           ▼
                    PostgreSQL + PostGIS
                    (spatial event store)
                           │
                    WebSocket broadcast
```

---

## The Four Layers

### 1. Data Ingestion

Two named agents collect raw signals continuously:

**Agent ALPHA — Telegram Harvester**
Monitors 16 public Telegram channels across all sides of the conflict (IDF official, Hamas-affiliated, Houthi, OSINT aggregators, Persian/Arabic/Hebrew sources). Each incoming message passes through language detection and is routed to the LLM pipeline for translation and entity extraction.

**Agent BRAVO — Sensor Fusion**
Four sub-agents run in parallel:
- `BRAVO-A`: Polls ADSB.lol v2 every 10 seconds — merges the global `/mil` feed with a 250 nm point-radius feed centred on Tel Aviv, filters to the Middle East bounding box. No API key required.
- `BRAVO-B`: Polls NASA FIRMS (VIIRS + MODIS satellites) every 5 minutes for thermal hotspots — used as ground-truth verification for strike reports
- `BRAVO-C`: Fetches Sentinel-2 satellite imagery for locations where strikes are confirmed
- `BRAVO-D`: Monitors HFGCS frequencies (8992 kHz, 11175 kHz) via WebSDR for military radio traffic

### 2. Intelligence Processing

Every Telegram message passes through a four-step NLP pipeline:

1. **Language detection** — fasttext (131MB model, 176 languages, <5ms)
2. **Translation** — Ollama llama3.1:8b translates Hebrew/Arabic/Persian to English
3. **Categorization** — Regex triage assigns event category (air alert, ground strike, troop movement, naval event, explosion, casualty report) with confidence score; LLM refines low-confidence cases
4. **Entity extraction** — Named entity recognition pulls location names, weapon systems, military units, and casualty figures

### 3. Confidence Engine (Dempster-Shafer PCR5)

The core mathematical innovation. When multiple sources report the same event from different locations, naive averaging produces a meaningless result. ARES uses Proportional Conflict Redistribution Rule 5 (PCR5) instead:

- Each source gets a reliability weight α (e.g. IDF official = 0.90, Houthi official = 0.48)
- Each report is converted to a Basic Belief Assignment (BBA) over possible locations
- BBAs are combined using PCR5, which computes a **conflict factor K**
- **K < 0.3** → sources agree, emit fused coordinate
- **K 0.3–0.5** → uncertain, display both candidates in amber
- **K ≥ 0.5** → conflict alert, refuse to fuse, display both in purple

Every event on the dashboard shows a `[Bel, Pl]` interval bar — the gap between belief (lower bound) and plausibility (upper bound) visualizes how much uncertainty remains.

**Fusion validation**: When a NASA FIRMS thermal hotspot appears within 5km of a Telegram strike report within 2 hours, the event is promoted to `VERIFIED` (green). This is the system's strongest signal.

### 4. Presentation

- **CesiumJS 3D Globe** — WGS84, dark basemap, Middle East default view. Events rendered as color-coded glowing points that scale with zoom. Click any point for the full intelligence card.
- **Intelligence Feed Sidebar** — Glassmorphism event log, newest first, with category badges, confidence meters, source attribution, and verification status.
- **WebSocket streaming** — Sub-second latency from ingestion to globe. All agent outputs (Telegram events, ADS-B sweeps, FIRMS verifications, satellite imagery) push over a single WebSocket connection.

---

## Source Reliability Matrix

| Source | Type | Reliability α | Notes |
|---|---|---|---|
| IDF official channels | Primary actor | 0.88–0.90 | High reliability, potential omission bias |
| OSINT aggregators | Secondary | 0.78–0.85 | Cross-referenced, generally accurate |
| Israeli media | Secondary | 0.82 | Professional editorial standards |
| Russian OSINT (Rybar) | Secondary | 0.65 | Good raw data, pro-Kremlin framing |
| Lebanese media | Secondary | 0.65–0.68 | Regional, limited verification |
| Iranian-aligned | Secondary | 0.45–0.60 | Known embellishment, cross-verify |
| Hamas/Houthi official | Primary actor | 0.48–0.50 | Self-serving, treat as claims only |
| NASA FIRMS (satellite) | Ground truth | N/A | Used as verifier, not as event source |

---

## Event Categories

| Category | Color | Trigger |
|---|---|---|
| Air Alert | Red | Missile launch, drone strike, air raid siren, interception |
| Ground Strike | Orange | Artillery, mortar, building hit, IED |
| Troop Movement | Blue | Deployment, advance, convoy, reinforcement |
| Naval Event | Cyan | Ship attack, naval blockade, Red Sea incident |
| Explosion | Amber | Unattributed blast reported |
| Casualty Report | Pink | Confirmed death/injury figures |
| VERIFIED | Green | Cross-confirmed by satellite thermal data |
| Conflicted | Purple | K ≥ 0.5, sources directly contradict each other |

---

## Data Flow Summary

```
Telegram message arrives
    → fasttext detects language (2ms)
    → Ollama translates if Hebrew/Arabic/Persian (5–30s)
    → Regex categorizer assigns category + confidence
    → LLM refines if confidence < 0.6
    → Geocoder resolves location names:
        1. Fuzzy match against 63-site local military base DB (<10ms)
        2. Nominatim fallback if no match (async, rate-limited)
    → DST initial BBA computed with channel α weight
    → Event stored in PostGIS
    → Broadcast over WebSocket to all connected frontends
    → Cross-source fusion check against recent events in same area
    → If NASA FIRMS hotspot found within 5km/2h → mark VERIFIED
    → If VERIFIED → queue Sentinel-2 imagery request
    → Satellite quicklook URL attached and re-broadcast
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend framework | React 18 + Vite 5 |
| 3D globe | CesiumJS 1.138+ (WGS84) |
| Styling | Vanilla CSS, glassmorphism |
| Backend | Python 3.12, FastAPI 0.115 |
| ASGI server | Uvicorn |
| Telegram client | Telethon 1.37 |
| Database | PostgreSQL 15 + PostGIS 3.4 |
| DB driver | asyncpg (fully async) |
| HTTP client | httpx (async) |
| Local LLM | Ollama llama3.1:8b (6GB VRAM or 8GB RAM) |
| Language detection | fasttext (131MB binary) |
| Fuzzy geocoding | rapidfuzz |
| Infrastructure | Docker Compose 2.x |

---

## Limitations and Honest Constraints

**MarineTraffic AIS** requires a commercial contract with Kpler. The agent is implemented and disabled by default. Free alternative: AISHub research tier.

**WebSDR HFGCS** audio capture is implemented but Whisper transcription integration is left as a stub — audio files are not persisted, only transcription summaries would be logged.

**Ollama LLM speed** on CPU-only hardware: ~30 seconds per translation request. GPU recommended. The system degrades gracefully — regex categorization still runs at full speed without LLM results.

**Telegram session**: Telethon requires an interactive phone verification on first run. The `.session` file persists authentication thereafter. You must manually join every channel you want to monitor from your Telegram account.

**α weights are heuristic** in v1.0. The plan includes a calibration loop — measuring each channel's track record against FIRMS-verified hotspots and updating α accordingly — but this is not automated in the current implementation.

---

*Project ARES v1.1 — Architecture Revision 1.1 — 2026-03-03 — BRAVO-A migrated from ADS-B Exchange (RapidAPI) to ADSB.lol v2*
