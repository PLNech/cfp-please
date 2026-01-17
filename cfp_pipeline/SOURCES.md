# CFP Data Sources

This document tracks all data sources used in the CFP aggregation pipeline.

## Active Sources

### 1. CallingAllPapers (Primary)
- **URL:** `https://api.callingallpapers.com/v1/cfp`
- **Type:** REST API (JSON)
- **Parser:** `sources/callingallpapers.py`
- **Coverage:** Tech conferences worldwide (aggregates from confs.tech, Sessionize, PaperCall, joind.in)
- **Fields:** name, description, dates, location, geoloc, tags
- **Quality:** High (already aggregated/deduplicated)
- **Rate limit:** None documented, cache 6h

### 2. confs.tech
- **URL:** `https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences/2026/{topic}.json`
- **Type:** GitHub JSON files by topic
- **Parser:** `sources/confstech.py`
- **Coverage:** Developer conferences, organized by technology (javascript, python, devops, etc.)
- **Fields:** name, url, dates, location, cfpUrl, cfpEndDate
- **Quality:** Medium (community maintained, sparse CFP data)
- **Topics:** 25 files including javascript, python, rust, devops, security, etc.
- **Rate limit:** GitHub API limits, cache 6h

### 3. AI Deadlines (aideadlin.es)
- **URL:** `https://raw.githubusercontent.com/paperswithcode/ai-deadlines/gh-pages/_data/conferences.yml`
- **Type:** GitHub YAML
- **Parser:** `sources/aideadlines.py`
- **Coverage:** ML/AI academic conferences (NeurIPS, ICML, CVPR, etc.)
- **Fields:** title, year, deadline, place, h-index (!), abstract_deadline
- **Quality:** High (curated, includes h-index quality metric)
- **Subjects:** ML, CV, NLP, Robotics, Data Mining, HCI, etc.
- **Rate limit:** GitHub API limits, cache 12h
- **Note:** Data is typically for current/next year, deadlines often 6-12 months ahead

### 4. developers.events (scraly/developers-conferences-agenda)
- **URL:** `https://developers.events/all-cfps.json`
- **Type:** REST API (JSON)
- **Parser:** `sources/developerevents.py`
- **Coverage:** Developer conferences worldwide (~333 open CFPs!)
- **Fields:**
  ```json
  {
    "link": "CFP submission URL",
    "until": "Human readable deadline",
    "untilDate": 1737158400000,  // Unix ms
    "conf": {
      "name": "Conference Name",
      "date": [1737158400000, 1737244800000],  // start/end in ms
      "hyperlink": "https://conf.example.com",
      "location": "Paris (France)"
    }
  }
  ```
- **Quality:** High (community-curated, active maintenance)
- **GitHub:** `https://github.com/scraly/developers-conferences-agenda`
- **Rate limit:** None documented, cache 6h

### 5. CFPlist
- **URL:** `https://cfplist.herokuapp.com/api/cfps`
- **Type:** REST API (JSON)
- **Parser:** Integrated via `collect-urls` CLI command
- **Coverage:** Tech conferences (~133 CFPs)
- **Fields:**
  ```json
  {
    "conferenceName": "Conference Name",
    "link": "https://conf.example.com",
    "cfpLink": "https://cfp.example.com/submit",
    "cfpDeadline": "2026-02-15",
    "eventDate": "March 15-17, 2026",
    "location": "San Francisco, CA"
  }
  ```
- **Quality:** Medium (community-curated)
- **Rate limit:** None documented

## Planned Sources

### 6. EasyChair CFP
- **URL:** `https://easychair.org/cfp/area.cgi?area=18` (area 18 = CS)
- **Type:** HTML scrape (table-based)
- **Status:** TODO
- **Coverage:** Academic conferences across all fields (~379 CFPs)
- **Fields:** acronym, name, location, deadline, start date, topics
- **Notes:** Pagination via JS (`Tab.tables['ec:table2']`), may need browser automation

### 7. dev.events
- **URL:** `https://dev.events/EU/FR/tech` (filterable by continent/country/topic)
- **Type:** HTML with Schema.org structured data
- **Status:** TODO (no CFP deadline data in RSS feed)
- **Coverage:** 53 tech conferences for France alone, global coverage
- **Fields:** name, dates, location, attendance mode (offline/online/mixed)
- **Notes:** Uses HTMX, embeds Schema.org `EducationEvent` markup

