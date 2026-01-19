# CallForPapersPlease - Project Guidelines

## Overview
CFP aggregator with AI-powered discovery. Chat-first UX with map visualization.
**Two Algolia indexes**: `cfps` (conferences) + `cfps_talks` (YouTube talks with FK).

## Tech Stack
- **Backend**: Python + Poetry (cfp_pipeline/)
- **Frontend**: React + TypeScript + Vite (frontend/)
- **Search**: Algolia InstantSearch (2 indexes)
- **Map**: Leaflet + OpenStreetMap
- **LLM**: Algolia Enablers API (MiniMax M2.1)
- **YouTube**: yt-dlp (no API key needed)

## Testing Strategy

### Python (cfp_pipeline)

**Framework**: pytest + pytest-asyncio

**Test Structure**:
```
tests/
  unit/
    test_normalizers.py    # Location/topic normalization
    test_models.py         # Pydantic model validation
  integration/
    test_enrichers.py      # LLM enrichment (mock API)
    test_sources.py        # CAP API client (mock responses)
    test_algolia.py        # Algolia indexing (test index)
```

**Key Test Patterns**:
1. **Normalizers**: Pure functions, table-driven tests
   ```python
   @pytest.mark.parametrize("input,expected", [
       ("San Francisco, CA, USA", {"city": "San Francisco", "region": "West Coast"}),
       ("Berlin, Germany", {"city": "Berlin", "continent": "Europe"}),
   ])
   def test_normalize_location(input, expected):
       result = normalize_location(input)
       assert result.city == expected.get("city")
   ```

2. **LLM Enrichment**: Mock HTTP responses, test retry logic
3. **Algolia**: Use test index, cleanup after tests

**Run Tests**:
```bash
poetry run pytest tests/ -v
poetry run pytest tests/unit/ --cov=cfp_pipeline  # with coverage
```

### Frontend (React)

**Framework**: Vitest + React Testing Library

**Test Structure**:
```
src/
  components/
    __tests__/
      CFPCard.test.tsx
      Chat.test.tsx
      CFPMap.test.tsx
```

**Key Test Patterns**:
1. **Components**: Render with mock data, test interactions
2. **InstantSearch**: Mock useHits/useSearchBox hooks
3. **Map**: Mock Leaflet, test marker rendering

**Run Tests**:
```bash
cd frontend
npm test
npm run test:coverage
```

### E2E Tests (Playwright)

**Framework**: Playwright (headless chromium)

**Config**: `frontend/playwright.config.ts`
- baseURL: `http://localhost:5177/cfp-please/`
- Screenshots: `frontend/screenshots/`
- Tests: `frontend/e2e/`

**Run Tests**:
```bash
cd frontend
npx playwright test e2e/ --project=chromium
```

**Testing Patterns**:
1. **Screenshot-driven debugging**: Always save screenshots for visual verification
   ```typescript
   await page.screenshot({ path: './screenshots/test-name.png', fullPage: true });
   ```

2. **Position assertions**: Verify dropdown/panel positioning
   ```typescript
   const inputBox = await input.boundingBox();
   const panelBox = await panel.boundingBox();
   const distance = panelBox.y - (inputBox.y + inputBox.height);
   expect(distance).toBeLessThan(50); // Panel should be near input
   ```

3. **Specific selectors**: Avoid broad selectors that match multiple elements
   ```typescript
   // Bad: matches carousel headers too
   page.locator('[class*="header"]')
   // Good: specific class
   page.locator('.talkflix-header')
   ```

4. **Section filtering with regex**: Use regex for partial matches
   ```typescript
   page.locator('.search-section-title').filter({ hasText: /^CFPs/ })
   ```

5. **Wait for network**: Use networkidle for SPAs
   ```typescript
   await page.waitForLoadState('networkidle');
   ```

**Key Tests**:
- `test-search.spec.ts`: Autocomplete positioning, search page dark theme, multi-index results

## Environment Variables

### Backend (.env)
- `ALGOLIA_APP_ID` - Algolia application ID
- `ALGOLIA_API_KEY` - Admin API key (for indexing)
- `ALGOLIA_INDEX_NAME` - Index name (default: cfps)
- `ENABLERS_JWT` - Algolia Enablers API token

