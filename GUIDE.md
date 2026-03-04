# Project ARES — Setup & Operations Guide

This guide covers everything required to get a fully operational ARES instance running from scratch, including all external account registrations, API keys, local software installs, first-run procedures, and operational notes.

---

## Prerequisites

Before you start, ensure the following are installed on your host machine:

| Software | Minimum Version | Check |
|---|---|---|
| Docker + Docker Compose | 24.x / 2.x | `docker --version` |
| Node.js | 20.x LTS | `node --version` |
| Python | 3.12+ | `python3 --version` |
| pip | 24+ | `pip --version` |
| Ollama | latest | `ollama --version` |
| wget or curl | any | `wget --version` |

Install Docker: https://docs.docker.com/get-docker/
Install Ollama: https://ollama.com/download (Linux one-liner: `curl -fsSL https://ollama.com/install.sh | sh`)

---

## Step 1 — Clone and configure environment

```bash
# Navigate into the ares/ project directory
cd ares/

# Copy the environment template
cp .env.example .env
```

Open `.env` in your editor. Fill in each section as you complete the steps below. Do not start any services until all required keys are in place.

---

## Step 2 — Database

Start PostgreSQL with Docker:

```bash
docker compose up -d postgres
```

Wait for the health check to pass (~10 seconds):
```bash
docker compose ps
# postgres should show: (healthy)
```

The PostGIS schema (tables, spatial indexes) is created automatically on first connection by the backend.

---

## Step 3 — Ollama Local LLM (Required for translation + NER)

Ollama runs the llama3.1:8b model locally for Hebrew/Arabic/Persian translation and entity extraction.

```bash
# Install Ollama (if not done already)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model (~4.7GB download)
ollama pull llama3.1:8b

# Verify it works
ollama run llama3.1:8b "Translate to English: שלום עולם"
# Expected output: "Hello world"

# Start the Ollama service (it runs on port 11434)
ollama serve
```

Ollama should start automatically as a system service after install. Check with `ollama ps`.

**Hardware requirements**:
- GPU (NVIDIA/AMD with 6GB+ VRAM): ~1–3 seconds per translation
- CPU only (8GB+ RAM): ~20–45 seconds per translation — functional but slow under high message volume

Add to `.env` (defaults are fine if running locally):
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Step 4 — NASA FIRMS API Key (Required for fusion validation)

FIRMS provides the thermal satellite data that promotes strike reports to VERIFIED status.

1. Go to https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. Fill in the registration form — free, instant, no approval needed
3. Your MAP_KEY is shown immediately and emailed to you

Add to `.env`:
```
FIRMS_MAP_KEY=your_32_character_key_here
```

**Rate limits**: 5,000 transactions per 10-minute window. ARES polls every 5 minutes — well within limits.

---

## Step 5 — ADSB.lol (No key required)

Tracks military aircraft in real time using the free ADSB.lol v2 API.
No account, no API key, and no payment are required.

Agent BRAVO-A queries two endpoints every 10 seconds:
- **Global military feed** — `https://api.adsb.lol/v2/mil`
- **Regional feed** — `https://api.adsb.lol/v2/point/32.0/34.8/250` (250 nm radius around Tel Aviv)

Both results are merged, de-duplicated by ICAO hex, and filtered to the Middle East bounding box.

The default value in `.env` is already correct:
```
ADSB_LOL_BASE_URL=https://api.adsb.lol/v2
```

---

## Step 6 — GDELT (No key required)

GDELT provides global news articles processed to extract conflict-related events.
No API key required — uses the free GDELT v2 Doc API.

Agent BRAVO-G polls every 15 minutes. Default config:
```
ENABLE_GDELT=true
GDELT_POLL_INTERVAL=900
```

---

## Step 7 — UCDP (No key required)

UCDP (Uppsala Conflict Data Program) provides georeferenced conflict event data.
No API key required — fully open REST API.

Agent CHARLIE-B polls every 2 hours. Default config:
```
ENABLE_UCDP=true
UCDP_POLL_INTERVAL=7200
UCDP_LOOKBACK_DAYS=30
```

---

## Step 8 — NGA Maritime Warnings (No key required)

