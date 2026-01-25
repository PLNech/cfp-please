# Intel Index Rebuild Plan

**Status**: DRAFT - pending final audit results
**Problem**: Current intel indexes have 33-67% noise (Reddit confirmed, HN/GitHub pending)

## Principles

1. **Precision over recall** - Better to have 5 real results than 50 with noise
2. **Validate post-fetch** - Never trust API results blindly
3. **Quality thresholds** - Minimum engagement signals required
4. **Source-appropriate strategy** - Each source needs tailored approach
5. **Confidence scoring** - Track how sure we are about each result

## Phase 1: Reset

```bash
# Delete all intel index records
poetry run python -c "
from algoliasearch.search.client import SearchClientSync
import os
from dotenv import load_dotenv
load_dotenv()

client = SearchClientSync(os.environ['ALGOLIA_APP_ID'], os.environ['ALGOLIA_API_KEY'])
for idx in ['cfps_intel_hn', 'cfps_intel_reddit', 'cfps_intel_github', 'cfps_intel_devto']:
    client.clear_objects(index_name=idx)
    print(f'Cleared {idx}')
"
```

## Phase 2: Query Strategy by Source

### Hacker News

**Current problem**: Generic search returns tangential results

**New approach**:
```python
# BEFORE (broken)
query = clean_name  # "KubeCon CloudNativeCon Europe"

# AFTER (precise)
query = f'"{clean_name}"'  # Quoted = exact phrase match
# OR for multi-word: require ALL words
query = f'"{short_name}"'  # Just "KubeCon" quoted
```

**Validation rules**:
- Conference name (or known alias) MUST appear in title
- Minimum: 5 points OR 2 comments (skip 0-engagement posts)
- Skip "Show HN", "Ask HN" unless specifically about conference

**Schema addition**:
```python
{
    "confidence": "high" | "medium" | "low",
    "match_type": "exact_title" | "partial_title" | "in_comments",
    "relevance_score": 0.0-1.0  # computed from signals
}
```

### GitHub

**Current problem**: Keyword search returns unrelated repos

**New approach**:
```python
# Search strategies (in order of confidence):
# 1. Official org search (highest confidence)
query = f'org:{conf_org} {conf_name}'  # If we know the org

# 2. Exact repo name match
query = f'"{conf_name}" in:name'

# 3. Topic-based (medium confidence)
query = f'topic:{conf_slug}'

# 4. Description search (lowest confidence, needs validation)
query = f'"{conf_name}" in:description'
```

**Validation rules**:
- Repo name or description MUST contain conference name
- Prefer repos with: >10 stars, recent activity (<2 years), README exists
- Flag official org repos separately (highest value)

**Confidence tiers**:
- `high`: Official org repo OR exact name match with >50 stars
- `medium`: Name contains conference, >10 stars
- `low`: Description mention only

### Reddit

**Current problem**: No subreddit filtering, generic matches

**New approach**:
```python
# Allowlist-only mode (strict)
TECH_SUBREDDITS = [
    "programming", "webdev", "devops", "kubernetes", "docker",
    "aws", "azure", "googlecloud", "python", "rust", "golang",
    "javascript", "typescript", "reactjs", "node", "linux",
    "sysadmin", "netsec", "machinelearning", "datascience",
    "cscareerquestions", "experienceddevs", "softwareengineering",
    # Conference-specific
    "fosdem", "kubecon", "pycon", "rustconf", "gophercon"
]

# Search only in allowed subreddits
for sub in TECH_SUBREDDITS:
    query = f'subreddit:{sub} "{conf_name}"'
```

**Validation rules**:
- Post title or selftext MUST contain conference name
- Minimum: 5 upvotes OR 2 comments
- Skip crossposts from blocked subs

**Consider**: Maybe Reddit isn't worth it. HN + GitHub might be enough.

### DEV.to

**Current problem**: Tag-based search misses most content

**New approach**:
```python
# Multi-strategy search
strategies = [
    f'tag:{conf_slug}',           # Tag match
    f'"{conf_name}" conference',  # Title search
    f'"{conf_name}" cfp',         # CFP-specific
]
```

**Validation**: Title or description contains conference name

## Phase 3: New Schema

```python
@dataclass
class IntelRecord:
    # Identity
    object_id: str           # Source-specific ID
    cfp_id: str              # FK to cfps index
    cfp_name: str            # Denormalized for search
    source: str              # "hn" | "github" | "reddit" | "devto"

    # Content
    title: str
    url: str
    author: str
    created_at: datetime

    # Source-specific
    points: int | None       # HN
    stars: int | None        # GitHub
    upvotes: int | None      # Reddit
    reactions: int | None    # DEV.to
    comments_count: int

    # Quality signals
    confidence: str          # "high" | "medium" | "low"
    match_type: str          # "exact_title" | "org_repo" | "description"
    relevance_score: float   # 0.0-1.0

    # Rich content (for description generation)
    top_comments: list[str]  # Max 5, >50 chars each
    description: str | None  # Repo desc or post selftext

    # Metadata
    fetched_at: datetime
    verified: bool           # Manual verification flag
```

## Phase 4: Rebuild Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FETCH     │ →   │  VALIDATE   │ →   │   SCORE     │ →   │   INDEX     │
│             │     │             │     │             │     │             │
│ Quoted      │     │ Name in     │     │ Compute     │     │ Only        │
│ searches    │     │ title?      │     │ confidence  │     │ confidence  │
│ per source  │     │ Min engage? │     │ + relevance │     │ >= medium   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   REJECT    │
                    │             │
                    │ Log for     │
                    │ analysis    │
                    └─────────────┘
```

## Phase 5: Quality Gates

Before declaring rebuild complete:

1. **Sample validation**: Manually check 20 random records per source
2. **Known-good test**: Verify FOSDEM, KubeCon, PyCon have quality data
3. **Known-bad test**: Verify "AgentCamp Ponferrada" doesn't have garbage
4. **Precision estimate**: Target >80% relevance (vs current 33%)

## Decision Points (pending audit)

| Question | Options | Depends on |
|----------|---------|------------|
| Keep Reddit? | Drop / Allowlist-only / Full rebuild | Audit results |
| Keep DEV.to? | Drop / Keep | Coverage analysis |
| Index structure | Separate per-source / Combined | Query patterns |
| Backfill strategy | All 424 / Top 100 first | API rate limits |

## Timeline Estimate

1. Reset indexes: 5 min
2. Implement new scraper logic: 2-3 hours
3. Test on 10 conferences: 30 min
4. Full backfill (424 CFPs × 4 sources): 2-4 hours (rate limited)
5. Quality validation: 1 hour

## Open Questions

1. Should we store rejected candidates for debugging?
2. Do we need conference aliases (KubeCon = CloudNativeCon)?
3. Should confidence affect popularity score weighting?
4. Rate limit budget - how aggressive can we be?

---

*This plan will be updated after HN and GitHub audit results.*
