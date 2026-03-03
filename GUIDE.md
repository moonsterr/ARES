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

## Step 2 — Cesium Ion Token (Required — Free)

The 3D globe requires a Cesium Ion token for World Terrain and high-resolution imagery.

1. Go to https://ion.cesium.com/signup and create a free account
2. Log in → click **Access Tokens** in the left sidebar
3. Click **Create token** → give it a name (e.g. "ARES") → use default scopes → **Create**
4. Copy the token string (starts with `eyJ...`)

Add to `.env`:
```
VITE_CESIUM_ION_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Without this token**: The globe will load but without terrain or basemap — you will see a blank sphere. The rest of the system still functions.

---

## Step 3 — Telegram API Credentials (Required for Agent ALPHA)

Agent ALPHA monitors 16 Telegram channels. Without this, you get no text intelligence feed — only ADS-B and sensor data.

1. Go to https://my.telegram.org — log in with your phone number
2. Click **API Development Tools**
3. Fill in the form:
   - App title: `ARES`
   - Short name: `ares_osint`
   - Platform: `Desktop`
   - URL: `http://localhost`
4. Click **Create application**
5. Note your `App api_id` (integer, e.g. `12345678`) and `App api_hash` (32-char hex)

Add to `.env`:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+12025551234
```

**Join the channels**: Telethon can only monitor channels your Telegram account has joined. Open your Telegram app and join each of these channels manually:

```
@idf_updates_english     @israeldefenseforces    @kann_news_eng
@sabereen_news           @palinfo                @intelsky
@militarymaps1           @rybar_english          @middle_east_spectator
@lebanese_breaking_news  @aljumhuriya_lb         @iran_briefing
@irna_fa                 @ansarallaheng          @wartranslated
@osint_collective
```

**First run authentication**: On the very first startup, Telethon will prompt you to enter a verification code sent to your phone. This is normal. After verification, a `.session` file is created and subsequent starts are automatic.

**Legal note**: Only monitor public channels or channels you are authorized to access.

---

## Step 4 — Ollama Local LLM (Required for translation + NER)

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

## Step 5 — NASA FIRMS API Key (Required for fusion validation)

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

## Step 6 — ADSB.lol (No key required — free community API)

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

## Step 7 — Copernicus Data Space (Optional — for satellite imagery)

Provides post-strike Sentinel-2 satellite imagery when events are verified.

1. Go to https://dataspace.copernicus.eu/ and register for a free account
2. Verify your email
3. Log in → go to **User Settings** (top right) → **OAuth Clients**
4. Click **Create Client** → note the `client_id` and `client_secret`

Add to `.env`:
```
COPERNICUS_USERNAME=your@email.com
COPERNICUS_PASSWORD=yourpassword
COPERNICUS_CLIENT_ID=cdse-public
```

If you skip this, verified events will not have satellite imagery attached — everything else works normally.

---

## Step 8 — MarineTraffic AIS (Optional — paid)

For naval vessel tracking in the Red Sea, Persian Gulf, and Mediterranean.

**Reality**: There is no free tier. Options:
- **Kpler/MarineTraffic commercial**: Contact https://www.kpler.com/maritime — request a developer trial
- **AISHub free alternative**: Register at https://www.aishub.net (requires you to share AIS data from your own receiver or use their research tier)

Add to `.env` if you have a key:
```
MARINETRAFFIC_API_KEY=your_token_here
ENABLE_MARINE=true
```

Leave `MARINETRAFFIC_API_KEY` blank and `ENABLE_MARINE=false` to skip — the agent sleeps silently.

---

## Step 9 — fasttext Language Detection Model

This 131MB binary enables fast language detection before routing messages to Ollama.

```bash
# From the project root
mkdir -p ares/backend/data/models
wget -O ares/backend/data/models/lid.176.bin \
  https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```

**If you skip this**: The system falls back to treating all messages as English, which means Arabic and Persian messages will be sent to Ollama for translation without pre-detection. Functionality is preserved but slightly less efficient.

---

## Step 10 — Build the Military Base Database (Optional — improves geocoding)

The repository includes 63 manually-curated military sites. To expand with GeoNames data (~200+ sites):

```bash
cd ares/backend/data/
python3 build_military_db.py
```

This downloads GeoNames military feature data for 16 Middle East countries and merges it with the curated entries. Takes about 2 minutes. Skip this if you want to start immediately — the 63 curated sites cover all major bases.

---

## Step 11 — Start the Database

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

## Step 12 — Install Backend Dependencies

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

## Step 13 — Install Frontend Dependencies

```bash
cd ares/frontend/
npm install
```

---

## Step 14 — Start the Backend

```bash
cd ares/backend/
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

