/**
 * useInsights - Algolia Insights for click/conversion tracking
 *
 * Sends events to train Recommend models and power analytics.
 */

import { useCallback, useEffect, useRef } from 'react';
import aa from 'search-insights';
import { ALGOLIA_APP_ID, ALGOLIA_INDEX_NAME, ALGOLIA_TALKS_INDEX } from '../config';

// Initialize Insights client once
let initialized = false;

function initInsights() {
  if (initialized) return;

  aa('init', {
    appId: ALGOLIA_APP_ID,
    apiKey: import.meta.env.VITE_ALGOLIA_SEARCH_KEY || '',
    useCookie: true, // Persist userToken across sessions
  });

  initialized = true;
}

// Generate anonymous user token
function getUserToken(): string {
  const key = 'cfp_user_token';
  let token = localStorage.getItem(key);

  if (!token) {
    token = `anon_${Math.random().toString(36).substring(2, 15)}`;
    localStorage.setItem(key, token);
  }

  return token;
}

export interface InsightsEvents {
  // Track when user clicks a CFP
  clickCFP: (objectID: string, position?: number, queryID?: string) => void;

  // Track when user clicks a Talk
  clickTalk: (objectID: string, position?: number, queryID?: string) => void;

  // Track when user submits to a CFP (conversion)
  convertCFP: (objectID: string, queryID?: string) => void;

  // Track when user watches a talk video (conversion)
  watchTalk: (objectID: string, queryID?: string) => void;

  // Track "Inspire Me" clicks
  clickInspire: (talkObjectID: string) => void;

  // Track carousel views (for trending)
  viewCarousel: (carouselId: string, objectIDs: string[]) => void;
}

export function useInsights(): InsightsEvents {
  const userToken = useRef<string>('');

  useEffect(() => {
    initInsights();
    userToken.current = getUserToken();
    aa('setUserToken', userToken.current);
  }, []);

  const clickCFP = useCallback((objectID: string, position?: number, queryID?: string) => {
    if (queryID) {
      aa('clickedObjectIDsAfterSearch', {
        eventName: 'CFP Clicked',
        index: ALGOLIA_INDEX_NAME,
        objectIDs: [objectID],
        userToken: userToken.current,
        positions: position !== undefined ? [position] : [1],
        queryID,
      });
    } else {
      aa('clickedObjectIDs', {
        eventName: 'CFP Clicked',
        index: ALGOLIA_INDEX_NAME,
        objectIDs: [objectID],
        userToken: userToken.current,
      });
    }
  }, []);

  const clickTalk = useCallback((objectID: string, position?: number, queryID?: string) => {
    if (queryID) {
      aa('clickedObjectIDsAfterSearch', {
        eventName: 'Talk Clicked',
        index: ALGOLIA_TALKS_INDEX,
        objectIDs: [objectID],
        userToken: userToken.current,
        positions: position !== undefined ? [position] : [1],
        queryID,
      });
    } else {
      aa('clickedObjectIDs', {
        eventName: 'Talk Clicked',
        index: ALGOLIA_TALKS_INDEX,
        objectIDs: [objectID],
        userToken: userToken.current,
      });
    }
  }, []);

  const convertCFP = useCallback((objectID: string, queryID?: string) => {
    if (queryID) {
      aa('convertedObjectIDsAfterSearch', {
        eventName: 'CFP Submission Started',
        index: ALGOLIA_INDEX_NAME,
        objectIDs: [objectID],
        userToken: userToken.current,
        queryID,
      });
    } else {
      aa('convertedObjectIDs', {
        eventName: 'CFP Submission Started',
        index: ALGOLIA_INDEX_NAME,
        objectIDs: [objectID],
        userToken: userToken.current,
      });
    }
  }, []);

  const watchTalk = useCallback((objectID: string, queryID?: string) => {
    if (queryID) {
      aa('convertedObjectIDsAfterSearch', {
        eventName: 'Talk Video Opened',
        index: ALGOLIA_TALKS_INDEX,
        objectIDs: [objectID],
        userToken: userToken.current,
        queryID,
      });
    } else {
      aa('convertedObjectIDs', {
        eventName: 'Talk Video Opened',
        index: ALGOLIA_TALKS_INDEX,
        objectIDs: [objectID],
        userToken: userToken.current,
      });
    }
  }, []);

  const clickInspire = useCallback((talkObjectID: string) => {
    aa('clickedObjectIDs', {
      eventName: 'Inspire Me Clicked',
      index: ALGOLIA_TALKS_INDEX,
      objectIDs: [talkObjectID],
      userToken: userToken.current,
    });
  }, []);

  const viewCarousel = useCallback((carouselId: string, objectIDs: string[]) => {
    if (objectIDs.length === 0) return;

    // Determine index from carousel ID
    const isTalks = carouselId.includes('talk') || carouselId.includes('viral');

    aa('viewedObjectIDs', {
      eventName: `Carousel Viewed: ${carouselId}`,
      index: isTalks ? ALGOLIA_TALKS_INDEX : ALGOLIA_INDEX_NAME,
      objectIDs: objectIDs.slice(0, 20), // Max 20 per event
      userToken: userToken.current,
    });
  }, []);

  return {
    clickCFP,
    clickTalk,
    convertCFP,
    watchTalk,
    clickInspire,
    viewCarousel,
  };
}