NGA publishes NAVAREA maritime warnings covering military exercises and hazards in the Persian Gulf, Red Sea, and surrounding waters.
No API key required — official US government public data.

Agent CHARLIE-C polls every 30 minutes. Default config:
```
ENABLE_NGA=true
NGA_POLL_INTERVAL=1800
```

---

## Step 9 — ACLED (Optional — requires free registration)

ACLED provides real-time armed conflict events for 170+ countries with lat/lon, actors, and fatality counts.

1. Register free at https://acleddata.com/register/ (instant approval)
2. Both your API key AND your registration email are required per API request

Add to `.env`:
```
ACLED_API_KEY=your_api_key_here
ACLED_EMAIL=your@email.com
ENABLE_ACLED=true
```

**Note**: ACLED is disabled by default (`ENABLE_ACLED=false`). UCDP and GDELT cover similar ground and require no credentials.

---

## Step 10 — fasttext Language Detection Model (Optional)

This 131MB binary enables fast language detection before routing messages to Ollama.

```bash
mkdir -p backend/data/models
wget -O backend/data/models/lid.176.bin \
  https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```

**If you skip this**: The system falls back to treating all messages as English. Arabic and Persian messages will be sent to Ollama for translation without pre-detection. Functionality is preserved but slightly less efficient.

---

## Step 11 — Install Backend Dependencies

```bash
cd backend/
pip install -r requirements.txt
```

Recommended: use a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Step 12 — Install Frontend Dependencies

```bash
cd frontend/
npm install
```

---

## Step 13 — Start the Backend

```bash
cd backend/
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On first start you will see logs like:
```
[ARES] Database initialized
[ARES] 7 agent tasks launched
[Geocoder] Loaded 63 military sites, 312 name variants
[BRAVO-A] ADSB.lol: polling every 10s
[BRAVO-B] FIRMS: polling every 5 minutes
[BRAVO-G] GDELT: polling every 15 minutes
[BRAVO-N] RSS: loaded 170 feeds from rss_feeds.json, polling every 5 minutes
[CHARLIE-B] UCDP: polling every 2 hours, lookback 30 days
[CHARLIE-C] NGA: polling every 30 minutes
```

---

## Step 14 — Start the Frontend

Open a new terminal:

```bash
cd frontend/
npm run dev
```

Open your browser at: **http://localhost:5173**

You should see:
- The Deck.gl 2D map focused on the Middle East
- The status bar showing `WS LIVE` in green
- Layer toggle panel accessible from the top-right button
- The intelligence feed sidebar on the right (populates as events arrive)
- The collapsible MapLegend in the bottom-left corner

---

## Running with Docker Compose (Full Stack)

If you prefer to run everything in containers:

```bash
docker compose up
```

**Note**: Ollama must still run on the host — it is not containerized because it needs GPU access. The backend container connects to it via `host.docker.internal:11434`.

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, add to the backend service in `docker-compose.yml`:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

---

## Optional: Telegram Credentials

If you want to monitor Telegram channels (Agent ALPHA):

1. Go to https://my.telegram.org — log in with your phone number
2. Click **API Development Tools**
3. Fill in the form (App title: `ARES`, Platform: `Desktop`)
4. Note your `App api_id` and `App api_hash`

Add to `.env`:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+12025551234
ENABLE_TELEGRAM=true
```

You must join each monitored Telegram channel from your account before ARES can read it.

---

## Optional: Copernicus Sentinel-2

For post-strike satellite imagery on verified events:

1. Register free at https://dataspace.copernicus.eu/
2. Add to `.env`:
```
COPERNICUS_USERNAME=your@email.com
COPERNICUS_PASSWORD=yourpassword
ENABLE_SENTINEL=true
```

---

## Verifying the System is Working

### Check agent health
```bash
curl http://localhost:8000/api/health
```
Expected:
```json
{
  "status": "operational",
  "version": "1.0.0",
  "agents": {
    "alpha_telegram":  false,
    "bravo_news":      true,
    "bravo_gdelt":     true,
    "bravo_adsb":      true,
    "bravo_firms":     true,
    "bravo_sentinel":  true,
    "bravo_websdr":    false,
    "bravo_marine":    false,
    "charlie_acled":   false,
    "charlie_ucdp":    true,
    "charlie_nga":     true
  },
  "ws_clients": 1
}
```

