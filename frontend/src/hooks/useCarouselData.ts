/**
 * useCarouselData - Multi-index Algolia queries for carousel rows
 *
 * Fetches data for all carousel categories with proper caching.
 */

import { useState, useEffect, useCallback } from 'react';
import { algoliasearch } from 'algoliasearch';
import type { SearchClient } from 'algoliasearch';
import {
  ALGOLIA_APP_ID,
  ALGOLIA_SEARCH_KEY,
  ALGOLIA_INDEX_NAME,
  ALGOLIA_TALKS_INDEX,
} from '../config';
import type { CFP, Talk, UserProfile, CarouselConfig } from '../types';

// Initialize Algolia client (singleton)
let algoliaClient: SearchClient | null = null;

function getClient(): SearchClient {
  if (!algoliaClient) {
    algoliaClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
  }
  return algoliaClient;
}

// Get current timestamp for filtering open CFPs
function getNowTimestamp(): number {
  return Math.floor(Date.now() / 1000);
}

interface CarouselData {
  id: string;
  items: (CFP | Talk)[];
  loading: boolean;
  error: string | null;
}

interface UseCarouselDataResult {
  carousels: Map<string, CarouselData>;
  hero: CFP | null;
  heroLoading: boolean;
  refetch: () => void;
}

export function useCarouselData(
  configs: CarouselConfig[],
  _profile: UserProfile  // Reserved for future match score calculation
): UseCarouselDataResult {
  const [carousels, setCarousels] = useState<Map<string, CarouselData>>(new Map());
  const [hero, setHero] = useState<CFP | null>(null);
  const [heroLoading, setHeroLoading] = useState(true);

  const fetchCarousel = useCallback(async (config: CarouselConfig): Promise<CarouselData> => {
    const client = getClient();
    const indexName = config.index === 'cfps_talks' ? ALGOLIA_TALKS_INDEX : ALGOLIA_INDEX_NAME;

    try {
      // Build filters
      let filters = config.filters || '';
      const now = getNowTimestamp();

      // Add open CFP filter for cfps index (skip if already has cfpEndDate filter)
      if (config.index === 'cfps' && !filters.includes('cfpEndDate')) {
        const openFilter = `cfpEndDate > ${now}`;
        filters = filters ? `${filters} AND ${openFilter}` : openFilter;
      }

      const response = await client.searchSingleIndex({
        indexName,
        searchParams: {
          query: '',
          filters,
          hitsPerPage: config.limit || 20,
        },
      });

      return {
        id: config.id,
        items: response.hits as (CFP | Talk)[],
        loading: false,
        error: null,
      };
    } catch (e) {
      console.error(`Error fetching carousel ${config.id}:`, e);
      return {
        id: config.id,
        items: [],
        loading: false,
        error: e instanceof Error ? e.message : 'Unknown error',
      };
    }
  }, []);

  const fetchHero = useCallback(async (): Promise<CFP | null> => {
    const client = getClient();
    const now = getNowTimestamp();

    try {
      // Get CFPs closing within 14 days, sorted by popularity
      const response = await client.searchSingleIndex({
        indexName: ALGOLIA_INDEX_NAME,
        searchParams: {
          query: '',
          filters: `cfpEndDate > ${now} AND cfpEndDate < ${now + 14 * 86400}`,
          hitsPerPage: 10,
        },
      });

      const cfps = response.hits as CFP[];

      // Pick the most popular one, or the one closing soonest if no popularity data
      const withPopularity = cfps.filter((c) => c.popularityScore && c.popularityScore > 0);
      if (withPopularity.length > 0) {
        return withPopularity.sort((a, b) => (b.popularityScore || 0) - (a.popularityScore || 0))[0];
      }

      // Fallback: closest deadline
      return cfps.sort((a, b) => (a.cfpEndDate || Infinity) - (b.cfpEndDate || Infinity))[0] || null;
    } catch (e) {
      console.error('Error fetching hero CFP:', e);
      return null;
    }
  }, []);

  const fetchAll = useCallback(async () => {
    // Set loading state while preserving existing data (prevents flash)
    setCarousels(prev => {
      const updated = new Map(prev);
      configs.forEach((config) => {
        const existing = updated.get(config.id);
        if (existing) {
          // Keep existing items while loading
          updated.set(config.id, { ...existing, loading: true });
        } else {
          // New carousel, initialize loading
          updated.set(config.id, {
            id: config.id,
            items: [],
            loading: true,
            error: null,
          });
        }
      });
      return updated;
    });
    setHeroLoading(true);

    // Fetch hero and all carousels in parallel
    const [heroResult, ...carouselResults] = await Promise.all([
      fetchHero(),
      ...configs.map(fetchCarousel),
    ]);

    setHero(heroResult);
    setHeroLoading(false);

    const newCarousels = new Map<string, CarouselData>();
    carouselResults.forEach((result) => {
      newCarousels.set(result.id, result);
    });
    setCarousels(newCarousels);
  }, [configs, fetchCarousel, fetchHero]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    carousels,
    hero,
    heroLoading,
    refetch: fetchAll,
  };
}

// Dynamic carousel configs based on user profile
export function buildCarouselConfigs(profile: UserProfile): CarouselConfig[] {
  const configs: CarouselConfig[] = [];
  const now = getNowTimestamp();

  // Hot Deadlines (always first)
  configs.push({
    id: 'hot-deadlines',
    title: 'Hot Deadlines',
    icon: '🔥',
    index: 'cfps',
    filters: `cfpEndDate > ${now} AND cfpEndDate < ${now + 7 * 86400}`,
    limit: 20,
  });

  // Personalized rows based on profile topics
  if (profile.topics.length > 0) {
    const topicFilter = profile.topics
      .map((t) => `topicsNormalized:"${t}"`)
      .join(' OR ');

    configs.push({
      id: 'for-you',
      title: `Because you like ${profile.topics.slice(0, 2).join(' & ')}`,
      icon: '💡',
      index: 'cfps',
      filters: `(${topicFilter}) AND cfpEndDate > ${now}`,
      limit: 15,
    });
  }

  // Trending on HN
  configs.push({
    id: 'trending-hn',
    title: 'Trending on HN',
    icon: '📈',
    index: 'cfps',
    filters: `hnStories > 0 AND cfpEndDate > ${now}`,
    limit: 15,
  });

  // GitHub Buzz
  configs.push({
    id: 'github-buzz',
    title: 'GitHub Buzz',
    icon: '💻',
    index: 'cfps',
    filters: `githubRepos > 0 AND cfpEndDate > ${now}`,
    limit: 15,
  });

  // Viral Talks
  configs.push({
    id: 'viral-talks',
    title: 'Talks That Went Viral',
    icon: '🎬',
    index: 'cfps_talks',
    filters: 'view_count > 10000',
    limit: 20,
  });

  // Topic-specific talks if profile set
  if (profile.topics.length > 0) {
    const topic = profile.topics[0];
    configs.push({
      id: `talks-${topic.toLowerCase().replace(/[^a-z]/g, '')}`,
      title: `${topic} Deep Dives`,
      icon: '🎯',
      index: 'cfps_talks',
      filters: `topics:"${topic}"`,
      limit: 15,
    });
  }

  return configs;
}
