# Map v1 Ideation: Geo in Netflix UI

## Current State

- **84% of Sessionize CFPs** have `_geoloc` (lat/lng from OSM Nominatim)
- **12% are virtual** (no geocoding needed)
- Algolia supports `aroundLatLng`, `aroundRadius` for geo-sorted queries

## Design Constraints

1. **Maintain Netflix vibe** - Dark theme, carousels, browse-first UX
2. **Map as enhancement** - Complement carousels, don't replace
3. **Mobile-first** - Maps on mobile need careful UX
4. **Performance** - Leaflet/OSM is free, no API keys needed

---

## Options Evaluated

### 1. "Near You" Geo-Carousel (TalkFlixHome)

A special carousel showing CFPs sorted by distance from user.

```
┌──────────────────────────────────────────────────┐
│  📍 Near You (based on your location)            │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐                     │
│  │ 5km│ │12km│ │45km│ │89km│  →                  │
│  └────┘ └────┘ └────┘ └────┘                     │
└──────────────────────────────────────────────────┘
```

**Pros:** Fits existing UX, minimal change, works on mobile
**Cons:** No visual map, less exploration power

**Effort:** Low (add geo query + one carousel)

---

### 2. Map Toggle on Search Page

Toggle between list view and map view (Airbnb-style).

```
┌──────────────────────────────────────────────────┐
│  [List] [Map]  ← Toggle                          │
├──────────────────────────────────────────────────┤
│                                                  │
│            🗺️ FULL SCREEN MAP                   │
│         with clickable conference pins           │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Pros:** Full map experience, familiar pattern
**Cons:** Context switch between modes

**Effort:** Medium

---

### 3. Split View (Map + Cards)

Side-by-side: map left, scrollable cards right.

```
┌─────────────────┬────────────────────────────────┐
│                 │  ┌──────────────────────────┐  │
│   🗺️ MAP       │  │ RustWeek 2026           │  │
│                 │  │ Utrecht, Netherlands    │  │
│  (pins)         │  │ 📅 Jun 10-14            │  │
│                 │  └──────────────────────────┘  │
│                 │  ┌──────────────────────────┐  │
│                 │  │ JNation 2026            │  │
│                 │  └──────────────────────────┘  │
└─────────────────┴────────────────────────────────┘
```

**Pros:** Best of both worlds, hover/click sync
**Cons:** Desktop-only (needs responsive fallback)

**Effort:** High

---

### 4. Mini Map Widget (Header/Hero)

Small interactive map, always visible. Click pin → scrolls to CFP.

```
┌──────────────────────────────────────────────────┐
│  Header                    ┌─────────┐           │
│                            │🗺️ mini │           │
│                            │  map    │           │
│                            └─────────┘           │
├──────────────────────────────────────────────────┤
│  Carousels...                                    │
```

**Pros:** Non-intrusive, always accessible
**Cons:** Too small for real exploration

**Effort:** Low-Medium

---

### 5. Map Modal/Overlay

Click button → full-screen map appears as overlay.

**Pros:** Clean carousels, full map when needed
**Cons:** Extra click, interrupts flow

**Effort:** Medium

---

## Recommendation: Hybrid Approach

### Phase 1 (v1)
1. **TalkFlixHome**: Add "📍 Near You" carousel (geo-sorted)
2. **SearchPage**: Add small map toggle in filter bar

### Phase 2 (v2)
3. **SearchPage**: Split view for desktop
4. **Mobile**: Full-screen map toggle

---

## Technical Notes

### Algolia Geo Query
```ts
const { hits } = await index.search('', {
  aroundLatLng: `${userLat},${userLng}`,
  aroundRadius: 'all',  // Sort by distance, no cutoff
  getRankingInfo: true, // Get distance in response
});
```

### Leaflet + React
```bash
npm install leaflet react-leaflet
```

```tsx
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';

<MapContainer center={[52.37, 4.89]} zoom={6}>
  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
  {cfps.map(cfp => cfp._geoloc && (
    <Marker position={[cfp._geoloc.lat, cfp._geoloc.lng]}>
      <Popup>{cfp.name}</Popup>
    </Marker>
  ))}
</MapContainer>
```

### User Location
```ts
navigator.geolocation.getCurrentPosition(
  (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
  () => setUserLocation(null) // Fallback: no geo filter
);
```

---

## Questions for You

1. **Priority?** Near You carousel first, or full map on search?
2. **Location consent?** Prompt user or default to no geo?
3. **Virtual events?** Show in separate "🌐 Virtual" carousel or mixed?
4. **Pin density?** Cluster overlapping pins or show all?

---

## Effort Estimate

| Feature | Effort | Dependencies |
|---------|--------|--------------|
| Near You carousel | 2-4h | Geo query hook |
| Map toggle (search) | 4-6h | Leaflet setup |
| Split view | 8-12h | Responsive handling |
| Pin clustering | 2-3h | Leaflet plugin |