### Check agent status details
```bash
curl http://localhost:8000/api/agents/status
```

### Check infrastructure layers
```bash
curl http://localhost:8000/api/infrastructure | python3 -m json.tool | head -30
```

### Check conflict summary
```bash
curl http://localhost:8000/api/conflict/summary
```

### Check recent events
```bash
curl "http://localhost:8000/api/events?limit=10"
```

### Test WebSocket
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws/events
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://ares:ares_secret@localhost:5432/ares_db` | asyncpg connection string |
| `OLLAMA_BASE_URL` | Yes | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | Yes | `llama3.1:8b` | Model name |
| `FIRMS_MAP_KEY` | Yes* | `""` | NASA FIRMS API key |
| `ADSB_LOL_BASE_URL` | No | `https://api.adsb.lol/v2` | ADSB.lol v2 base URL |
| `ACLED_API_KEY` | Yes* | `""` | ACLED API key |
| `ACLED_EMAIL` | Yes* | `""` | ACLED registration email |
| `ACLED_POLL_INTERVAL` | No | `3600` | Seconds between ACLED polls |
| `ACLED_RELIABILITY_ALPHA` | No | `0.80` | DST source weight |
| `UCDP_BASE_URL` | No | (see .env.example) | UCDP GED API URL |
| `UCDP_POLL_INTERVAL` | No | `7200` | Seconds between UCDP polls |
| `UCDP_LOOKBACK_DAYS` | No | `30` | Days of history to query |
| `UCDP_RELIABILITY_ALPHA` | No | `0.78` | DST source weight |
| `NGA_BASE_URL` | No | (see .env.example) | NGA MSI API URL |
| `NGA_POLL_INTERVAL` | No | `1800` | Seconds between NGA polls |
| `GDELT_POLL_INTERVAL` | No | `900` | Seconds between GDELT polls |
| `ENABLE_TELEGRAM` | No | `false` | Toggle ALPHA agent |
| `ENABLE_RSS` | No | `true` | Toggle BRAVO-N RSS agent (170+ feeds) |
| `ENABLE_GDELT` | No | `true` | Toggle BRAVO-G GDELT agent |
| `ENABLE_ADSB` | No | `true` | Toggle BRAVO-A agent |
| `ENABLE_FIRMS` | No | `true` | Toggle BRAVO-B agent |
| `ENABLE_SENTINEL` | No | `true` | Toggle BRAVO-C agent |
| `ENABLE_WEBSDR` | No | `false` | Toggle BRAVO-D agent |
| `ENABLE_MARINE` | No | `false` | Toggle BRAVO-E agent |
| `ENABLE_ACLED` | No | `false` | Toggle CHARLIE-A agent (needs key) |
| `ENABLE_UCDP` | No | `true` | Toggle CHARLIE-B agent |
| `ENABLE_NGA` | No | `true` | Toggle CHARLIE-C agent |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

*Required for the named agent to function. The system runs without them but the corresponding agent sleeps idle.

---

## Troubleshooting

### Map doesn't load
Make sure you ran `npm install` in the `frontend/` directory. This installs `deck.gl`, `maplibre-gl`, and `supercluster`.

### LLM pipeline is slow / timing out
Ollama is running on CPU. Normal — ~30s per request. If you have an NVIDIA GPU, ensure CUDA drivers are installed and `ollama ps` shows GPU usage.

### Events appear but no coordinates
The geocoder could not resolve location names. Check `LOG_LEVEL=DEBUG` output for `[Geocoder]` lines.

### Database connection refused
The PostgreSQL container is not running or not healthy. Run `docker compose up -d postgres` and wait for `(healthy)`.

### ADS-B shows 0 aircraft
There may genuinely be no military aircraft in the Middle East bounding box. Check backend logs for `[BRAVO-A]` lines — the agent itself may report no results from the API.

### ACLED agent sleeps immediately
Either `ACLED_API_KEY` or `ACLED_EMAIL` is not set in `.env`, or `ENABLE_ACLED=false`.

### Circuit breaker tripped
If a remote API is down, the circuit breaker opens after 3 consecutive failures and will not retry for 5–10 minutes. Check backend logs for `CB=open` lines. The state resets automatically.

