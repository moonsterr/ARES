# ARES — Autonomous Reconnaissance & Event Synthesis

A real-time, multi-source OSINT fusion dashboard for monitoring armed conflict. ARES ingests raw signals from eleven independent data sources simultaneously, fuses conflicting reports using Dempster-Shafer PCR5 evidential reasoning, and streams structured intelligence events to a live 2D map — sub-second latency, no manual refresh.

---

## How to run (every time)

### Prerequisites (one-time)

| Requirement | Install |
|---|---|
| Docker + Docker Compose v2 | `docker compose` (not `docker-compose`) |
| Ollama on the **host** (not in Docker) | [ollama.ai](https://ollama.ai) |
| `llama3.1:8b` model | `ollama pull llama3.1:8b` |
| Node.js 20+ | For the frontend |

### Start the system

```bash
# 1. Make sure Ollama is running on the host
ollama serve   # skip if already running as a service

# 2. Start PostgreSQL + backend
cd /path/to/ares
docker compose up postgres backend -d

# 3. Start the frontend (separate terminal)
cd frontend
npm install    # first time only
npm run dev
```

Open `http://localhost:5173`. Backend API at `http://localhost:8000`.

### Stop the system

```bash
docker compose down
```

### Rebuild after code changes

```bash
docker compose up postgres backend -d --build
```

---

## Telegram authentication

Telegram uses your **personal account** (not a bot). The session is stored in `ares_session.session` on the host and mounted into the container automatically.

### First-time auth (or after session expires)

```bash
# Step 1 — request a login code to be sent to your Telegram phone
docker run --rm \
  --env-file .env \
  -v $(pwd)/ares_session.session:/app/ares_session.session \
  -v $(pwd)/auth_telegram.py:/app/auth_telegram.py \
  ares-backend \
  python3 /app/auth_telegram.py

# Step 2 — enter the code + 2FA password you received
docker run --rm \
  --env-file .env \
  -v $(pwd)/ares_session.session:/app/ares_session.session \
  -v $(pwd)/auth_telegram.py:/app/auth_telegram.py \
  ares-backend \
  python3 /app/auth_telegram.py <CODE> <PHONE_CODE_HASH> <2FA_PASSWORD>
```

After success, restart the backend. You only need to do this again if Telegram revokes the session (e.g. you log out all sessions from the app, or the account is flagged).

### Signs the session is dead

The backend logs will show:
```
[ALPHA] SESSION NOT AUTHORIZED — run auth_telegram.py on the host
```
or:
```
[ALPHA] FATAL SESSION ERROR: SessionRevokedError
```

Re-run the auth steps above then `docker compose restart backend`.

### Watched channels (14)

| Channel | Type | Reliability (α) |
|---|---|---|
| `@idfofficial` | IDF official (verified) | 0.90 |
| `@kann_news` | Israeli public broadcaster (Hebrew) | 0.82 |
| `@OSINTdefender` | OSINT breaking news | 0.75 |
| `@intelsky` | IntelSky OSINT | 0.78 |
| `@LBCI_news` | Lebanese TV news | 0.72 |
| `@militarymaps` | Military maps aggregator | 0.72 |
| `@middle_east_spectator` | ME regional commentary (pro-Iran bias declared) | 0.70 |
| `@rybar` | Russian OSINT (Russian language — translated) | 0.65 |
| `@IntelSlava` | Global conflict aggregator | 0.68 |
| `@SabrenNewss` | Iraqi PMF / Iran-aligned (Arabic) | 0.55 |
| `@mehwaralmokawma` | Resistance axis media (Arabic) | 0.58 |
| `@QudsNen` | Palestine/Gaza/Houthi ops | 0.52 |
| `@palinfo` | Hamas-affiliated news (Arabic) | 0.50 |
| `@irna_en` | IRNA Iranian state media | 0.45 |

Your Telegram account must be a **member** of each of these channels. Join them manually from the Telegram app.

---

## Environment setup

Copy `.env.example` to `.env` and fill in credentials. **Never commit `.env` or `ares_session.session`** — both are in `.gitignore`.

```bash
cp .env.example .env
```

### Required credentials

| Variable | Where to get it |
|---|---|
| `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` | [my.telegram.org](https://my.telegram.org) → API Development Tools |
| `TELEGRAM_PHONE` | Your phone number with country code e.g. `+96179184506` |
| `FIRMS_MAP_KEY` | Free — [firms.modaps.eosdis.nasa.gov/api/area](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| `COPERNICUS_USERNAME` + `COPERNICUS_PASSWORD` | Free — [dataspace.copernicus.eu](https://dataspace.copernicus.eu) |
| `ACLED_EMAIL` + `ACLED_PASSWORD` | Free registration — [acleddata.com/register](https://acleddata.com/register/) then request API access from dashboard |

### Optional / commercial

| Variable | Notes |
|---|---|
| `UCDP_ACCESS_TOKEN` | Register at [ucdpapi.pcr.uu.se](https://ucdpapi.pcr.uu.se). Without this, UCDP agent logs 401s silently. |
| `MARINETRAFFIC_API_KEY` | Commercial. Leave blank and set `ENABLE_MARINE=false`. |
| `ENABLE_NGA` | Geo-blocked outside the US. Keep `false` unless behind a US IP. |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Data Sources                     │
│  RSS·170+ feeds  GDELT  Telegram  ADSB.lol          │
│  NASA FIRMS  Sentinel-2  ACLED  UCDP  NGA  AIS      │
└───────────────────┬─────────────────────────────────┘
                    │  async agents (one task each)
┌───────────────────▼─────────────────────────────────┐
│                 Intelligence Pipeline               │
│  fasttext detect → Ollama translate → regex NER     │
│  → global geocoder → DST PCR5 confidence → DB       │
└───────────────────┬─────────────────────────────────┘
                    │  WebSocket broadcast
┌───────────────────▼─────────────────────────────────┐
│            FastAPI + PostgreSQL/PostGIS             │
│       REST API · WebSocket · asyncpg pool           │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│          React + Deck.gl + MapLibre GL              │
│    9 toggleable layers · 12 region presets          │
│    EventLog sidebar · Bel/Pl confidence meter       │
└─────────────────────────────────────────────────────┘
```

---

## Agents

| Code | Agent | Source | Interval | Enabled by default |
|---|---|---|---|---|
| ALPHA | Telegram Monitor | 14 OSINT channels | Real-time | Yes (needs credentials) |
| BRAVO-N | RSS Harvester | 170+ feeds | 5 min | Yes |
| BRAVO-G | GDELT Extractor | GDELT v2 Doc API | 15 min | Yes |
| BRAVO-A | ADS-B Tracker | ADSB.lol `/mil` + radius | 10 sec | Yes |
| BRAVO-B | FIRMS Hotspots | NASA FIRMS thermal CSV | 5 min | Yes (needs key) |
| BRAVO-C | Sentinel-2 Imagery | Copernicus Dataspace | On demand | Yes (needs account) |
| BRAVO-D | WebSDR Radio | WebSDR HFGCS | — | No (stub) |
| BRAVO-E | AIS Vessels | MarineTraffic API | Configurable | No (commercial key) |
| CHARLIE-A | ACLED Conflicts | ACLED REST API (OAuth2) | 1 hour | Yes (needs credentials) |
| CHARLIE-B | UCDP Events | UCDP GED REST API | 2 hours | Yes (needs token) |
| CHARLIE-C | NGA Warnings | NGA MSI broadcast-warn | 30 min | No (US geo-blocked) |

---

## NLP / Translation pipeline

Every message goes through:

1. **Language detection** — fasttext `lid.176.bin` (126MB, ~2ms). Model is downloaded automatically at first build to `backend/data/models/lid.176.bin` and persisted on the host.
2. **Translation** — Ollama (`llama3.1:8b`) translates Hebrew / Arabic / Persian / Russian → English. Ollama must run on the **host** machine for GPU access.
3. **Regex NER** — fast keyword extraction for categories, weapons, units, casualties.
4. **LLM NER** — Ollama extracts structured entities (locations, weapons, units) from translated text.
5. **Geocoding** — fuzzy match against local military base DB (~312 variants), then global Nominatim fallback. No geographic restriction — any location on Earth resolves.
6. **DST confidence** — Dempster-Shafer PCR5 engine assigns `[Belief, Plausibility]` per source reliability weight (α).

---

## Geocoding

Location resolution uses two stages:

1. **Local military DB** (`backend/data/mideast_military_bases.json`) — 312 name variants, fuzzy matched with rapidfuzz. Sub-millisecond.
2. **Nominatim (OpenStreetMap)** — global fallback, 1 req/s rate limit. Resolves any city, country, or landmark worldwide. No bounding box restriction.

---

## Confidence scoring

Every event carries a `[Bel, Pl]` Dempster-Shafer uncertainty interval.

- **Belief (Bel)** — lower bound: minimum probability the event occurred
- **Plausibility (Pl)** — upper bound: maximum probability consistent with evidence
- **Conflict K** — contradiction between sources (0 = full agreement, 1 = full contradiction)

| K value | `fusion_status` | Action |
|---|---|---|
| K < 0.3 | `FUSED` | Sources agree — merge to weighted centroid |
| 0.3 ≤ K < 0.5 | `UNCERTAIN` | Display both candidate locations |
| K ≥ 0.5 | `CONFLICT_ALERT` | Flag for human review |

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/events?limit=N&category=X` | Recent events (default 200) |
| `GET` | `/api/acled-events` | ACLED-sourced events only |
| `GET` | `/api/ucdp-events` | UCDP-sourced events only |
| `GET` | `/api/nga-warnings` | NGA NAVAREA maritime warnings |
| `GET` | `/api/conflict/summary` | Event counts by source and category |
| `GET` | `/api/infrastructure` | All 5 GeoJSON infrastructure layers |
| `GET` | `/api/infrastructure/{layer}` | `cables`, `pipelines`, `ports`, `military_bases`, `nuclear_sites` |
| `GET` | `/api/health` | Agent states + WebSocket client count |
| `GET` | `/api/agents/status` | Per-agent config details |
| `WS`  | `/ws/events` | Real-time event stream (JSON) |

---

## Map layers

| Layer | Default | Data |
|---|---|---|
| Conflict events | On | All ingested events, colour-coded by category |
| Heatmap | Off | Confidence-weighted density |
| ADS-B aircraft | On | Live military aircraft positions + heading |
| AIS vessels | On | Live vessel positions |
| FIRMS hotspots | Off | NASA thermal detections |
| Military bases | Off | 63 installations (GeoJSON) |
| Ports | Off | 29 major shipping ports |
| Pipelines | Off | Oil (red) and gas (green) routes |
| Submarine cables | Off | Fibre optic cable routes |

**Event colours**: verified=green, conflict_alert=purple, air_alert=red, ground_strike=orange, troop_movement=blue, naval_event=cyan, explosion=yellow, casualty_report=pink, unknown=grey

**12 named regions**: Middle East, Levant, Gaza, Persian Gulf, Red Sea, Yemen, Iran, Eastern Mediterranean, North Africa, Horn of Africa, Ukraine, Caucasus

---

## Database schema

PostgreSQL 15 + PostGIS 3.4. Schema is applied automatically on first startup.

**`events`** — primary intelligence store

| Column | Type | Description |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `category` | TEXT | EventCategory value |
| `location` | GEOMETRY(Point, 4326) | WGS84 |
| `location_name` | TEXT | Human-readable place name |
| `confidence` | FLOAT | 0–1 overall confidence |
| `bel` | FLOAT | DST belief lower bound |
| `pl` | FLOAT | DST plausibility upper bound |
| `conflict_k` | FLOAT | DST conflict factor |
| `sources` | TEXT[] | Source identifiers |
| `raw_text` | TEXT | Original text |
| `translation` | TEXT | English translation |
| `entities` | JSONB | Weapons, units, casualties, language |
| `verified` | BOOLEAN | Confirmed by FIRMS hotspot |
| `fusion_status` | TEXT | SINGLE_SOURCE / FUSED / UNCERTAIN / CONFLICT_ALERT |
| `satellite_quicklook` | TEXT | Sentinel-2 image URL |
| `created_at` | TIMESTAMPTZ | UTC |

---

## Project structure

```
ares/
├── docker-compose.yml
├── .env                        # secrets — never commit
├── .env.example                # template
├── ares_session.session        # Telegram auth — never commit (in .gitignore)
├── auth_telegram.py            # one-shot Telegram auth helper
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py               # all settings via pydantic-settings
│   ├── main.py                 # FastAPI app + agent startup
│   ├── database.py             # asyncpg pool + DDL
│   ├── websocket_manager.py    # fan-out broadcast hub
│   ├── agents/
│   │   ├── alpha_harvester.py  # Telegram (Telethon, 14 channels, reconnect loop)
│   │   ├── bravo_adsb.py       # ADS-B aircraft
│   │   ├── bravo_firms.py      # NASA FIRMS hotspots
│   │   ├── bravo_marine.py     # AIS vessels
│   │   ├── bravo_news.py       # RSS feeds
│   │   ├── bravo_sentinel.py   # Copernicus Sentinel-2
│   │   ├── bravo_websdr.py     # WebSDR (stub)
│   │   ├── gdelt_fetcher.py    # GDELT v2
│   │   ├── acled_fetcher.py    # ACLED (OAuth2)
│   │   ├── ucdp_fetcher.py     # UCDP GED
│   │   └── nga_warnings.py     # NGA maritime
│   ├── intelligence/
│   │   ├── llm_pipeline.py     # fasttext + Ollama NLP
│   │   ├── geocoder.py         # fuzzy local DB + global Nominatim
│   │   ├── categorizer.py      # regex event classification
│   │   ├── confidence.py       # DST PCR5 engine
│   │   └── fusion.py           # cross-source correlation
│   ├── models/                 # ConflictIntel, EventCategory, LocationEntity
│   ├── services/               # REST query helpers
│   ├── utils/                  # circuit breaker
│   └── data/
│       ├── models/
│       │   └── lid.176.bin         # fasttext language model (126MB, git-ignored)
│       ├── rss_feeds.json          # 170+ feeds
│       ├── mideast_military_bases.json  # geocoding DB (312 variants)
│       ├── military_bases.geojson
│       ├── nuclear_sites.geojson
│       ├── ports.geojson
│       ├── pipelines.geojson
│       └── cables.geojson
└── frontend/
    ├── Dockerfile
    ├── vite.config.js          # proxies /api + /ws to :8000
    └── src/
        ├── App.jsx
        ├── components/         # DeckGLMap, EventLog, StatusBar, MapPopup, etc.
        ├── config/             # layer config, region presets
        ├── hooks/              # useWebSocket, useEventStore
        ├── services/           # API fetch helpers
        └── utils/              # Supercluster wrapper
```

---

## Troubleshooting

**Telegram harvester not starting / session not authorized**

```
[ALPHA] SESSION NOT AUTHORIZED
```
Run `auth_telegram.py` (see Telegram section above), then restart the backend.

**Telegram session randomly dies after working**

Telegram can revoke sessions if: you log out all devices from the app, the account gets flagged, or the session file gets corrupted. Re-run auth. Session is stored at `./ares_session.session` on the host.

**Translation not working / all messages detected as English**

The fasttext language model is missing. It lives at `backend/data/models/lid.176.bin` (126MB). Download it:
```bash
wget -O backend/data/models/lid.176.bin \
  https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin
```
Then restart the backend. The Dockerfile will also download it automatically on a fresh `--build`.

**Ollama not responding**

Ollama must run on the host, not in Docker. Check:
```bash
ollama serve          # start if not running
ollama list           # confirm llama3.1:8b is listed
curl http://localhost:11434/api/tags   # test it's reachable
```

**Location shows as 'unknown' / no pin on map**

Normal for very vague text (e.g. "sources say"). The geocoder resolves globally — if a recognisable place name appears in the (translated) text, Nominatim will find it anywhere in the world. If the NER extracted no location, the event is stored without coordinates and won't appear as a pin.

**ACLED returns 403 Access Denied**

Your account is authenticated but doesn't have data API access. Log in at [acleddata.com](https://acleddata.com), go to your dashboard, and request API data access. Usually approved same-day.

**GDELT returns 429 Too Many Requests**

Normal on startup after a recent restart. The circuit breaker recovers automatically on the next 15-minute cycle.

**UCDP returns 401 Unauthorized**

UCDP requires an access token. Register at [ucdpapi.pcr.uu.se](https://ucdpapi.pcr.uu.se), set `UCDP_ACCESS_TOKEN=your_token` in `.env`, restart.

**NGA agent fails / times out**

`msi.gs.mil` is geo-blocked outside the US. Set `ENABLE_NGA=false` in `.env`.

**Frontend `vite: not found`**

```bash
cd frontend && npm install
```

**RSS XML parse errors in logs**

Harmless — feedparser handles malformed XML gracefully. Many RSS feed URLs in the list are dead (404/403) — they're skipped automatically and the rest continue.
