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

  // City hero images (from Unsplash)
  city_image_urls?: string[];    // 5 high-res URLs for variety
  city_image_thumbs?: string[];  // Thumbnail versions

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
  conference_location?: string;
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

  // City hero images (from Unsplash, inherited from conference)
  city_image_urls?: string[];
  city_image_thumbs?: string[];

  // Transcript enrichment
  transcript_enriched?: boolean;
  transcript_summary?: string;
  transcript_keywords?: string[];
  transcript_topics?: string[];
  transcript_bangers?: string[];  // Quotable punchlines
}

// Speaker from cfps_speakers index
export interface Speaker {
  objectID: string;
  name: string;
  aliases?: string[];
  company?: string;
  is_algolia_speaker?: boolean;

  // Stats
  talk_count: number;
  total_views: number;
  max_views: number;
  avg_views?: number;
  influence_score?: number;
  consistency_score?: number;

  // Timeline
  years_active: number[];
  first_talk_year?: number;
  latest_talk_year?: number;
  active_years?: number;

  // Topics & Conferences
  topics: string[];
  topic_counts?: Record<string, number>;
  conferences: string[];
  conference_counts?: Record<string, number>;
  conference_count?: number;

  // Talk references
  top_talk_ids: string[];
  all_talk_ids: string[];

  // Links
  profile_url?: string;
  twitter?: string;
  linkedin?: string;
  github?: string;

  // Achievements
  achievements: string[];
}

// Interview profile from AI conversation
export interface InterviewProfile {
  role?: string;                    // "Frontend Engineer", "DevRel", "Engineering Manager"
  company?: string;                 // Company name or type ("Startup", "Enterprise")
  techStack?: string[];             // ["React", "TypeScript", "Kubernetes"]
  sideProjects?: string[];          // Brief descriptions of side projects
  interests?: string[];             // ["AI/ML", "Open Source", "Developer Experience"]
  speakingTopics?: string[];        // Topics they'd like to speak about
  travelWants?: string[];           // Cities/countries they want to visit
  travelAvoids?: string[];          // Places to avoid (visa issues, preferences)
  speakingExperience?: 'none' | 'meetups' | 'regional' | 'international';
  goals?: string[];                 // ["Get first talk", "Speak internationally", "Build personal brand"]
  interviewedAt?: number;           // Timestamp of last interview
  rawResponses?: Record<string, string>; // Raw Q&A for context
}

// User profile for personalization (localStorage)
export interface UserProfile {
  topics: string[];
  experienceLevel: 'beginner' | 'intermediate' | 'advanced';
  preferredFormats: ('in-person' | 'virtual' | 'hybrid')[];
  viewedCFPs: string[];
  savedCFPs: string[];
  // TalkFlix Phase 2: Talk & Speaker tracking
  watchedTalks: string[];      // Last 50 talk IDs (most recent first)
  favoriteTalks: string[];     // Bookmarked talks (max 50)
  favoriteSpeakers: string[];  // Followed speakers (max 20)
  // Interview-based profile (from AI conversation)
  interview?: InterviewProfile;
}

export const DEFAULT_PROFILE: UserProfile = {
  topics: [],
  experienceLevel: 'intermediate',
  preferredFormats: [],
  viewedCFPs: [],
  savedCFPs: [],
  watchedTalks: [],
  favoriteTalks: [],
  favoriteSpeakers: [],
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
