// CFP data types matching Algolia index schema

export interface Location {
  city?: string;
  state?: string;
  country?: string;
  region?: string;
  continent?: string;
  raw?: string;
}

export interface GeoLoc {
  lat: number;
  lng: number;
}

export interface CFP {
  objectID: string;
  name: string;
  description?: string;

  // URLs
  url?: string;
  cfpUrl?: string;
  iconUrl?: string;

  // CFP Dates (timestamps for filtering)
  cfpStartDate?: number;
  cfpEndDate?: number;
  cfpStartDateISO?: string;
  cfpEndDateISO?: string;

  // Event Dates
  eventStartDate?: number;
  eventEndDate?: number;
  eventStartDateISO?: string;
  eventEndDateISO?: string;

  // Location
  location: Location;
  _geoloc?: GeoLoc;

  // Topics
  topics: string[];
  topicsNormalized: string[];

  // Enrichment fields
  languages: string[];
  technologies: string[];
  audienceLevel?: string;
  eventFormat?: string;
  talkTypes: string[];
  industries: string[];

  // Meta
  source: string;
  enriched: boolean;
  daysUntilCfpClose?: number;
}

// Urgency levels for deadline display
export type UrgencyLevel = 'critical' | 'warning' | 'ok' | 'unknown';

export function getUrgencyLevel(daysUntilClose?: number): UrgencyLevel {
  if (daysUntilClose === undefined || daysUntilClose === null) return 'unknown';
  if (daysUntilClose <= 7) return 'critical';
  if (daysUntilClose <= 30) return 'warning';
  return 'ok';
}

export function getUrgencyColor(level: UrgencyLevel): string {
  switch (level) {
    case 'critical': return '#ef4444'; // red
    case 'warning': return '#f59e0b';  // amber
    case 'ok': return '#22c55e';       // green
    default: return '#6b7280';         // gray
  }
}
