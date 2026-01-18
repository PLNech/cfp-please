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

  // Intel data (from HN, GitHub, Reddit, DEV.to)
  popularityScore?: number;
  hnStories?: number;
  hnPoints?: number;
  githubRepos?: number;
  githubStars?: number;
  redditPosts?: number;
  redditSubreddits?: string[];
  devtoArticles?: number;
  intelEnriched?: boolean;

  // Meta
  source: string;
  enriched: boolean;
  daysUntilCfpClose?: number;
}

// Talk from YouTube (cfps_talks index)
export interface Talk {
  objectID: string;
  conference_id: string;
  conference_name: string;
  conference_slug?: string;
  title: string;
  speaker?: string;
  speakers?: string[];
  description?: string;
  url: string;
  thumbnail_url?: string;
  channel?: string;
  duration_seconds?: number;
  duration_minutes?: number;
  view_count?: number;
  year?: number;
  topics?: string[];
  languages?: string[];
  popularity_score?: number;
}

// User profile for personalization (localStorage)
export interface UserProfile {
  topics: string[];
  experienceLevel: 'beginner' | 'intermediate' | 'advanced';
  preferredFormats: ('in-person' | 'virtual' | 'hybrid')[];
  viewedCFPs: string[];
  savedCFPs: string[];
}

export const DEFAULT_PROFILE: UserProfile = {
  topics: [],
  experienceLevel: 'intermediate',
  preferredFormats: [],
  viewedCFPs: [],
  savedCFPs: [],
};

// Carousel configuration
export interface CarouselConfig {
  id: string;
  title: string;
  icon: string;
  index: 'cfps' | 'cfps_talks';
  filters?: string;
  sort?: string;
  limit?: number;
  dynamicTitle?: (profile: UserProfile) => string;
}

// Predefined carousel categories
export const CAROUSEL_CONFIGS: CarouselConfig[] = [
  {
    id: 'hot-deadlines',
    title: 'Hot Deadlines',
    icon: '🔥',
    index: 'cfps',
    filters: 'daysUntilCfpClose <= 7 AND daysUntilCfpClose >= 0',
    sort: 'daysUntilCfpClose:asc',
    limit: 20,
  },
  {
    id: 'trending-hn',
    title: 'Trending on HN',
    icon: '📈',
    index: 'cfps',
    filters: 'hnStories > 0',
    sort: 'hnPoints:desc',
    limit: 15,
  },
  {
    id: 'github-buzz',
    title: 'GitHub Buzz',
    icon: '💻',
    index: 'cfps',
    filters: 'githubRepos > 0',
    sort: 'githubStars:desc',
    limit: 15,
  },
  {
    id: 'viral-talks',
    title: 'Talks That Went Viral',
    icon: '🎬',
    index: 'cfps_talks',
    filters: 'view_count > 10000',
    sort: 'popularity_score:desc',
    limit: 20,
  },
];

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