On first start you will see:
```
[ARES] Database initialized
[ARES] 4 agent tasks launched
[Geocoder] Loaded 63 military sites, 312 name variants
[LLM] fasttext model loaded
[ALPHA] Harvester active — watching 16 channels
[BRAVO-A] ADSB.lol: polling every 10s
[BRAVO-B] FIRMS: polling every 5 minutes
```

**Telegram first-run only**: If this is the first time running with Telegram credentials, the terminal will prompt:
```
Please enter your phone (or bot token): +12025551234
Please enter the code you received: 12345
```
Enter the code sent to your Telegram app. This only happens once. The `ares_session` file is created and reused on all subsequent starts.

---

## Step 15 — Start the Frontend

Open a new terminal:

```bash
cd ares/frontend/
npm run dev
```

Open your browser at: **http://localhost:5173**

You should see:
- The CesiumJS 3D globe focused on the Middle East
- The status bar showing `WS LIVE` in green
- `ALPHA` and `BRAVO` agent indicators in the top right
- The intelligence feed sidebar on the right (will populate as events arrive)

---

## Running with Docker Compose (Full Stack)

If you prefer to run everything in containers:

```bash
cd ares/

# Copy your filled-in .env to the ares root (docker-compose reads it from there)
# Then start everything:
docker compose up

# Or detached:
docker compose up -d
docker compose logs -f backend   # tail backend logs
```

**Note**: Ollama must still run on the host — it is not containerized because it needs GPU access. The backend container connects to `host.docker.internal:11434` — adjust `OLLAMA_BASE_URL` in `.env` accordingly:

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
    "alpha_telegram": true,
    "bravo_adsb": true,
    "bravo_firms": true,
    "bravo_sentinel": true,
    "bravo_websdr": false,
    "bravo_marine": false
  },
  "ws_clients": 1
}
```

### Check recent events
```bash
curl http://localhost:8000/api/events?limit=10
```

### Test WebSocket
```bash
# Install wscat: npm install -g wscat
wscat -c ws://localhost:8000/ws/events
# Events will appear as JSON as they are ingested
```

### Check database
```bash
docker exec -it ares_postgres psql -U ares -d ares_db \
  -c "SELECT count(*), category FROM events GROUP BY category ORDER BY count DESC;"
```

---

## Environment Variables Reference

All variables go in `ares/.env`. The backend reads from `backend/.env` if running outside Docker, or from the root `.env` when using Docker Compose.

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_CESIUM_ION_TOKEN` | Yes | — | Cesium Ion access token |
| `TELEGRAM_API_ID` | Yes* | `0` | Integer from my.telegram.org |
| `TELEGRAM_API_HASH` | Yes* | `""` | 32-char hex from my.telegram.org |
| `TELEGRAM_PHONE` | Yes* | `""` | Phone number with country code |
| `DATABASE_URL` | Yes | `postgresql://ares:ares_secret@localhost:5432/ares_db` | asyncpg connection string |
| `OLLAMA_BASE_URL` | Yes | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | Yes | `llama3.1:8b` | Model name |
| `FIRMS_MAP_KEY` | Yes* | `""` | NASA FIRMS API key |
| `ADSB_LOL_BASE_URL` | No | `https://api.adsb.lol/v2` | ADSB.lol v2 base URL (no key needed) |
| `COPERNICUS_USERNAME` | No | `""` | Copernicus Data Space email |
| `COPERNICUS_PASSWORD` | No | `""` | Copernicus Data Space password |
| `COPERNICUS_CLIENT_ID` | No | `cdse-public` | OAuth client ID |
| `MARINETRAFFIC_API_KEY` | No | `""` | Leave blank to disable AIS |
| `BROADCASTIFY_API_KEY` | No | `""` | Leave blank to disable |
| `VITE_WS_URL` | No | `ws://localhost:8000/ws/events` | WebSocket URL for frontend |
| `ENABLE_TELEGRAM` | No | `true` | Toggle ALPHA agent |
| `ENABLE_ADSB` | No | `true` | Toggle BRAVO-A agent |
| `ENABLE_FIRMS` | No | `true` | Toggle BRAVO-B agent |
| `ENABLE_SENTINEL` | No | `true` | Toggle BRAVO-C agent |
| `ENABLE_WEBSDR` | No | `false` | Toggle BRAVO-D agent |
| `ENABLE_MARINE` | No | `false` | Toggle BRAVO-E agent |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

*Required for the named agent to function. The system runs without them but the corresponding agent sleeps.

---

## Troubleshooting

### Globe shows blank black sphere
Your Cesium Ion token is missing or invalid. Check `VITE_CESIUM_ION_TOKEN` in `frontend/.env`.

### "Telegram credentials not configured"
Set `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`. Get them from https://my.telegram.org.

