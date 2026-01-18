/**
 * useSpeakers - Fetch speakers from Algolia cfps_speakers index
 *
 * Provides hooks for top speakers, speakers by topic, etc.
 */

import { useState, useEffect, useCallback } from 'react';
import { algoliasearch } from 'algoliasearch';
import type { SearchClient } from 'algoliasearch';
import {
  ALGOLIA_APP_ID,
  ALGOLIA_SEARCH_KEY,
  ALGOLIA_SPEAKERS_INDEX,
} from '../config';
import type { Speaker } from '../types';

// Reuse client singleton
let algoliaClient: SearchClient | null = null;

function getClient(): SearchClient {
  if (!algoliaClient) {
    algoliaClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
  }
  return algoliaClient;
}

interface UseSpeakersResult {
  speakers: Speaker[];
  loading: boolean;
  error: string | null;
}

/**
 * Fetch top speakers by influence score
 */
export function useTopSpeakers(limit = 15): UseSpeakersResult {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSpeakers = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const client = getClient();
      const response = await client.searchSingleIndex({
        indexName: ALGOLIA_SPEAKERS_INDEX,
        searchParams: {
          query: '',
          hitsPerPage: limit,
          // Sort by influence_score (descending) - assumes replica or virtual replica
          // Fallback: just use main index, top records by default ranking
        },
      });

      // Convert hits to Speaker type
      const results = (response.hits as unknown as Speaker[]).map((hit) => ({
        ...hit,
        objectID: hit.objectID || (hit as any).object_id,
      }));

      // Sort by influence score if available
      results.sort((a, b) => (b.influence_score || 0) - (a.influence_score || 0));

      setSpeakers(results);
    } catch (e) {
      console.error('Error fetching top speakers:', e);
      setError(e instanceof Error ? e.message : 'Unknown error');
      setSpeakers([]);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  return { speakers, loading, error };
}

/**
 * Fetch speakers by topic
 */
export function useSpeakersByTopic(topic: string | null, limit = 10): UseSpeakersResult {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSpeakers = useCallback(async () => {
    if (!topic) {
      setSpeakers([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const client = getClient();
      const response = await client.searchSingleIndex({
        indexName: ALGOLIA_SPEAKERS_INDEX,
        searchParams: {
          query: '',
          filters: `topics:"${topic}"`,
          hitsPerPage: limit,
        },
      });

      const results = (response.hits as unknown as Speaker[]).map((hit) => ({
        ...hit,
        objectID: hit.objectID || (hit as any).object_id,
      }));

      // Sort by influence within topic
      results.sort((a, b) => (b.influence_score || 0) - (a.influence_score || 0));

      setSpeakers(results);
    } catch (e) {
      console.error(`Error fetching speakers for topic "${topic}":`, e);
      setError(e instanceof Error ? e.message : 'Unknown error');
      setSpeakers([]);
    } finally {
      setLoading(false);
    }
  }, [topic, limit]);

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  return { speakers, loading, error };
}

/**
 * Fetch followed speakers by IDs
 */
export function useFollowedSpeakers(speakerIds: string[]): UseSpeakersResult {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSpeakers = useCallback(async () => {
    if (speakerIds.length === 0) {
      setSpeakers([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const client = getClient();

      // Fetch speakers by IDs
      const response = await client.getObjects<Speaker>({
        requests: speakerIds.map((id) => ({
          indexName: ALGOLIA_SPEAKERS_INDEX,
          objectID: id,
        })),
      });

      // Filter out null results and maintain order
      const validSpeakers = response.results.filter((r): r is Speaker => r !== null);

      // Sort by original ID order
      const orderedSpeakers = speakerIds
        .map((id) => validSpeakers.find((s) => s.objectID === id))
        .filter((s): s is Speaker => s !== undefined);

      setSpeakers(orderedSpeakers);
    } catch (e) {
      console.error('Error fetching followed speakers:', e);
      setError(e instanceof Error ? e.message : 'Unknown error');
      setSpeakers([]);
    } finally {
      setLoading(false);
    }
  }, [speakerIds]);

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  return { speakers, loading, error };
}
