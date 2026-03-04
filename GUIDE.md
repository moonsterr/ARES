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

Open `.env` in your editor. You will fill in each section as you complete the steps below. Do not start any services until all required keys are in place.

---

## Step 2 — Database

Start PostgreSQL with Docker:

```bash
cd ares/
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

FIRMS provides the thermal satellite data that promotes Telegram strike reports to VERIFIED status.

1. Go to https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. Fill in the registration form — free, instant, no approval needed
3. Your MAP_KEY is shown immediately and emailed to you

Add to `.env`:
```
FIRMS_MAP_KEY=your_32_character_key_here
```

**Rate limits**: 5,000 transactions per 10-minute window. ARES polls every 5 minutes — well within limits.

---

## Step 5 — ADSB.lol (No key required — free community API)

Tracks military aircraft in the Middle East in real time using the free ADSB.lol v2 API.
No account, no API key, and no payment are required.

Agent BRAVO-A queries two endpoints every 10 seconds:
- **Global military feed** — `https://api.adsb.lol/v2/mil` (all military transponders worldwide)
- **Regional feed** — `https://api.adsb.lol/v2/point/32.0/34.8/250` (250 nm radius around Tel Aviv for higher-precision Middle East coverage)

Both results are merged, de-duplicated by ICAO hex, and filtered to the ME bounding box before storage and broadcast.

The default value in `.env` is already correct:
```
ADSB_LOL_BASE_URL=https://api.adsb.lol/v2
```

**Rate limiting**: ADSB.lol is currently un-rated, but Agent BRAVO-A enforces a 10-second cool-down between poll cycles as a good-citizen policy. Do not remove this sleep.

---

## Step 6 — GDELT (No key required — free news API)

GDELT provides global news articles that are processed to extract conflict-related events.
No API key required — uses the free GDELT v2 Doc API.

Agent BRAVO-G polls every 15 minutes:
- Queries for conflict-related keywords (military, strike, attack, war, etc.)
- Uses LLM to extract locations and categorize events
- Creates conflict events from news headlines

Default config in `.env`:
```
GDELT_BASE_URL=https://api.gdeltproject.org/api/v2/doc/doc
GDELT_POLL_INTERVAL=900
ENABLE_GDELT=true
```

---

## Step 7 — fasttext Language Detection Model (Optional)

This 131MB binary enables fast language detection before routing messages to Ollama.

```bash
# From the project root
mkdir -p ares/backend/data/models
wget -O ares/backend/data/models/lid.176.bin \
  https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```

**If you skip this**: The system falls back to treating all messages as English, which means Arabic and Persian messages will be sent to Ollama for translation without pre-detection. Functionality is preserved but slightly less efficient.

---

## Step 8 — Install Backend Dependencies

```bash
cd ares/backend/
pip install -r requirements.txt
```

This installs FastAPI, Telethon, asyncpg, httpx, pydantic, fasttext-wheel, rapidfuzz, and all other dependencies. Use a virtual environment if preferred:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Step 9 — Install Frontend Dependencies

```bash
cd ares/frontend/
npm install
```

---

## Step 10 — Start the Backend

```bash
cd ares/backend/
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On first start you will see:
```
[ARES] Database initialized
[ARES] 5 agent tasks launched
[Geocoder] Loaded 63 military sites, 312 name variants
[LLM] fasttext model loaded
[BRAVO-A] ADSB.lol: polling every 10s
[BRAVO-B] FIRMS: polling every 5 minutes
[BRAVO-G] GDELT: polling every 15 minutes
[BRAVO-N] RSS: polling every 5 minutes
```

---

## Step 11 — Start the Frontend

Open a new terminal:

```bash
cd ares/frontend/
npm run dev
```

Open your browser at: **http://localhost:5173**

You should see:
- The Deck.gl 2D map focused on the Middle East
- The status bar showing `WS LIVE` in green
- Layer toggle button in top-right corner
- The intelligence feed sidebar on the right (will populate as events arrive)

---

## Optional: Telegram Credentials

If you want to monitor Telegram channels (Agent ALPHA):

1. Go to https://my.telegram.org — log in with your phone number
2. Click **API Development Tools**
3. Fill in the form:
   - App title: `ARES`
   - Short name: `ares_osint`
   - Platform: `Desktop`
   - URL: `http://localhost`
4. Click **Create application**
5. Note your `App api_id` and `App api_hash`

Add to `.env`:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+12025551234
ENABLE_TELEGRAM=true
```

**Join the channels**: You must join each channel from your Telegram account before ARES can monitor it.

---

## Optional: Copernicus Sentinel-2

For satellite imagery on verified events:

1. Go to https://dataspace.copernicus.eu/ and register
2. Add credentials to `.env`:
```
COPERNICUS_USERNAME=your@email.com
COPERNICUS_PASSWORD=yourpassword
ENABLE_SENTINEL=true
```

---

## Running with Docker Compose (Full Stack)

If you prefer to run everything in containers:

```bash
cd ares/
docker compose up
```

**Note**: Ollama must still run on the host — it is not containerized because it needs GPU access. The backend container connects to `host.docker.internal:11434`:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, add to the backend service in `docker-compose.yml`:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
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
    "alpha_telegram": false,
    "bravo_news": true,
    "bravo_gdelt": true,
    "bravo_adsb": true,
    "bravo_firms": true,
    "bravo_sentinel": true,
    "bravo_websdr": false,
    "bravo_marine": false
  },
  "ws_clients": 1
}
```