### LLM pipeline is slow / timing out
Ollama is running on CPU. Normal — ~30s per request. If you have an NVIDIA GPU, ensure CUDA drivers are installed and `ollama ps` shows GPU usage. For CPU-only operation, consider using a smaller model: `ollama pull llama3.2:3b` and set `OLLAMA_MODEL=llama3.2:3b`.

### Events appear but no coordinates (location undetermined)
The geocoder could not resolve location names. Either the location was not in the military base DB or Nominatim returned no result (common for obscure neighborhood names). Check `LOG_LEVEL=DEBUG` output for geocoder lines.

### "Cannot access channel — not a member"
You must join each Telegram channel from your personal Telegram account before ARES can monitor it. Open Telegram, search for the channel username, and click Join.

### Database connection refused
The PostgreSQL container is not running or not healthy. Run `docker compose up -d postgres` and wait for `(healthy)` status.

### ADS-B shows 0 aircraft
There may genuinely be no military aircraft in the Middle East bounding box at the moment, or ADSB.lol may be temporarily unreachable. Check the backend logs for `[BRAVO-A]` lines. No API key or rate-limit quota is involved — the API is free and open.

### FloodWait errors in Telegram logs
Telegram is rate-limiting your account. The harvester automatically sleeps for the required duration (shown in the log). This is normal under high message volume. Reduce the channel count if it persists.

---

## Operational Notes

### Updating channel reliability weights
Edit `ares/backend/data/channel_reliability.json`. The harvester loads this at startup. Restart the backend to apply changes. Long-term: build an empirical calibration loop comparing each channel's reports against FIRMS-verified hotspots.

### Adding new Telegram channels
1. Join the channel from your Telegram account
2. Add the username to `WATCHED_CHANNELS` in `backend/agents/alpha_harvester.py`
3. Add an α weight to `CHANNEL_RELIABILITY` in the same file
4. Restart the backend

### Expanding the military base database
Run `python3 ares/backend/data/build_military_db.py` to pull updated GeoNames data. The script merges with existing curated entries without duplicating them.

### Purging old events
```sql
-- Connect to the database
docker exec -it ares_postgres psql -U ares -d ares_db

-- Delete events older than 30 days
DELETE FROM events WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM hotspots WHERE detected_at < NOW() - INTERVAL '7 days';

-- Reclaim space
VACUUM ANALYZE;
```

### Production deployment
For a production server (not covered in depth here):
- Run Nginx as a reverse proxy in front of Uvicorn
- Use `gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app` (keep 1 worker — agents are not multi-process safe)
- Store the Telethon `.session` file in a persistent volume
- Use `systemd` or `supervisor` to manage the backend process
- Consider Redis for WebSocket broadcasting if you need multi-instance deployment

---

## File Locations Quick Reference

```
ares/
├── .env.example              ← copy to .env, fill in keys
├── .env                      ← your private configuration (never commit)
├── docker-compose.yml        ← PostgreSQL + backend + frontend containers
├── GUIDE.md                  ← this file
├── UNIVERSAL.md              ← high-level system overview
├── frontend/
│   ├── .env                  ← frontend-only env vars (Cesium token, WS URL)
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx           ← root component
│       ├── components/       ← MapContainer, EventLog, EventCard, etc.
│       ├── hooks/            ← useWebSocket, useEventStore, useCesiumEntities
│       ├── lib/              ← cesiumColors, formatters
│       └── styles/           ← global.css, globe.css, sidebar.css, cards.css
└── backend/
    ├── main.py               ← FastAPI app entry point
    ├── config.py             ← all settings loaded from .env
    ├── database.py           ← asyncpg + PostGIS schema
    ├── websocket_manager.py  ← broadcast to connected frontends
    ├── requirements.txt      ← pip dependencies
    ├── agents/
    │   ├── alpha_harvester.py   ← Telegram monitor
    │   ├── bravo_adsb.py        ← ADS-B Exchange
    │   ├── bravo_firms.py       ← NASA FIRMS + fusion validation
    │   ├── bravo_sentinel.py    ← Copernicus Sentinel-2
    │   ├── bravo_websdr.py      ← WebSDR HFGCS radio
    │   └── bravo_marine.py      ← MarineTraffic AIS
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
        ├── mideast_military_bases.json  ← 63-site geocoding DB
        ├── channel_reliability.json     ← per-channel α weights
        ├── build_military_db.py         ← GeoNames expansion script
        └── models/
            └── lid.176.bin              ← fasttext model (download separately)
```

---

*Project ARES — Setup Guide v1.1 — 2026-03-03 — Step 6 updated: ADS-B Exchange replaced by ADSB.lol v2 (no API key required)*
