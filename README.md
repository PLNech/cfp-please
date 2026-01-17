# cfp-please

AI-powered discovery for conference Call for Papers.

## What is this?

A tool for conference speakers to find relevant CFPs using natural language queries like:
- "AI conferences in Europe closing soon"
- "Frontend talks in the Midwest this summer"
- "Security conferences with workshops"

## Features

- **Chat-first UX**: Natural language search powered by Algolia
- **Map view**: See conferences geographically with urgency indicators
- **Smart filters**: Topics, regions, deadlines
- **350+ CFPs**: Aggregated from CallingAllPapers, enriched with LLM

## Tech Stack

| Layer | Tech |
|-------|------|
| Data Pipeline | Python, Poetry, CallingAllPapers API |
| Search | Algolia |
| Frontend | React, TypeScript, Vite, Leaflet |
| Hosting | GitHub Pages |

## Development

### Pipeline (Python)

```bash
cd cfp_pipeline
poetry install
poetry run cfp sync          # Fetch + index CFPs
poetry run cfp sync --enrich # With LLM enrichment
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local`:
```
VITE_ALGOLIA_APP_ID=your_app_id
VITE_ALGOLIA_SEARCH_KEY=your_search_key
VITE_ALGOLIA_INDEX_NAME=cfps
```

## License

GPL-3.0 - see [LICENSE](LICENSE)
