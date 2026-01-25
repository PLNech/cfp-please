/**
 * Design Playground - Prototype UI experiments
 *
 * Route: /demo
 * Purpose: Test different UI approaches before promoting to production
 */

import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import createGlobe from 'cobe';
import 'leaflet/dist/leaflet.css';
import './DemoPage.css';

// Fix Leaflet default marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// =============================================================================
// GLOBE WIDGET - Cobe WebGL globe with glowing location marker
// =============================================================================

interface GlobeWidgetProps {
  lat?: number;
  lng?: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'zoomed' | 'lowres' | 'smooth';
}

const GLOBE_SIZES = { sm: 60, md: 100, lg: 160, xl: 200 };

function GlobeWidget({ lat = 52.37, lng = 4.89, label = 'Amsterdam', size = 'md', variant = 'default' }: GlobeWidgetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const globeSize = GLOBE_SIZES[size];

  useEffect(() => {
    if (!canvasRef.current) return;

    const targetPhi = (lng * Math.PI) / 180;
    const targetTheta = (lat * Math.PI) / 180;

    // Variant-specific settings to combat moiré
    const variantSettings = {
      default: {
        mapSamples: 16000,
        mapBrightness: 6,
        devicePixelRatio: 2,
        scale: 1,
        markerSize: size === 'sm' ? 0.25 : size === 'md' ? 0.2 : 0.15,
      },
      zoomed: {
        // Render bigger globe, CSS will crop it
        mapSamples: 20000,
        mapBrightness: 5,
        devicePixelRatio: 2,
        scale: 2.5,  // Zoom in to show quarter
        markerSize: 0.08,
      },
      lowres: {
        // Fewer dots = less moiré
        mapSamples: 4000,
        mapBrightness: 8,
        devicePixelRatio: 1.5,
        scale: 1,
        markerSize: size === 'sm' ? 0.3 : 0.25,
      },
      smooth: {
        // Medium samples with blur
        mapSamples: 8000,
        mapBrightness: 5,
        devicePixelRatio: 1,
        scale: 1,
        markerSize: size === 'sm' ? 0.3 : 0.25,
      },
    };

    const settings = variantSettings[variant];
    const renderSize = Math.round(globeSize * settings.scale);

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: settings.devicePixelRatio,
      width: renderSize * 2,
      height: renderSize * 2,
      phi: targetPhi,
      theta: targetTheta,
      dark: 1,
      diffuse: 1.2,
      mapSamples: settings.mapSamples,
      mapBrightness: settings.mapBrightness,
      baseColor: [0.15, 0.2, 0.25],
      markerColor: [1, 0.2, 0.2],
      glowColor: [0.1, 0.15, 0.2],
      markers: [
        { location: [lat, lng], size: settings.markerSize }
      ],
      onRender: (state) => {
        state.phi = targetPhi;
        state.theta = targetTheta;
      }
    });

    return () => globe.destroy();
  }, [lat, lng, globeSize, size, variant]);

  const isZoomed = variant === 'zoomed';
  const isSmooth = variant === 'smooth';

  return (
    <div
      className={`globe-widget globe-${size} globe-variant-${variant}`}
      title={label}
      style={isZoomed ? { overflow: 'hidden' } : undefined}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: isZoomed ? globeSize * 2.5 : globeSize,
          height: isZoomed ? globeSize * 2.5 : globeSize,
          maxWidth: isZoomed ? undefined : '100%',
          aspectRatio: '1',
          transform: isZoomed ? 'translate(-30%, -20%)' : undefined,
          filter: isSmooth ? 'blur(0.5px)' : undefined,
        }}
      />
      {label && <span className="globe-label">{label}</span>}
    </div>
  );
}

// =============================================================================
// GLOBE CARD - Globe as card background texture
// =============================================================================

interface GlobeCardProps {
  title: string;
  subtitle: string;
  lat: number;
  lng: number;
  badge?: string;
  cityImageUrl?: string;  // Unsplash city image to layer with globe
}