---

## File Locations Quick Reference

```
ares/
├── .env.example              ← copy to .env, fill in keys
├── .env                      ← your private configuration (never commit)
├── docker-compose.yml        ← PostgreSQL + backend + frontend containers
├── GUIDE.md                  ← this file
├── UNIVERSAL.md              ← high-level system overview
├── technical.md              ← technical documentation
├── alternatives.md           ← completed — all items implemented
├── plan.md                   ← original feature plan (mostly complete)
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── DeckGLMap.jsx     ← Deck.gl 2D map (MapLibre basemap)
│       │   ├── MapPopup.jsx      ← click popup for all layers
│       │   ├── MapLegend.jsx     ← collapsible layer legend
│       │   ├── EventLog.jsx
│       │   ├── EventCard.jsx
│       │   └── StatusBar.jsx
│       ├── config/
│       │   ├── mapLayers.js      ← layer definitions + colour config
│       │   └── regions.js        ← 12 named region view-states
│       ├── hooks/
│       │   ├── useWebSocket.js
│       │   └── useEventStore.js
│       ├── services/
│       │   ├── infrastructure.js ← fetchInfrastructure()
│       │   ├── acled.js          ← fetchAcledEvents()
│       │   └── ucdp.js           ← fetchUcdpEvents(), fetchNgaWarnings(), fetchConflictSummary()
│       └── utils/
│           └── clustering.js     ← Supercluster wrapper
└── backend/
    ├── main.py               ← FastAPI app + all endpoints
    ├── config.py             ← all settings loaded from .env
    ├── database.py           ← asyncpg + PostGIS schema
    ├── websocket_manager.py  ← broadcast to connected frontends
    ├── requirements.txt      ← pip dependencies
    ├── agents/
    │   ├── alpha_harvester.py    ← Telegram monitor (ALPHA)
    │   ├── bravo_adsb.py         ← ADS-B military aircraft (BRAVO-A)
    │   ├── bravo_firms.py        ← NASA FIRMS thermal sensor (BRAVO-B)
    │   ├── bravo_sentinel.py     ← Copernicus Sentinel-2 imagery (BRAVO-C)
    │   ├── bravo_websdr.py       ← WebSDR HFGCS radio stub (BRAVO-D)
    │   ├── bravo_marine.py       ← MarineTraffic AIS (BRAVO-E)
    │   ├── bravo_news.py         ← RSS news (170+ feeds from JSON) (BRAVO-N)
    │   ├── gdelt_fetcher.py      ← GDELT v2 news geo-events (BRAVO-G)
    │   ├── acled_fetcher.py      ← ACLED conflict events (CHARLIE-A)
    │   ├── ucdp_fetcher.py       ← UCDP GED events (CHARLIE-B)
    │   └── nga_warnings.py       ← NGA NAVAREA maritime warnings (CHARLIE-C)
    ├── intelligence/
    │   ├── confidence.py         ← Dempster-Shafer PCR5 engine
    │   ├── llm_pipeline.py       ← fasttext + Ollama NLP
    │   ├── geocoder.py           ← fuzzy local DB + Nominatim
    │   ├── categorizer.py        ← regex event classification
    │   └── fusion.py             ← cross-source correlation
    ├── models/
    │   └── event.py              ← ConflictIntel Pydantic schema
    ├── services/
    │   └── conflict_service.py   ← unified conflict query + summary
    ├── utils/
    │   └── circuit_breaker.py    ← async circuit breaker (all external APIs)
    └── data/
        ├── rss_feeds.json            ← 170+ curated feeds with reliability weights
        ├── cables.geojson            ← submarine fiber optic cables
        ├── pipelines.geojson         ← oil/gas pipelines
        ├── ports.geojson             ← major shipping ports
        ├── military_bases.geojson    ← 63 military installations
        ├── nuclear_sites.geojson     ← 15 verified nuclear facilities
        ├── mideast_military_bases.json
        └── channel_reliability.json
```

---

*Project ARES — Setup Guide v3.0 — 2026-03-04 — Added ACLED / UCDP / NGA agents, circuit breaker, conflict service, nuclear sites, MapLegend, clustering, regions*
