/**
 * useRecommend - Algolia Recommend for related items
 *
 * Uses content-based filtering for related talks/CFPs.
 */

import { useState, useEffect } from 'react';
import { recommendClient } from '@algolia/recommend';
import { ALGOLIA_APP_ID, ALGOLIA_TALKS_INDEX, ALGOLIA_INDEX_NAME } from '../config';
import type { Talk, CFP } from '../types';

// Initialize Recommend client
const client = recommendClient(
  ALGOLIA_APP_ID,
  import.meta.env.VITE_ALGOLIA_SEARCH_KEY || ''
);

interface UseRelatedTalksResult {
  relatedTalks: Talk[];
  loading: boolean;
  error: string | null;
}

interface UseRelatedCFPsResult {
  relatedCFPs: CFP[];
  loading: boolean;
  error: string | null;
}

/**
 * Get talks related to a given talk
 */
export function useRelatedTalks(
  talkObjectID: string | null,
  limit: number = 6
): UseRelatedTalksResult {
  const [relatedTalks, setRelatedTalks] = useState<Talk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!talkObjectID) {
      setRelatedTalks([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    client
      .getRecommendations({
        requests: [
          {
            indexName: ALGOLIA_TALKS_INDEX,
            objectID: talkObjectID,
            model: 'related-products',
            maxRecommendations: limit,
            threshold: 0,
          },
        ],
      })
      .then((response) => {
        if (cancelled) return;

        const results = response.results[0];
        if (results && 'hits' in results) {
          setRelatedTalks(results.hits as unknown as Talk[]);
        } else {
          setRelatedTalks([]);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        console.error('Error fetching related talks:', err);
        setError(err.message || 'Failed to fetch related talks');
        setRelatedTalks([]);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [talkObjectID, limit]);

  return { relatedTalks, loading, error };
}

/**
 * Get CFPs related to a given CFP
 */
export function useRelatedCFPs(
  cfpObjectID: string | null,
  limit: number = 6
): UseRelatedCFPsResult {
  const [relatedCFPs, setRelatedCFPs] = useState<CFP[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cfpObjectID) {
      setRelatedCFPs([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    client
      .getRecommendations({
        requests: [
          {
            indexName: ALGOLIA_INDEX_NAME,
            objectID: cfpObjectID,
            model: 'related-products',
            maxRecommendations: limit,
            threshold: 0,
          },
        ],
      })
      .then((response) => {
        if (cancelled) return;

        const results = response.results[0];
        if (results && 'hits' in results) {
          setRelatedCFPs(results.hits as unknown as CFP[]);
        } else {
          setRelatedCFPs([]);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        console.error('Error fetching related CFPs:', err);
        setError(err.message || 'Failed to fetch related CFPs');
        setRelatedCFPs([]);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [cfpObjectID, limit]);

  return { relatedCFPs, loading, error };
}

/**
 * Get trending talks (most clicked/viewed recently)
 */
export function useTrendingTalks(limit: number = 10): UseRelatedTalksResult {
  const [trendingTalks, setTrendingTalks] = useState<Talk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    client
      .getRecommendations({
        requests: [
          {
            indexName: ALGOLIA_TALKS_INDEX,
            model: 'trending-items',
            maxRecommendations: limit,
            threshold: 0,
          },
        ],
      })
      .then((response) => {
        if (cancelled) return;

        const results = response.results[0];
        if (results && 'hits' in results) {
          setTrendingTalks(results.hits as unknown as Talk[]);
        } else {
          setTrendingTalks([]);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        console.error('Error fetching trending talks:', err);
        setError(err.message || 'Failed to fetch trending talks');
        setTrendingTalks([]);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [limit]);

  return { relatedTalks: trendingTalks, loading, error };
}

/**
 * Get frequently bought together (talks often watched together)
 */
export function useFrequentlyWatchedTogether(
  talkObjectID: string | null,
  limit: number = 4
): UseRelatedTalksResult {
  const [talks, setTalks] = useState<Talk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!talkObjectID) {
      setTalks([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    client
      .getRecommendations({
        requests: [
          {
            indexName: ALGOLIA_TALKS_INDEX,
            objectID: talkObjectID,
            model: 'bought-together',
            maxRecommendations: limit,
            threshold: 0,
          },
        ],
      })
      .then((response) => {
        if (cancelled) return;

        const results = response.results[0];
        if (results && 'hits' in results) {
          setTalks(results.hits as unknown as Talk[]);
        } else {
          setTalks([]);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        // FBT requires training data, gracefully handle no results
        console.log('FBT not available yet:', err.message);
        setTalks([]);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [talkObjectID, limit]);

  return { relatedTalks: talks, loading, error };
}
