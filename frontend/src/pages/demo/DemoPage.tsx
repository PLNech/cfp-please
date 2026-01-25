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
  size?: 'sm' | 'md' | 'lg';
}

const GLOBE_SIZES = { sm: 60, md: 100, lg: 160 };

function GlobeWidget({ lat = 52.37, lng = 4.89, label = 'Amsterdam', size = 'md' }: GlobeWidgetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const globeSize = GLOBE_SIZES[size];

  useEffect(() => {
    if (!canvasRef.current) return;

    let phi = 0;
    const targetPhi = (lng + 90) * (Math.PI / 180);
    const targetTheta = (90 - lat) * (Math.PI / 180) - Math.PI / 2;

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: globeSize * 2,
      height: globeSize * 2,
      phi: targetPhi,
      theta: targetTheta,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: 6,
      baseColor: [0.15, 0.2, 0.25],
      markerColor: [1, 0.3, 0.3],         // Brighter red
      glowColor: [0.1, 0.15, 0.2],
      markers: [
        { location: [lat, lng], size: 0.15 }  // Bigger marker
      ],
      onRender: (state) => {
        state.phi = targetPhi + phi;
        phi += 0.003;
      }
    });

    return () => globe.destroy();
  }, [lat, lng, globeSize]);

  return (
    <div className={`globe-widget globe-${size}`} title={label}>
      <canvas
        ref={canvasRef}
        style={{
          width: globeSize,
          height: globeSize,
          maxWidth: '100%',
          aspectRatio: '1',
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
}

function GlobeCard({ title, subtitle, lat, lng, badge }: GlobeCardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    let phi = 0;
    const targetPhi = (lng + 90) * (Math.PI / 180);
    const targetTheta = (90 - lat) * (Math.PI / 180) - Math.PI / 2;

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: 400,
      height: 400,
      phi: targetPhi,
      theta: targetTheta,
      dark: 1,
      diffuse: 0.8,
      mapSamples: 20000,
      mapBrightness: 4,
      baseColor: [0.1, 0.15, 0.2],
      markerColor: [1, 0.3, 0.3],
      glowColor: [0.05, 0.1, 0.15],
      markers: [
        { location: [lat, lng], size: 0.12 }
      ],
      onRender: (state) => {
        state.phi = targetPhi + phi;
        phi += 0.002;
      }
    });

    return () => globe.destroy();
  }, [lat, lng]);

  return (
    <div className="globe-card">
      <canvas
        ref={canvasRef}
        className="globe-card-bg"
      />
      <div className="globe-card-content">
        {badge && <span className="globe-card-badge">{badge}</span>}
        <h4>{title}</h4>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

// =============================================================================
// LOCATION CONSENT MODAL
// =============================================================================

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLocate: () => void;
  onManualEntry: (location: string) => void;
}

function LocationModal({ isOpen, onClose, onLocate, onManualEntry }: LocationModalProps) {
  const [manualInput, setManualInput] = useState('');
  const [isLocating, setIsLocating] = useState(false);

  if (!isOpen) return null;

  const handleLocate = () => {
    setIsLocating(true);
    // Simulate geolocation
    setTimeout(() => {
      setIsLocating(false);
      onLocate();
    }, 1500);
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
          <input
            type="text"
            placeholder="Enter city or country..."
            value={manualInput}
            onChange={e => setManualInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && manualInput && onManualEntry(manualInput)}
          />
          <button
            className="location-btn location-btn-secondary"
            disabled={!manualInput}
            onClick={() => onManualEntry(manualInput)}
          >
            Set
          </button>
        </div>

        <p className="location-modal-footer">
          🔒 Stored locally on your device only
        </p>
      </div>
    </div>
  );
}

// =============================================================================
// NEAR YOU CAROUSEL (Mock)
// =============================================================================

interface NearYouCFP {
  name: string;
  location: string;
  distance: string;
  date: string;
  lat: number;
  lng: number;
}

const MOCK_NEAR_YOU: NearYouCFP[] = [
  { name: 'RustWeek 2026', location: 'Utrecht, NL', distance: '45 km', date: 'Jun 10-14', lat: 52.09, lng: 5.10 },
  { name: 'Cloud Native Rejekts', location: 'Amsterdam, NL', distance: '52 km', date: 'Mar 31', lat: 52.37, lng: 4.89 },
  { name: 'devCampNoord', location: 'Groningen, NL', distance: '180 km', date: 'May 3', lat: 53.21, lng: 6.59 },
  { name: 'Techorama Belgium', location: 'Antwerp, BE', distance: '210 km', date: 'May 7-9', lat: 51.22, lng: 4.40 },
  { name: 'DDD North', location: 'Hull, UK', distance: '450 km', date: 'Feb 22', lat: 53.77, lng: -0.37 },
];

function NearYouCarousel() {
  const [userLocation, setUserLocation] = useState<string | null>('Amsterdam, NL');

  return (
    <div className="nearyou-carousel">
      <div className="nearyou-header">
        <h3>
          <span className="nearyou-icon">📍</span>
          Near You
        </h3>
        {userLocation && (
          <span className="nearyou-location">
            Based on {userLocation}
            <button className="nearyou-change">Change</button>
          </span>
        )}
      </div>

      <div className="nearyou-scroll">
        {MOCK_NEAR_YOU.map((cfp, i) => (
          <div key={i} className="nearyou-card">
            <GlobeWidget lat={cfp.lat} lng={cfp.lng} size="sm" />
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

function MapTogglePreview() {
  const [view, setView] = useState<'list' | 'map'>('list');

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
              center={[50, 10]}
              zoom={4}
              style={{ height: '100%', width: '100%' }}
              scrollWheelZoom={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
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

  const handleManualEntry = (location: string) => {
    // Mock: use entered location
    setUserLocation({ lat: 48.85, lng: 2.35, label: location });
    setShowLocationModal(false);
  };

  return (
    <div className="demo-page">
      <header className="demo-header">
        <h1>🧪 Design Playground</h1>
        <p>Prototype UI experiments before production</p>
      </header>

      <main className="demo-content">
        {/* Globe Widget */}
        <section className="demo-section">
          <h2>Globe Widget</h2>
          <p className="demo-desc">Tiny dark globe with glowing location dot</p>

          <div className="demo-row">
            <GlobeWidget lat={52.37} lng={4.89} label="Amsterdam" size="sm" />
            <GlobeWidget lat={40.71} lng={-74.01} label="New York" size="md" />
            <GlobeWidget lat={35.68} lng={139.69} label="Tokyo" size="lg" />
          </div>

          <div className="demo-row">
            <GlobeWidget lat={-33.87} lng={151.21} label="Sydney" size="md" />
            <GlobeWidget lat={51.51} lng={-0.13} label="London" size="md" />
            <GlobeWidget lat={48.85} lng={2.35} label="Paris" size="md" />
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

          <NearYouCarousel />
        </section>

        {/* Map Toggle */}
        <section className="demo-section">
          <h2>Map Toggle (Search Page)</h2>
          <p className="demo-desc">Switch between list and map views</p>

          <MapTogglePreview />
        </section>

        {/* Badges */}
        <section className="demo-section">
          <BadgeExperiments />
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
