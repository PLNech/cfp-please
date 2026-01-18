/**
 * useTalksByIds - Fetch talks from Algolia by objectID
 *
 * Used for Continue Watching and Favorites carousels.
 */

import { useState, useEffect, useCallback } from 'react';
import { algoliasearch } from 'algoliasearch';
import type { SearchClient } from 'algoliasearch';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, ALGOLIA_TALKS_INDEX } from '../config';
import type { Talk } from '../types';

// Reuse client singleton
let algoliaClient: SearchClient | null = null;

function getClient(): SearchClient {
  if (!algoliaClient) {
    algoliaClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
  }
  return algoliaClient;
}

interface UseTalksByIdsResult {
  talks: Talk[];
  loading: boolean;
  error: string | null;
}

export function useTalksByIds(talkIds: string[], limit = 10): UseTalksByIdsResult {
  const [talks, setTalks] = useState<Talk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTalks = useCallback(async () => {
    if (talkIds.length === 0) {
      setTalks([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const client = getClient();
      const idsToFetch = talkIds.slice(0, limit);

      // Use getObjects to fetch by IDs directly
      const response = await client.getObjects<Talk>({
        requests: idsToFetch.map((id) => ({
          indexName: ALGOLIA_TALKS_INDEX,
          objectID: id,
        })),
      });

      // Filter out null results and maintain order
      const validTalks = response.results.filter((r): r is Talk => r !== null);

      // Sort by original ID order (most recently watched first)
      const orderedTalks = idsToFetch
        .map((id) => validTalks.find((t) => t.objectID === id))
        .filter((t): t is Talk => t !== undefined);

      setTalks(orderedTalks);
    } catch (e) {
      console.error('Error fetching talks by IDs:', e);
      setError(e instanceof Error ? e.message : 'Unknown error');
      setTalks([]);
    } finally {
      setLoading(false);
    }
  }, [talkIds, limit]);

  useEffect(() => {
    fetchTalks();
  }, [fetchTalks]);

  return { talks, loading, error };
}
