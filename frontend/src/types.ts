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

// Satellite design system colors
export function getUrgencyColor(level: UrgencyLevel): string {
  switch (level) {
    case 'critical': return '#E5484D'; // Satellite red
    case 'warning': return '#F5A623';  // Satellite amber
    case 'ok': return '#30A46C';       // Satellite green
    default: return '#5A5E9A';         // Satellite secondary
  }
}