### Check infrastructure layers
```bash
curl http://localhost:8000/api/infrastructure
```

### Check recent events
```bash
curl http://localhost:8000/api/events?limit=10
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
| `GDELT_BASE_URL` | No | `https://api.gdeltproject.org/api/v2/doc/doc` | GDELT v2 API |
| `GDELT_POLL_INTERVAL` | No | `900` | Seconds between GDELT polls |
| `ENABLE_TELEGRAM` | No | `false` | Toggle ALPHA agent |
| `ENABLE_RSS` | No | `true` | Toggle BRAVO-N RSS agent |
| `ENABLE_GDELT` | No | `true` | Toggle BRAVO-G GDELT agent |
| `ENABLE_ADSB` | No | `true` | Toggle BRAVO-A agent |
| `ENABLE_FIRMS` | No | `true` | Toggle BRAVO-B agent |
| `ENABLE_SENTINEL` | No | `true` | Toggle BRAVO-C agent |
| `ENABLE_WEBSDR` | No | `false` | Toggle BRAVO-D agent |
| `ENABLE_MARINE` | No | `false` | Toggle BRAVO-E agent |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

*Required for the named agent to function. The system runs without them but the corresponding agent sleeps.

---

## Troubleshooting

### Map doesn't load
Make sure you ran `npm install` in the frontend directory to get deck.gl and maplibre-gl dependencies.

### LLM pipeline is slow / timing out
Ollama is running on CPU. Normal — ~30s per request. If you have an NVIDIA GPU, ensure CUDA drivers are installed and `ollama ps` shows GPU usage.

### Events appear but no coordinates
The geocoder could not resolve location names. Check `LOG_LEVEL=DEBUG` output for geocoder lines.

### Database connection refused
The PostgreSQL container is not running or not healthy. Run `docker compose up -d postgres`.

### ADS-B shows 0 aircraft
There may genuinely be no military aircraft in the Middle East bounding box at the moment. Check the backend logs for `[BRAVO-A]` lines.

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
├── alternatives.md           ← future data source implementation notes
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx           ← root component
│       ├── components/
│       │   ├── DeckGLMap.jsx     ← NEW: Deck.gl 2D map
│       │   ├── MapPopup.jsx      ← NEW: click popup
│       │   ├── MapContainer.jsx  ← legacy (Cesium)
│       │   ├── EventLog.jsx
│       │   ├── EventCard.jsx
│       │   └── StatusBar.jsx
│       ├── config/
│       │   └── mapLayers.js     ← NEW: layer definitions
│       ├── hooks/
│       │   ├── useWebSocket.js
│       │   └── useEventStore.js
│       └── services/
│           └── infrastructure.js ← NEW
└── backend/
    ├── main.py               ← FastAPI app entry point
    ├── config.py             ← all settings loaded from .env
    ├── database.py           ← asyncpg + PostGIS schema
    ├── websocket_manager.py  ← broadcast to connected frontends
    ├── requirements.txt      ← pip dependencies
    ├── agents/
    │   ├── alpha_harvester.py   ← Telegram monitor
    │   ├── bravo_adsb.py        ← ADS-B
    │   ├── bravo_firms.py       ← NASA FIRMS
    │   ├── bravo_sentinel.py    ← Copernicus Sentinel-2
    │   ├── bravo_websdr.py      ← WebSDR HFGCS radio
    │   ├── bravo_marine.py      ← MarineTraffic AIS
    │   ├── bravo_news.py        ← RSS news
    │   └── gdelt_fetcher.py     ← NEW: GDELT news
    ├── intelligence/
    │   ├── confidence.py        ← Dempster-Shafer PCR5 engine
    │   ├── llm_pipeline.py      ← fasttext + Ollama NLP
    │   ├── geocoder.py          ← fuzzy local DB + Nominatim
    │   ├── categorizer.py       ← regex event classification
    │   └── fusion.py            ← cross-source correlation
    ├── models/
    │   ├── event.py             ← ConflictIntel Pydantic schema
    │   ├── aircraft.py
    │   ├── vessel.py
    │   └── hotspot.py
    └── data/
        ├── cables.geojson           ← NEW: submarine cables
        ├── pipelines.geojson        ← NEW: oil/gas pipelines
        ├── ports.geojson            ← NEW: shipping ports
        ├── military_bases.geojson   ← NEW: military bases
        ├── mideast_military_bases.json
        ├── channel_reliability.json
        └── build_military_db.py
```

---

*Project ARES — Setup Guide v2.0 — 2026-03-04 — Updated: CesiumJS replaced by Deck.gl + MapLibre, added GDELT agent*
