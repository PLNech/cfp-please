# CallForPapersPlease - Task Backlog

## Active Tasks

### 1. GitHub Actions: Data Pipeline Automation
**Status: Pending**

Create CI/CD for regular data refresh.

**Files to Create:**
- `.github/workflows/fetch-cfps.yml` - Daily fetch from sources
- `.github/workflows/enrich-cfps.yml` - LLM enrichment
- `.github/workflows/sync-algolia.yml` - Push to Algolia
- `.github/workflows/cleanup.yml` - Remove expired CFPs

**Schedule:**
- Fetch: Daily at 06:00 UTC
- Enrich: After fetch
- Sync: After enrich
- Cleanup: Weekly (Sundays 02:00 UTC)

---

### 2. Frontend: Hide Past-CFP Events
**Status: Pending**

Prevent user frustration by hiding closed CFPs.

**Filter Rules:**
- `cfpEndDate > ${now}` in Algolia query
- Or filter in React: `daysUntilCfpClose >= 0`
- Show badge for "Closed yesterday" if < 7 days past

**Files to Update:**
- `frontend/src/pages/search/SearchPage.tsx` - Add date filter
- `frontend/src/pages/TalkFlixHome.tsx` - Filter carousel CFPs
- `frontend/src/App.tsx` - Modal shows closed state

---

### 3. CRITICAL: Fix Fabricated Intel Data
**Status: COMPLETED ✅**

**Problem:** Intel counts were fake - "118 HN stories" for RustWeek when only 1 real result existed.

**Solution:** Added noise filter in `cfp_pipeline/enrichers/popularity.py`:
- Filters newsletter patterns (`"This Week in *"`, `"Issue #"`, `"Show HN"`, etc.)
- Requires conference name to appear in title
- Keeps old-year content (FOSDEM 2020 videos still about FOSDEM)

**Results:**
```
FOSDEM 2026:    718 → 49 stories (93% noise filtered)
RustWeek 2026:  119 → 1 story  (99% noise filtered)
State of Map US: 220 → 4 stories (98% noise filtered)
Craft Conference: 38 → 1 story (kept, mentions conf)
```

**Verification Tool:** `poetry run python verify_intel.py "Conference Name"`

---

### 4. Semantic Intel Filtering v2 (Future)
**Status: Pending**

Replace regex noise filtering with semantic similarity for better precision.

**Approach:**
1. Pull all HN/GH/Reddit results for a conference query
2. Compute embedding similarity to conference name
3. Only index results above threshold (e.g., 0.7)

**Benefits:**
- Handles "This Week in Rust" → RustWeek correctly
- No manual regex maintenance
- Catches edge cases

---

### 5. Modal Quick Fixes & Search UI Redesign
**Status: COMPLETED ✅**

**Changes:**
1. **Modal title color** - Fixed visibility on dark background
2. **Community Buzz redesign** - Shows real HN/Reddit comments
3. **Search cards with description** - Added description field
4. **Encoding fixes** - Python + JS UTF-8 validation

---

### 6. User Personalization & Filtering
**Status: Pending**

**Features:**

#### 6.1 Country/Region Filters
- Include/exclude countries with flag + code chips
- Distance filter from city (OSM/Nominatim autocomplete)

#### 6.2 Thumbs Up/Down Personalization
- None → 👍 → 💖 (double-tap) → None
- None → 👎 → None
- Stored in localStorage + optional sync
- Compressed context for agent prompts

**Data Model:**
```typescript
interface UserPreferences {
  likedCfps: string[];      // objectIDs with "adore" level
  dislikedCfps: string[];    // objectIDs
  preferenceVector: {
    topics: Record<string, -1 | 0 | 1>;
    locations: Record<string, -1 | 1>;
    formats: Record<string, -1 | 1>;
  };
}
```

**Prompt Injection Format:**
```
## User Preferences (compressed)
LOC_PREF: IT:+1, DE:+1, US:-1 | FMT: hybrid:+1 | TOPIC: AI:+1, Rust:-1
```

**Files to Modify:**
- `backend/models/user.py` - Add preferences fields
- `backend/api/user.py` - Add preferences endpoints
- `frontend/src/hooks/usePreferences.ts` - New hook
- `frontend/src/components/filters/CountryFilter.tsx` - New
- `frontend/src/components/filters/DistanceFilter.tsx` - New
- `frontend/src/components/CFPThumbs.tsx` - New
- `frontend/src/pages/search/SearchPage.tsx` - Add filters panel

---

## Completed Checklist

- [x] Modal title visibility fix
- [x] Community Buzz shows real comments (or empty state)
- [x] Search cards show description
- [x] Encoding fix (Python + JS)
- [x] Intel noise filter (no more fake counts)
- [x] `verify_intel.py` audit script

---

## Data Quality Notes (Jan 2026)

### Intel Scraping Observations
- **Large confs (FOSDEM)**: 49 stories, rich comments, 5648 pts
- **Small confs (RustWeek)**: 1 story, 1 pt, no comments
- **Pattern**: Comments only exist for established conferences

### Recommendation
- Use FOSDEM-style comments for description generation
- Show "Be first to discuss" for small confs
- Don't fabricate counts - show 0 honestly

### Test Conference List
```
U.S. Travel's ESTO 2026 | AgentCon San Francisco | SREday London 2026 Q1
RustWeek 2026 | AgentCamp 2026 - Madrid | State of the Map US 2026
Sikkerhetsfestivalen 2026 | CNCF Co-located Events Europe 2026
Xen Spring Meetup 2026 | Web Day 2026 | Devopsdays Copenhagen
AWS Community Day Ahmedabad 2026 | JFTL | Stir Trek 2026
AI Coding Summit | Neos Conference 2026 | Techorama 2026 Belgium
Global Power Platform Bootcamp 2026 | Global Azure Veneto 2026
Tenerife Winter Sessions 2026 | HackConRD 2026 | Torino.NET
FOSDEM 2026 | Craft Conference 2026
```