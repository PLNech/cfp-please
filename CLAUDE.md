# CallForPapersPlease - Project Guidelines

## Vision

**A trust engine for CFP discovery** - Help speakers find conferences they'll actually care about, without lying to them.

Core principles:
1. **Data trust** - Real data or nothing. Never fabricate counts.
2. **Pipeline-first** - Validate source → scrape → index → frontend. Each stage verified before next.
3. **Good citizen** - Cache scraped data in indexes (`cfps_intel_*`). Don't re-hit APIs needlessly.
4. **Relevance** - Personalized to user's situation (location, interests, preferences).
5. **Freshness** - No stale CFPs, no expired deadlines, automated refresh.

## Pipeline Methodology

Every feature follows this validation chain. **Each stage must be verified before the next.**

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
│ SOURCE  │ →  │ SCRAPE  │ →  │  INDEX  │ →  │ FRONTEND │
│         │    │         │    │         │    │          │
│ What    │    │ What we │    │ What    │    │ What     │
│ exists  │    │ extract │    │ Algolia │    │ user     │
│ in wild │    │ + clean │    │ stores  │    │ sees     │
└─────────┘    └─────────┘    └─────────┘    └──────────┘
     ↓              ↓              ↓              ↓
  Audit API     Verify N       Query test     Screenshot
  responses     samples        + schema       verification
```

### Validation Gates

| Stage | Gate | Tool |
|-------|------|------|
| Source | "Does this API/site actually return X?" | `curl`, manual check |
| Scrape | "Do we extract correctly for N=100 samples?" | `verify_intel.py`, test fixtures |
| Index | "Is it queryable as expected?" | Algolia dashboard, test queries |
| Frontend | "Does it render correctly?" | Playwright screenshots |

**Rules:**
- Never design UI for data you haven't validated through scrape + index
- Never declare victory from <10 samples - use full test set (`tests/fixtures/test_conferences.json`)
- Description generation (MiniMax) only AFTER intel data is verified

## Tech Stack

- **Backend**: Python + Poetry (`cfp_pipeline/`)
- **Frontend**: React + TypeScript + Vite (`frontend/`)
- **Search**: Algolia InstantSearch (multi-index)
- **Map**: Leaflet + OpenStreetMap
- **LLM**: Algolia Enablers API (MiniMax M2.1)
- **YouTube**: yt-dlp (no API key needed)

## Algolia Index Architecture

### Primary Indexes

| Index | Entries | Purpose |
|-------|---------|---------|
| `cfps` | ~424 | Main conferences |
| `cfps_talks` | ~4274 | YouTube talks (FK: `conference_id`) |
| `cfps_speakers` | ~1425 | Speaker profiles |

### Intel Indexes (Cached Scrapes)

| Index | Entries | Source |
|-------|---------|--------|
| `cfps_intel_hn` | ~163 | Hacker News stories/comments |
| `cfps_intel_github` | ~183 | GitHub repos/discussions |
| `cfps_intel_reddit` | ~375 | Reddit posts/comments |
| `cfps_intel_devto` | ~22 | Dev.to articles |

**Why separate indexes?** Good citizen principle - scrape once, query many. Don't re-hit HN/Reddit/GitHub on every request.

### Sorting Replicas

`cfps_deadline_asc`, `cfps_github_desc`, `cfps_hn_desc`, `cfps_popularity_desc`

## Data Sources & Trust Status

| Source | Data | Trust | Notes |
|--------|------|-------|-------|
| CallingAllPapers API | CFP basics | ✅ | Core source |
| Conference URLs | Descriptions, topics | ⚠️ | 60% extraction success |
| HN (via Algolia API) | Stories, comments | ⚠️ | Filtered - was fabricating |
| Reddit | Posts, comments | ❓ | Needs audit |
| GitHub | Repos, stars | ❓ | Needs audit |
| YouTube (yt-dlp) | Talks | ✅ | FK to conferences |
| Sessionize | CFP structure, fields | ❓ | Not yet integrated |

### Potential New Sources

| Source | What it offers | Integration complexity |
|--------|----------------|----------------------|
| Sessionize | CFP form fields, session formats, speaker slots | Medium - scrape or API? |
| Papercall | Similar to Sessionize | Medium |
| Confs.tech | Curated tech conferences | Low - JSON API |
| Dev.to events | Community events | Low - API |

### Intel Filtering (Lessons Learned)

**Problem discovered**: "118 HN stories" for RustWeek when only 1 real result existed.

**Root cause**: Newsletters ("This Week in Rust"), Show HN spam, unrelated mentions.

**Solution**: Noise filter in `cfp_pipeline/enrichers/popularity.py`:
- Filters newsletters (`"This Week in *"`, `"Issue #"`, `"Show HN"`)
- Requires conference name in title
- Keeps historical content (FOSDEM 2020 videos still about FOSDEM)

**Verification**: `poetry run python cfp_pipeline/verify_intel.py "Conference Name"`

## Test Fixtures

Test data lives in `tests/fixtures/`:
- `test_conferences.json` - 100 conferences for validation (mix of large/small, known/obscure)

**Always test against this set when changing scraping/enrichment logic.**

## Common Commands

```bash
# CFP Pipeline
poetry run cfp fetch              # Fetch from sources
poetry run cfp enrich --limit 50  # LLM enrichment
poetry run cfp sync               # Push to Algolia