function GlobeCard({ title, subtitle, lat, lng, badge, cityImageUrl }: GlobeCardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const globeRef = useRef<ReturnType<typeof createGlobe> | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    // Cobe coordinate system:
    // phi = horizontal rotation (0 = prime meridian facing camera)
    // theta = vertical tilt (0 = equator level, negative = looking down from north)
    // To center camera on a location: rotate globe so location faces us
    const targetPhi = (-lng * Math.PI) / 180;  // Negative to rotate location to front
    const targetTheta = (lat * Math.PI) / 180; // Positive for northern hemisphere

    globeRef.current = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: 400,
      height: 400,
      phi: targetPhi,
      theta: targetTheta,
      dark: 1,
      diffuse: 1.5,
      mapSamples: 16000,
      mapBrightness: 8,
      baseColor: [0.2, 0.25, 0.3],
      markerColor: [1, 0.3, 0.3],     // Brighter red
      glowColor: [0.15, 0.2, 0.25],
      markers: [
        { location: [lat, lng], size: 0.17 }  // Visible but not too large
      ],
      onRender: (state) => {
        state.phi = targetPhi;
        state.theta = targetTheta;
      }
    });

    return () => {
      if (globeRef.current) {
        globeRef.current.destroy();
        globeRef.current = null;
      }
    };
  }, [lat, lng]);

  return (
    <div className="globe-card">
      {/* Layer 1: City image (if available) */}
      {cityImageUrl && (
        <img
          src={cityImageUrl}
          alt=""
          className="globe-card-city-img"
          loading="lazy"
        />
      )}
      {/* Layer 2: Globe overlay */}
      <canvas
        ref={canvasRef}
        className="globe-card-globe"
      />
      {/* Layer 3: Content with gradient */}
      <div className="globe-card-content">
        {badge && <span className="globe-card-badge">{badge}</span>}
        <h4>{title}</h4>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

// =============================================================================
// LOCATION CONSENT MODAL with OSM Autocomplete
// =============================================================================

interface OSMPlace {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
}

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLocate: () => void;
  onManualEntry: (location: string, lat: number, lng: number) => void;
}