### 8. WikiCFP
- **URL:** `http://www.wikicfp.com/cfp/`
- **Type:** HTML scrape
- **Status:** TODO (site currently unreachable - ECONNREFUSED)
- **Coverage:** Academic conferences, searchable by topic
- **Fields:** name, dates, location, deadline, categories

### 9. PaperCall.io (Direct)
- **URL:** `https://www.papercall.io/events?cfps-scope=open`
- **Type:** HTML scrape
- **Status:** Low priority (most data already in CallingAllPapers)
- **Coverage:** Tech conferences, speaker-focused platform

### 10. Sessionize (Direct)
- **URL:** Various endpoints
- **Type:** HTML/API
- **Status:** Low priority (most data already in CallingAllPapers)
- **Coverage:** Tech conferences, major events like CNCF

## Quality Heuristics for Deduplication

When merging records from multiple sources, prefer records with:
1. **h-index** available (AI Deadlines provides this)
2. **Description** present
3. **Geolocation** coordinates
4. **CFP URL** (direct submission link)
5. **Topic tags** (more = better)

Sources are prioritized: CallingAllPapers > AI Deadlines > confs.tech

## URL → CFP Extraction Pipeline

The pipeline now supports extracting CFP metadata directly from conference URLs, enabling any URL source to be enriched with structured data.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    URL PROVIDERS (dumb)                     │
├─────────────────────────────────────────────────────────────┤
│  developers.events │ CallingAllPapers │ CFPlist │ confs.tech│
│       (327)        │      (136)       │  (133)  │    (1)    │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              URL → CFP EXTRACTOR (smart)                    │
├─────────────────────────────────────────────────────────────┤
│  1. Fetch HTML (httpx + Firefox UA + retries)               │
│  2. Detect SPA shell → fallback to Playwright Firefox       │
│  3. Dismiss cookie consent banners (GDPR)                   │
│  4. Extract via (in order of confidence):                   │
│     - Platform-specific (Sessionize, PaperCall, Eventbrite) │
│     - Schema.org JSON-LD (Event, EducationEvent)            │
│     - OpenGraph meta tags                                   │
│     - HTML heuristics (deadline patterns, CFP keywords)     │
│  5. Capture full text for search indexing                   │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Dedupe + Normalize + Algolia Index             │
└─────────────────────────────────────────────────────────────┘
```

### Extractors

Located in `extractors/`:

| File | Purpose |
|------|---------|
| `fetch.py` | Smart HTTP fetcher with UA rotation, caching, Playwright fallback |
| `structured.py` | Schema.org JSON-LD and OpenGraph extraction |
| `platforms.py` | Platform-specific extractors (Sessionize, PaperCall, Eventbrite) |
| `heuristics.py` | HTML pattern matching for dates, topics, locations |
| `pipeline.py` | Orchestrates all extractors, merges results |
| `url_store.py` | Persistent store for collected URLs with status tracking |

### Tracking & Stats

The URL store tracks:
- **SPA vs Classic**: How many sites needed JavaScript rendering
- **Fetch method**: httpx (fast) vs Playwright (slow)
- **HTTP status codes**: 404, 403, timeouts, etc.
- **Error reasons**: connection errors, low confidence, etc.

View stats: `poetry run cfp url-stats`

### CLI Commands

```bash
# Collect URLs from all sources into the store
poetry run cfp collect-urls

# Extract from a single URL (test)
poetry run cfp extract --url "https://example.com/conf"

# Batch extract from pending URLs
poetry run cfp extract --limit 50 --workers 5

# Extract and sync to Algolia
poetry run cfp extract-sync --limit 100

# View URL store stats
poetry run cfp url-stats
```

## Adding New Sources

### Option A: URL Provider (Recommended)

If the source provides conference URLs but minimal metadata:

1. Add collection logic to `cli.py` `collect_urls()` command
2. URLs are stored and extracted automatically
3. Document in this file

### Option B: Full Parser

If the source has rich structured data (API, JSON, YAML):

1. Create `sources/{name}.py` with:
   - `RawXxxRecord` Pydantic model for raw data
   - `fetch_xxx()` async function with caching
   - `transform_record()` to convert to `CFP` model
   - `get_cfps()` main entry point

2. Update `pipeline.py` to include new source

3. Document in this file

4. Test: `poetry run python -c "from cfp_pipeline.sources.xxx import get_cfps; ..."`
