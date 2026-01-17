import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { CFP } from '../types';
import { getUrgencyLevel, getUrgencyColor } from '../types';

// Fix Leaflet default marker icon issue
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

interface CFPMapProps {
  hits: CFP[];
  onMarkerClick?: (cfp: CFP) => void;
  selectedCfp?: CFP | null;
}

// Create colored marker icons
function createMarkerIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'cfp-map-marker',
    html: `
      <svg width="24" height="36" viewBox="0 0 24 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24c0-6.6-5.4-12-12-12z" fill="${color}"/>
        <circle cx="12" cy="12" r="6" fill="white"/>
      </svg>
    `,
    iconSize: [24, 36],
    iconAnchor: [12, 36],
    popupAnchor: [0, -36],
  });
}

// Component to fit bounds when hits change
function FitBounds({ hits }: { hits: CFP[] }) {
  const map = useMap();

  useEffect(() => {
    const geoHits = hits.filter((h) => h._geoloc?.lat && h._geoloc?.lng);
    if (geoHits.length === 0) return;

    const bounds = L.latLngBounds(
      geoHits.map((h) => [h._geoloc!.lat, h._geoloc!.lng])
    );

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    }
  }, [hits, map]);

  return null;
}

export function CFPMap({ hits, onMarkerClick }: CFPMapProps) {
  // Filter to hits with geolocation
  const geoHits = useMemo(
    () => hits.filter((h) => h._geoloc?.lat && h._geoloc?.lng),
    [hits]
  );

  // Memoize marker icons
  const markerIcons = useMemo(() => ({
    critical: createMarkerIcon(getUrgencyColor('critical')),
    warning: createMarkerIcon(getUrgencyColor('warning')),
    ok: createMarkerIcon(getUrgencyColor('ok')),
    unknown: createMarkerIcon(getUrgencyColor('unknown')),
  }), []);

  if (geoHits.length === 0) {
    return (
      <div className="cfp-map-empty">
        <p>No conferences with location data</p>
      </div>
    );
  }

  const center: [number, number] = [30, 0]; // Global view

  return (
    <MapContainer
      center={center}
      zoom={2}
      className="cfp-map"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds hits={geoHits} />

      {geoHits.map((cfp) => {
        const urgency = getUrgencyLevel(cfp.daysUntilCfpClose);

        return (
          <Marker
            key={cfp.objectID}
            position={[cfp._geoloc!.lat, cfp._geoloc!.lng]}
            icon={markerIcons[urgency]}
            eventHandlers={{
              click: () => onMarkerClick?.(cfp),
            }}
          >
            <Popup>
              <div className="cfp-map-popup">
                <strong>{cfp.name}</strong>
                <p>
                  {cfp.location?.city && `${cfp.location.city}, `}
                  {cfp.location?.country}
                </p>
                {cfp.cfpEndDateISO && (
                  <p className="cfp-map-popup-deadline">
                    CFP closes: {new Date(cfp.cfpEndDateISO).toLocaleDateString()}
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