function LocationModal({ isOpen, onClose, onLocate, onManualEntry }: LocationModalProps) {
  const [manualInput, setManualInput] = useState('');
  const [isLocating, setIsLocating] = useState(false);
  const [suggestions, setSuggestions] = useState<OSMPlace[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<number | null>(null);

  // OSM Nominatim autocomplete
  const searchPlaces = async (query: string) => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5&addressdetails=1`,
        { headers: { 'User-Agent': 'CFPPlease/1.0' } }
      );
      const data: OSMPlace[] = await response.json();
      setSuggestions(data);
    } catch (err) {
      console.error('OSM search failed:', err);
      setSuggestions([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleInputChange = (value: string) => {
    setManualInput(value);

    // Debounce search
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = window.setTimeout(() => {
      searchPlaces(value);
    }, 300);
  };

  const handleSelectSuggestion = (place: OSMPlace) => {
    const shortName = place.display_name.split(',').slice(0, 2).join(',');
    setManualInput(shortName);
    setSuggestions([]);
    onManualEntry(shortName, parseFloat(place.lat), parseFloat(place.lon));
  };

  if (!isOpen) return null;

  const handleLocate = () => {
    setIsLocating(true);
    // Use browser geolocation
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          // Reverse geocode to get city name
          try {
            const response = await fetch(
              `https://nominatim.openstreetmap.org/reverse?format=json&lat=${position.coords.latitude}&lon=${position.coords.longitude}`,
              { headers: { 'User-Agent': 'CFPPlease/1.0' } }
            );
            const data = await response.json();
            const city = data.address?.city || data.address?.town || data.address?.village || 'Your Location';
            const country = data.address?.country || '';
            const label = country ? `${city}, ${country}` : city;
            onManualEntry(label, position.coords.latitude, position.coords.longitude);
          } catch {
            onManualEntry('Your Location', position.coords.latitude, position.coords.longitude);
          }
          setIsLocating(false);
        },
        () => {
          setIsLocating(false);
          alert('Could not get your location. Please enter manually.');
        }
      );
    } else {
      setIsLocating(false);
      onLocate();
    }
  };

  return (
    <div className="location-modal-overlay" onClick={onClose}>
      <div className="location-modal" onClick={e => e.stopPropagation()}>
        <button className="location-modal-close" onClick={onClose}>×</button>

        <div className="location-modal-icon">📍</div>
        <h2>Find conferences near you</h2>
        <p className="location-modal-desc">
          Enable location to see CFPs sorted by distance
        </p>

        <button
          className="location-btn location-btn-primary"
          onClick={handleLocate}
          disabled={isLocating}
        >
          {isLocating ? (
            <>
              <span className="location-spinner" />
              Locating...
            </>
          ) : (
            <>
              <span className="location-icon">🎯</span>
              Use my location
            </>
          )}
        </button>

        <div className="location-divider">
          <span>or</span>
        </div>

        <div className="location-manual">
          <div className="location-autocomplete">
            <input
              type="text"
              placeholder="Enter city or country..."
              value={manualInput}
              onChange={e => handleInputChange(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && suggestions.length > 0) {
                  handleSelectSuggestion(suggestions[0]);
                }
              }}
            />
            {isSearching && <span className="location-searching">...</span>}
            {suggestions.length > 0 && (
              <ul className="location-suggestions">
                {suggestions.map(place => (
                  <li key={place.place_id} onClick={() => handleSelectSuggestion(place)}>
                    {place.display_name.split(',').slice(0, 3).join(',')}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <p className="location-modal-footer">
          🔒 Stored locally on your device only
        </p>
      </div>
    </div>
  );
}

// =============================================================================
// NEAR YOU CAROUSEL - Dynamic based on user location
// =============================================================================

interface NearYouCFP {
  name: string;
  location: string;
  distance: string;
  date: string;
  lat: number;
  lng: number;
}

// Sample conferences around the world for demo
const ALL_CONFERENCES: Omit<NearYouCFP, 'distance'>[] = [
  { name: 'RustWeek 2026', location: 'Utrecht, NL', date: 'Jun 10-14', lat: 52.09, lng: 5.10 },
  { name: 'Cloud Native Rejekts', location: 'Amsterdam, NL', date: 'Mar 31', lat: 52.37, lng: 4.89 },
  { name: 'devCampNoord', location: 'Groningen, NL', date: 'May 3', lat: 53.21, lng: 6.59 },
  { name: 'Techorama Belgium', location: 'Antwerp, BE', date: 'May 7-9', lat: 51.22, lng: 4.40 },
  { name: 'DDD North', location: 'Hull, UK', date: 'Feb 22', lat: 53.77, lng: -0.37 },
  { name: 'JSNation', location: 'Amsterdam, NL', date: 'Jun 12-13', lat: 52.38, lng: 4.90 },
  { name: 'React Summit', location: 'Amsterdam, NL', date: 'Jun 14-15', lat: 52.38, lng: 4.90 },
  { name: 'PyCon US', location: 'Pittsburgh, US', date: 'May 14-22', lat: 40.44, lng: -79.99 },
  { name: 'JSConf Budapest', location: 'Budapest, HU', date: 'Jun 26-27', lat: 47.50, lng: 19.04 },
  { name: 'NDC Oslo', location: 'Oslo, NO', date: 'Jun 9-13', lat: 59.91, lng: 10.75 },
  { name: 'Devoxx France', location: 'Paris, FR', date: 'Apr 16-18', lat: 48.85, lng: 2.35 },
  { name: 'DevTernity', location: 'Riga, LV', date: 'Dec 7-8', lat: 56.95, lng: 24.11 },
  { name: 'QCon London', location: 'London, UK', date: 'Apr 7-9', lat: 51.51, lng: -0.13 },
  { name: 'KubeCon EU', location: 'Paris, FR', date: 'Mar 18-21', lat: 48.85, lng: 2.35 },
  { name: 'Codemotion Madrid', location: 'Madrid, ES', date: 'May 20-21', lat: 40.42, lng: -3.70 },
];

// Haversine distance in km
function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}

interface NearYouCarouselProps {
  userLocation?: { lat: number; lng: number; label: string } | null;
  onChangeLocation?: () => void;
}

function NearYouCarousel({ userLocation, onChangeLocation }: NearYouCarouselProps) {
  // Calculate distances and sort by nearest
  const nearYouCfps = React.useMemo<NearYouCFP[]>(() => {
    const baseLat = userLocation?.lat ?? 52.37; // Default: Amsterdam
    const baseLng = userLocation?.lng ?? 4.89;

    return ALL_CONFERENCES
      .map(conf => {
        const distKm = haversineKm(baseLat, baseLng, conf.lat, conf.lng);
        return {
          ...conf,
          distance: distKm < 100 ? `${Math.round(distKm)} km` : `${Math.round(distKm / 10) * 10} km`,
          distKm,
        };
      })
      .sort((a, b) => a.distKm - b.distKm)
      .slice(0, 6);
  }, [userLocation]);

  return (
    <div className="nearyou-carousel">
      <div className="nearyou-header">
        <h3>
          <span className="nearyou-icon">📍</span>
          Near You
        </h3>
        <span className="nearyou-location">
          Based on {userLocation?.label || 'Amsterdam, NL'}
          {onChangeLocation && (
            <button className="nearyou-change" onClick={onChangeLocation}>Change</button>
          )}
        </span>
      </div>

      <div className="nearyou-scroll">
        {nearYouCfps.map((cfp, i) => (
          <div key={i} className="nearyou-card">
            {/* Use simple location dot instead of globe to save WebGL contexts */}
            <div className="nearyou-location-dot" title={cfp.location}>
              <span className="location-dot-icon">📍</span>
            </div>
            <div className="nearyou-card-content">
              <h4>{cfp.name}</h4>
              <div className="nearyou-card-meta">
                <span className="nearyou-distance">{cfp.distance}</span>
                <span className="nearyou-location-text">{cfp.location}</span>
              </div>
              <span className="nearyou-date">{cfp.date}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// MAP TOGGLE PREVIEW
// =============================================================================

const DEMO_CONFERENCES = [
  { name: 'KubeCon EU', location: 'Amsterdam', lat: 52.37, lng: 4.89 },
  { name: 'PyCon US', location: 'Pittsburgh', lat: 40.44, lng: -79.99 },
  { name: 'RustWeek', location: 'Utrecht', lat: 52.09, lng: 5.10 },
  { name: 'JSNation', location: 'Amsterdam', lat: 52.38, lng: 4.90 },
  { name: 'DDD North', location: 'Hull, UK', lat: 53.77, lng: -0.37 },
];

// Custom icon for user location
const userLocationIcon = new L.DivIcon({
  className: 'user-location-marker',
  html: '<div class="user-marker-dot"></div><div class="user-marker-pulse"></div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

interface MapTogglePreviewProps {
  userLocation?: { lat: number; lng: number; label: string } | null;
}

function MapTogglePreview({ userLocation }: MapTogglePreviewProps) {
  const [view, setView] = useState<'list' | 'map'>('list');

  // Center map on user location if available
  const mapCenter: [number, number] = userLocation
    ? [userLocation.lat, userLocation.lng]
    : [50, 10];
  const mapZoom = userLocation ? 5 : 4;

  return (
    <div className="map-toggle-preview">
      <div className="map-toggle-header">
        <span>Search Results</span>
        <div className="map-toggle-buttons">
          <button
            className={view === 'list' ? 'active' : ''}
            onClick={() => setView('list')}
          >
            <span>☰</span> List
          </button>
          <button
            className={view === 'map' ? 'active' : ''}
            onClick={() => setView('map')}
          >
            <span>🗺️</span> Map
          </button>
        </div>
      </div>

      <div className={`map-toggle-content ${view}`}>
        {view === 'list' ? (
          <div className="map-toggle-list">
            {DEMO_CONFERENCES.map((conf, i) => (
              <div key={i} className="map-toggle-list-item">
                <strong>{conf.name}</strong>
                <span>{conf.location}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="map-toggle-map">
            <MapContainer
              center={mapCenter}
              zoom={mapZoom}
              style={{ height: '100%', width: '100%' }}
              scrollWheelZoom={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
              {/* User location marker */}
              {userLocation && (
                <Marker position={[userLocation.lat, userLocation.lng]} icon={userLocationIcon}>
                  <Popup>
                    <strong>📍 You</strong><br />
                    {userLocation.label}
                  </Popup>
                </Marker>
              )}
              {/* Conference markers */}
              {DEMO_CONFERENCES.map((conf, i) => (
                <Marker key={i} position={[conf.lat, conf.lng]}>
                  <Popup>
                    <strong>{conf.name}</strong><br />
                    {conf.location}
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// BADGE EXPERIMENTS
// =============================================================================

function BadgeExperiments() {
  return (
    <div className="badge-experiments">
      <h3>Badge & Highlight Styles</h3>

      <div className="badge-row">
        <span className="badge badge-urgency-critical">3 days left</span>
        <span className="badge badge-urgency-soon">2 weeks</span>
        <span className="badge badge-urgency-normal">1 month</span>
      </div>

      <div className="badge-row">
        <span className="badge badge-format-virtual">🌐 Virtual</span>
        <span className="badge badge-format-inperson">📍 In-person</span>
        <span className="badge badge-format-hybrid">🔄 Hybrid</span>
      </div>

      <div className="badge-row">
        <span className="badge badge-intel badge-intel-hn">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
            <path d="M0 0v24h24V0H0zm12.3 12.5v5.2h-1.3v-5.2L7.5 6.3h1.5l2.7 5 2.6-5h1.5l-3.5 6.2z"/>
          </svg>
          142 pts
        </span>
        <span className="badge badge-intel badge-intel-gh">
          ★ 1.2k stars
        </span>
        <span className="badge badge-intel badge-intel-trending">
          🔥 Trending
        </span>
      </div>

      <div className="badge-row">
        <span className="badge badge-distance">45 km</span>
        <span className="badge badge-distance">210 km</span>
        <span className="badge badge-distance badge-distance-far">1,200 km</span>
      </div>

      <div className="badge-row">
        <span className="badge badge-benefit">✈️ Travel</span>
        <span className="badge badge-benefit">🏨 Hotel</span>
        <span className="badge badge-benefit">🎟️ Free ticket</span>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN DEMO PAGE
// =============================================================================

export function DemoPage() {
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number; label: string } | null>(null);

  const handleLocate = () => {
    // Mock: set to Amsterdam
    setUserLocation({ lat: 52.37, lng: 4.89, label: 'Amsterdam, NL' });
    setShowLocationModal(false);
  };

  const handleManualEntry = (location: string, lat: number, lng: number) => {
    setUserLocation({ lat, lng, label: location });
    setShowLocationModal(false);
  };

  return (
    <div className="demo-page">
      <header className="demo-header">
        <h1>🧪 Design Playground</h1>
        <p>Prototype UI experiments before production</p>
      </header>

      <main className="demo-content">
        {/* Globe as Card Background Layer */}
        <section className="demo-section demo-section-wide">
          <h2>Globe + City Image Card</h2>
          <p className="demo-desc">Layered: city photo + globe overlay + content gradient</p>

          <div className="globe-card-carousel">
            {/* With city image */}
            <GlobeCard
              title="Devoxx France"
              subtitle="Paris, France • Apr 16-18"
              lat={48.85}
              lng={2.35}
              badge="12 days left"
              cityImageUrl="https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=640&q=80"
            />

            {/* With city image */}
            <GlobeCard
              title="JSConf Budapest"
              subtitle="Budapest, Hungary • Jun 26-27"
              lat={47.50}
              lng={19.04}
              badge="45 km"
              cityImageUrl="https://images.unsplash.com/photo-1549923746-c502d488b3ea?w=640&q=80"
            />

            {/* Without city image - globe only */}
            <GlobeCard
              title="RustWeek 2026"
              subtitle="Utrecht, Netherlands • Jun 10-14"
              lat={52.09}
              lng={5.10}
              badge="New"
            />

            {/* Tokyo example */}
            <GlobeCard
              title="RubyKaigi 2026"
              subtitle="Tokyo, Japan • May 15-17"
              lat={35.68}
              lng={139.69}
              badge="Open"
              cityImageUrl="https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=640&q=80"
            />
          </div>
        </section>

        {/* Location Modal */}
        <section className="demo-section">
          <h2>Location Consent Modal</h2>
          <p className="demo-desc">Ask for location with locate-me or manual entry</p>

          <button
            className="demo-trigger-btn"
            onClick={() => setShowLocationModal(true)}
          >
            Open Location Modal
          </button>

          {userLocation && (
            <div className="demo-location-status">
              <GlobeWidget
                lat={userLocation.lat}
                lng={userLocation.lng}
                label={userLocation.label}
                size="sm"
              />
              <span>Location set: {userLocation.label}</span>
            </div>
          )}
        </section>

        {/* Near You Carousel */}
        <section className="demo-section demo-section-wide">
          <h2>Near You Carousel</h2>
          <p className="demo-desc">Geo-sorted CFPs with distance badges</p>

          <NearYouCarousel
            userLocation={userLocation}
            onChangeLocation={() => setShowLocationModal(true)}
          />
        </section>

      </main>

      <LocationModal
        isOpen={showLocationModal}
        onClose={() => setShowLocationModal(false)}
        onLocate={handleLocate}
        onManualEntry={handleManualEntry}
      />

      <footer className="demo-footer">
        <p>🔒 All preferences stored locally on your device</p>
      </footer>
    </div>
  );
}