### Frontend (.env.local)
- `VITE_ALGOLIA_APP_ID` - Same as backend
- `VITE_ALGOLIA_SEARCH_KEY` - Search-only API key
- `VITE_ALGOLIA_INDEX_NAME` - Same as backend

## Git Workflow

- `master` - stable, protected
- `feature/*` - feature branches
- `fix/*` - bug fixes

Commits: conventional commits (`feat:`, `fix:`, `docs:`, `test:`)

## Common Commands

```bash
# CFP Pipeline
poetry run cfp fetch              # Fetch CFPs from sources
poetry run cfp enrich --limit 50  # Enrich with LLM
poetry run cfp sync               # Push to Algolia cfps index
poetry run cfp url-stats          # Show URL extraction stats

# URL Extraction (scrape conference pages)
poetry run cfp collect-urls       # Collect URLs from all sources
poetry run cfp extract --limit 50 # Extract CFP data from URLs
poetry run cfp extract --retry    # Retry failed (transient errors only)
poetry run cfp extract -f         # Force retry (ignore backoff)

# Talks Pipeline (YouTube)
poetry run cfp fetch-talks -c "KubeCon" --talks 100  # Single conference
poetry run cfp fetch-talks --limit 20 --talks 50    # Batch from top CFPs
poetry run cfp talks-stats                           # Show talks index stats

# Frontend
cd frontend && npm run dev   # Dev server
npm run build               # Production build

# Tests
poetry run pytest tests/ -v
```

## Architecture

### Models Package (`cfp_pipeline/models/`)
```
models/
├── __init__.py      # Exports: CFP, Location, GeoLoc, Talk
├── cfp.py           # CFP, Location, GeoLoc, RawCAPRecord
└── talk.py          # Talk model with conference FK
```
**Note**: Use `cfp.object_id` (snake_case) in Python, `objectID` in Algolia.

### URL Extraction Pipeline (`cfp_pipeline/extractors/`)
```
extractors/
├── fetch.py         # httpx + Playwright fallback for SPAs
├── url_store.py     # Persistent URL store with retry tracking
├── structured.py    # Schema.org / OpenGraph extraction
├── heuristics.py    # HTML pattern matching
└── pipeline.py      # Orchestrates all extractors
```

### Retry Strategy (URL Extraction)
- **Retryable errors**: timeout, connection, 429, 5xx
- **Permanent errors**: 404, 403, low_confidence
- **Backoff**: 1h → 6h → 24h (max 3 retries)

### Talks Index Schema (`cfps_talks`)
```json
{
  "objectID": "yt_VIDEO_ID",
  "conference_id": "abc123",     // FK to cfps
  "conference_name": "KubeCon",
  "title": "Kubernetes Design Principles",
  "speaker": "Saad Ali",
  "year": 2024,                  // Facet
  "view_count": 139284,
  "url": "https://youtube.com/watch?v=..."
}
```

## Algolia Index Schema

Key fields for search:
- `name` - Conference name (searchable)
- `description` - LLM-enriched description
- `topicsNormalized` - Facet for topics
- `location.region` - Facet for region
- `cfpEndDate` - Timestamp for filtering open CFPs
- `_geoloc` - Geo search

## Notes

- Always filter to open CFPs: `filters: cfpEndDate > ${now}`
- Deadline urgency: <=7 days (critical), <=30 days (warning), else OK
- LLM enrichment: 8 parallel workers, DDG fallback for unreachable URLs

### MiniMax API Tips
- Model returns `reasoning` + `content` fields
- Use extended timeouts (60s+) for complex prompts
- If `content` is null but `reasoning` exists, model is still thinking - retry
- Step-by-step extraction (description → topics → languages) works better than one-shot

### YouTube Search (yt-dlp)
- Use quoted conference names: `'"PyCon" 2024 presentation OR talk'`
- Strip year from conference name before searching (e.g., "KubeCon 2026" → "KubeCon")
- Filter out shorts (<5min) and non-talk content (trailers, recaps)
- Sort by view_count for popular talks

### Frontend CSS
- Design system with CSS custom properties (`--color-primary`, `--space-*`)
- Mobile-first: bottom nav, slide-over filters, 48px touch targets
- Spacing scale: 4px base (`--space-1` = 0.25rem)

### Data Quality (as of session)
- CFPs: 404 open, 0% descriptions, 58% geoloc, 17% topics
- Talks: separate index, FK to conferences
- URL store: 597 URLs, ~60% extraction success rate
