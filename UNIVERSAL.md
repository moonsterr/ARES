# Project ARES — System Overview

**Autonomous Reconnaissance & Event Synthesis**
Real-time multi-source intelligence fusion dashboard for the Middle East conflict space.

---

## What It Does

ARES ingests raw signals from seven independent data sources, fuses conflicting reports using a mathematically rigorous evidential reasoning engine, and streams the results to a 2D map dashboard in real time. The system answers one question: *given that multiple sources are reporting different things, what actually happened, where, and how confident should we be?*

---

## Architecture at a Glance

```
DATA SOURCES          FUSION ENGINE              PRESENTATION
────────────         ─────────────              ────────────
Telegram (16 ch) ─┐
RSS Feeds         ─┤   FastAPI Backend            React + Deck.gl
GDELT News        ─┼─► LLM Pipeline   ─► PCR5 ─► 2D Map (MapLibre)
ADSB.lol (free)  ─┤   (Ollama 8B)       Fusion   Event Log Sidebar
NASA FIRMS       ─┼─►                       Engine   Layer Toggles
Sentinel-2       ─┤        │                 Hotspots Heatmap
MarineTraffic    ─┘        ▼
                     PostgreSQL + PostGIS
                     (spatial event store)
                            │
                     WebSocket broadcast
```

---

## The Four Layers

### 1. Data Ingestion

Seven agents collect raw signals continuously:

**Agent ALPHA — Telegram Harvester** (optional)
Monitors 16 public Telegram channels across all sides of the conflict.

**Agent BRAVO-N — RSS News Harvester**
Polls RSS feeds (Al Jazeera, Jerusalem Post, Middle East Eye) every 5 minutes.

**Agent BRAVO-G — GDELT News Geo-Event Extractor** (NEW)
Polls GDELT v2 API every 15 minutes for conflict-related articles, uses LLM to extract geographic locations.

**Agent BRAVO-A — ADSB.lol**
Polls every 10 seconds — merges global `/mil` feed with regional point-radius feed.

**Agent BRAVO-B — NASA FIRMS**
Polls every 5 minutes for thermal hotspots — used as ground-truth verification.

**Agent BRAVO-C — Sentinel-2**
Fetches satellite imagery for verified events.

**Agent BRAVO-E — MarineTraffic AIS** (optional)
Polls for naval vessels in Red Sea, Persian Gulf, Mediterranean.

---

### 2. Intelligence Processing

Every Telegram/RSS/GDELT message passes through a multi-step NLP pipeline:

1. **Language detection** — fasttext (<5ms)
2. **Translation** — Ollama llama3.1:8b translates Hebrew/Arabic/Persian to English
3. **Categorization** — Regex triage assigns event category
4. **Entity extraction** — LLM pulls location names, weapon systems, military units

---

### 3. Confidence Engine (Dempster-Shafer PCR5)

The core mathematical innovation. When multiple sources report the same event from different locations:

- Each source gets a reliability weight α
- Each report is converted to a Basic Belief Assignment (BBA)
- BBAs are combined using PCR5
- **K < 0.3** → sources agree, emit fused coordinate
- **K 0.3–0.5** → uncertain, display both candidates
- **K ≥ 0.5** → conflict alert, refuse to fuse

Every event shows a `[Bel, Pl]` interval bar — visualizing uncertainty.

---

### 4. Presentation

- **Deck.gl + MapLibre 2D Map** — Dark basemap, Middle East default view
- **Layer System** — Toggle conflicts, aircraft, vessels, heatmap, cables, pipelines, ports, military bases
- **Intelligence Feed Sidebar** — Glassmorphism event log
- **WebSocket streaming** — Sub-second latency

---

## Data Flow Summary

```
News/RSS/GDELT/Telegram message arrives
    ↓
Language detection (fasttext)
    ↓
Translation if needed (Ollama)
    ↓
Regex categorization + LLM refinement
    ↓
Geocoding (local DB → Nominatim)
    ↓
DST initial BBA computed
    ↓
Event stored in PostGIS
    ↓
Broadcast over WebSocket
    ↓
Cross-source fusion check
    ↓
If NASA FIRMS hotspot matches → VERIFIED
    ↓
If VERIFIED → queue Sentinel-2 imagery
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Frontend framework | React 18 + Vite 5 |
| 2D map | Deck.gl 9.x + MapLibre GL |
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

## Limitations

- **Ollama LLM speed** on CPU-only hardware: ~30 seconds per translation
- **Telegram** requires joining channels manually from your account
- **MarineTraffic** requires commercial API key
- **α weights** are heuristic — not yet calibrated automatically

---

*Project ARES v2.0 — Architecture Revision 2.0 — 2026-03-04 — Deck.gl + MapLibre, added GDELT agent*
