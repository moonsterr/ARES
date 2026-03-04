# Alternative Data Sources — Implementation Notes

This document outlines implementation approaches for additional data sources that could be integrated into ARES in the future. These are alternatives/supplements to the current GDELT integration.

---

## ACLED (Armed Conflict Location & Event Data)

**Status**: Not implemented  
**Priority**: Medium (high-value conflict data)

### Overview
ACLED provides real-time conflict event data with geographic coordinates, actor information, and fatality counts for 170+ countries.

### API Details
- **Base URL**: `https://api.acleddata.com/acled/read`
- **Authentication**: Free API token required (register at acleddata.com)
- **Fields**: `event_type`, `sub_event_type`, `country`, `location`, `lat`, `lon`, `fatalities`, `actors`, `source`
- **Polling**: Every 15 minutes recommended

### Implementation

**1. Add config to `backend/config.py`:**
```python
ACLED_API_KEY: str = Field(default="")
ACLED_POLL_INTERVAL: int = Field(default=900)
```

**2. Create agent `backend/agents/acled_fetcher.py`:**
```python
# Pseudocode structure
async def fetch_acled_events():
    params = {
        "key": settings.ACLED_API_KEY,
        "iso": "ISR,PSE,LBN,SYR,IRQ,YEM,IRN,SAU,ARE,KWT,BHR,OMN",  # ME countries
        "event_type": "Battle,Explosion,Violence against civilians",
        "format": "json",
        "limit": 500,
    }
    response = await client.get(f"{ACLED_API_URL}?{urlencode(params)}")
    # Parse and convert to ConflictIntel
    # Geocode if lat/lon missing
```

**3. Add model to `backend/models/event.py`:**
```python
class AcledConflictEvent(BaseModel):
    event_id: str
    event_date: datetime
    event_type: str
    sub_event_type: str
    country: str
    location: str
    lat: float
    lon: float
    fatalities: int
    actors: list[str]
    source: str
```

**4. Wire in `main.py`:**
- Import `poll_acled` agent
- Add to `lifespan()` if `settings.ENABLE_ACLED`

**5. Add frontend service:**
- `frontend/src/services/acled.ts` — fetch via backend `/api/acled-events`
- Add to event store merge logic

### Notes
- ACLED is primarily a historical/analytical dataset with ~2-week lag on real-time data
- Use as supplement to Telegram/RSS, not primary source
- α reliability weight: ~0.75 for cross-referenced events

---

## UCDP (Uppsala Conflict Data Program)

**Status**: Not implemented  
**Priority**: Low (primarily historical data)

### Overview
UCDP provides the GED (Georeferenced Event Dataset) with detailed conflict data. More academically rigorous but less real-time than ACLED.

### API Details
- **Data URL**: `https://ucdp.uu.se/downloads/ged/ged231-full.json` (JSON export)
- **Fields**: `conflict_id`, `event_type`, `country`, `location`, `latitude`, `longitude`, `deaths`
- **Polling**: Weekly or monthly (data is not real-time)

### Implementation Approach

**1. Create `backend/agents/ucdp_fetcher.py`:**
- Fetch full GED JSON (~yearly updates)
- Parse and store to database
- Don't poll frequently — data changes slowly

**2. Notes:**
- Best used as baseline/conflict context, not real-time events
- Good for historical trend analysis
- Less useful for live dashboard but valuable for pattern analysis

---

## NGA Maritime Warnings (NAVAREA)

**Status**: Not implemented  
**Priority**: Low (niche maritime data)

### Overview
National Geospatial-Intelligence Agency publishes NAVAREA broadcast warnings for maritime navigation safety.

### Source
- **URL**: `https://msi.gs.mil/api/publications/broadcast-warn`
- **Format**: XML/JSON
- **Content**: Navigation warnings, hazards, military exercises

### Implementation

**1. Create `backend/agents/nga_warnings.py`:**
```python
async def fetch_naval_warnings():
    # Parse NAVAREA warnings
    # Extract coordinates for hazard zones
    # Convert to events or hotspots
```

**2. Use case:**
- Display military exercise areas on map
- Navigation hazard warnings
- Not conflict-intelligence focused

---

## Future: Expanding RSS Feeds

The current `bravo_news.py` already handles RSS. To expand from ~3 feeds to 170+:

**1. Create `backend/data/rss_feeds.json`:**
```json
{
  "english": [
    "https://www.bbc.com/news/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews"
  ],
  "arabic": [
    "https://www.alarabiya.net/rss",
    "https://www.almayadeen.net/mobile/rss"
  ],
  "russian": [
    "https://meduza.io/rss",
    "https://ria.ru/export/rss2/index.xml"
  ]
}
```

**2. Update config:**
```python
RSS_FEEDS_FILE: str = Field(default="data/rss_feeds.json")
```

**3. Modify `bravo_news.py`:**
- Load feeds from JSON file instead of hardcoded list
- Add language detection to route to appropriate pipeline

---

## Priority Recommendation

1. **ACLED** — Medium priority, high value for conflict event enrichment
2. **RSS Expansion** — Easy win, just configuration
3. **UCDP** — Low priority, mostly historical data
4. **NGA** — Low priority, niche maritime use case

The current GDELT integration provides a good foundation for news-based geo-events. ACLED would be the next highest-value addition for conflict-specific data.