# URL Extraction
poetry run cfp collect-urls       # Collect URLs
poetry run cfp extract --limit 50 # Extract CFP data
poetry run cfp extract --retry    # Retry transient errors

# Talks Pipeline
poetry run cfp fetch-talks -c "KubeCon" --talks 100
poetry run cfp talks-stats

# Intel Verification (CRITICAL)
poetry run python cfp_pipeline/verify_intel.py "Conference Name"

# Frontend
cd frontend && npm run dev
npx playwright test e2e/ --project=chromium
```

## Architecture

### Models (`cfp_pipeline/models/`)
```
models/
├── __init__.py      # Exports: CFP, Location, GeoLoc, Talk
├── cfp.py           # CFP, Location, GeoLoc, RawCAPRecord
└── talk.py          # Talk model with conference FK
```
**Note**: Use `cfp.object_id` (snake_case) in Python, `objectID` in Algolia.

### Extractors (`cfp_pipeline/extractors/`)
```
extractors/
├── fetch.py         # httpx + Playwright fallback
├── url_store.py     # Persistent store with retry tracking
├── structured.py    # Schema.org / OpenGraph
├── heuristics.py    # HTML pattern matching
└── pipeline.py      # Orchestrator
```

### Retry Strategy
- **Retryable**: timeout, connection, 429, 5xx
- **Permanent**: 404, 403, low_confidence
- **Backoff**: 1h → 6h → 24h (max 3 retries)

## Environment Variables

### Backend (.env)
- `ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `ALGOLIA_INDEX_NAME`
- `ALGOLIA_SEARCH_API_KEY` - Read-only key
- `ENABLERS_JWT` - Algolia Enablers API token
- `UNSPLASH_ACCESS_KEY` - City images

### Frontend (.env.local)
- `VITE_ALGOLIA_APP_ID`, `VITE_ALGOLIA_SEARCH_KEY`, `VITE_ALGOLIA_INDEX_NAME`

## Git Workflow

- `main` - stable
- `feature/*` - feature branches
- `fix/*` - bug fixes

Commits: conventional commits (`feat:`, `fix:`, `docs:`, `test:`)

## Testing Strategy

### Pipeline Validation (Most Important)

```bash
# Verify intel data across full test set
poetry run python cfp_pipeline/verify_intel.py --batch

# Integration test for enrichers
poetry run pytest tests/integration/test_intel_accuracy.py -v
```

### Python (cfp_pipeline)

pytest + pytest-asyncio. Table-driven tests for normalizers, mocked HTTP for LLM.

### Frontend (React)

Vitest + React Testing Library.

### E2E (Playwright)

**Config**: `frontend/playwright.config.ts`

