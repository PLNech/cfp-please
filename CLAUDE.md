# CallForPapersPlease - Project Guidelines

## Overview
CFP aggregator with AI-powered discovery. Chat-first UX with map visualization.

## Tech Stack
- **Backend**: Python + Poetry (cfp_pipeline/)
- **Frontend**: React + TypeScript + Vite (frontend/)
- **Search**: Algolia InstantSearch
- **Map**: Leaflet + OpenStreetMap
- **LLM**: Algolia Enablers API (MiniMax M2.1)

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

### E2E Tests (future)

**Framework**: Playwright

**Key Flows**:
- Search → Results → Map markers update
- Filter → Results narrow → Map zooms
- Click marker → Detail modal opens

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
# Pipeline
poetry run cfp fetch         # Fetch CFPs from CAP
poetry run cfp enrich --limit 50  # Enrich with LLM
poetry run cfp sync          # Push to Algolia

# Frontend
cd frontend && npm run dev   # Dev server
npm run build               # Production build
npm test                    # Run tests

# Tests
poetry run pytest tests/ -v
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