**Critical patterns**:
1. Screenshot-driven debugging - always save screenshots
2. Wait for network with `networkidle`
3. Use specific selectors, not broad class matches

## Technical Notes

### MiniMax API
- Returns `reasoning` + `content` fields
- Use 60s+ timeouts
- If `content` is null but `reasoning` exists → retry
- Step-by-step extraction works better than one-shot
- **Only use for description generation AFTER intel is verified**

### YouTube (yt-dlp)
- Quoted conference names: `'"PyCon" 2024 presentation OR talk'`
- Strip year before searching
- Filter shorts (<5min) and non-talk content
- Sort by view_count

### Frontend CSS
- CSS custom properties (`--color-primary`, `--space-*`)
- Mobile-first: bottom nav, slide-over filters, 48px touch targets
- Dark theme: explicit background/border on all inputs
- **Always theme third-party components** (Algolia autocomplete is light by default)

### UX Quality Gates

**Always visually verify UI changes with Playwright screenshots.**
```bash
npx playwright screenshot http://localhost:5173/cfp-please/ screenshots/verify.png
```
Check: dark theme consistency, alignment, proper spacing.

## Encoding Fix

HTML entities in names (e.g., `U.S. Travel&#39;s ESTO`) must be:
1. Decoded at scrape time (Python: `html.unescape()`)
2. Escaped on render (React handles this, but verify)

## Algolia Agent Studio

### API Reference

Base URL: `https://{APP_ID}.algolia.net/agent-studio/1`

**Headers** (all requests):
- `X-Algolia-Application-Id`: App ID
- `X-Algolia-API-Key`: Admin key (editSettings ACL) for CRUD, Search key for completions

**Endpoints**:
| Method | Path | ACL | Purpose |
|--------|------|-----|---------|
| GET | `/agents` | settings | List agents |
| POST | `/agents` | editSettings | Create agent |
| GET | `/agents/{id}` | settings | Get agent |
| PATCH | `/agents/{id}` | editSettings | Update agent |
| DELETE | `/agents/{id}` | editSettings | Delete agent |
| POST | `/agents/{id}/publish` | editSettings | Publish agent |
| POST | `/agents/{id}/completions` | search | Chat with agent |

### Agent Configuration Schema

```json
{
  "name": "string (required)",
  "description": "string | null",
  "instructions": "string (system prompt, required)",
  "model": "string | null",
  "config": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "sendReasoning": true
  },
  "tools": [/* ToolConfig array */]
}
```

### Tool Types

**1. Client-Side Tool** (local execution, agent gets results back):
```json
{
  "type": "client_side",
  "name": "save_profile",
  "description": "Saves user profile preferences locally",
  "inputSchema": {
    "type": "object",
    "properties": {
      "role": { "type": "string" },
      "topics": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["role"],
    "additionalProperties": false
  }
}
```

**2. Algolia Search Tool**:
```json
{
  "type": "algolia_search_index",
  "name": "cfp_search",
  "indices": [{
    "index": "cfps",
    "description": "Search open CFPs by topic, location, deadline"
  }]
}
```

### Client-Side Tool Pattern (Frontend)

1. Agent calls tool → returns `tool_invocations` with `state: "call"`
2. App executes locally, validates, returns result
3. Agent processes result, continues conversation

**Validation flow**: Agent extracts data → calls `save_profile` → app validates → returns `{success, errors}` → agent retries on error

### Our Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| TalkFlix Hero Selector | Pick featured CFP | `cfp_search` |
| TalkFlix Match Score | Calculate user-CFP fit | none |
| TalkFlix Inspire | Generate talk ideas | `cfp_search` |
| **Profile Interview** | Collect user preferences | `save_profile` (client-side) |

### Creating Agents via API

```bash
curl -X POST "https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents" \
  -H "X-Algolia-Application-Id: ${ALGOLIA_APP_ID}" \
  -H "X-Algolia-API-Key: ${ALGOLIA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name": "...", "instructions": "...", "tools": [...]}'
```
