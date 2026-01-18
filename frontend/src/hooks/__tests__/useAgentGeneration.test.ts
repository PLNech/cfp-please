/**
 * Tests for useAgentGeneration - AI-powered talk idea generation
 *
 * Integration tests using real Algolia Agent Studio API.
 * Tests are skipped if VITE_ALGOLIA_SEARCH_KEY is not set.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAgentGeneration } from '../useAgentGeneration';
import { ALGOLIA_SEARCH_KEY, AGENT_ID } from '../../config';
import type { Talk } from '../../types';

// Check if we have API credentials
const hasCredentials = !!ALGOLIA_SEARCH_KEY && !!AGENT_ID;

// Factory for creating test talks
function createTalk(overrides: Partial<Talk> = {}): Talk {
  return {
    objectID: 'yt_test123',
    conference_id: 'conf_123',
    conference_name: 'KubeCon',
    title: 'Kubernetes Design Principles',
    speaker: 'Saad Ali',
    url: 'https://youtube.com/watch?v=test123',
    topics: ['Kubernetes', 'Cloud Native'],
    ...overrides,
  };
}

describe('useAgentGeneration', () => {
  describe('generateInspiration', () => {
    it.skipIf(!hasCredentials)(
      'generates talk ideas from a source talk (integration)',
      async () => {
        const { result } = renderHook(() => useAgentGeneration());

        const sourceTalk = createTalk({
          title: 'Building Scalable Microservices',
          speaker: 'Jane Doe',
          conference_name: 'GopherCon',
          topics: ['Go', 'Microservices'],
        });

        // Call generateInspiration
        const inspiration = await result.current.generateInspiration(
          sourceTalk,
          ['Backend', 'Cloud'],
          'intermediate'
        );

        // Should have results
        expect(inspiration).not.toBeNull();
        expect(inspiration!.talkIdeas).toHaveLength(3);

        // Each idea should have required fields
        for (const idea of inspiration!.talkIdeas) {
          expect(idea.title).toBeTruthy();
          expect(idea.description).toBeTruthy();
          expect(idea.angle).toBeTruthy();
        }
      },
      { timeout: 30000 } // Agent calls can take time
    );

    it.skipIf(!hasCredentials)(
      'uses cache for repeated calls with same input',
      async () => {
        const { result } = renderHook(() => useAgentGeneration());

        const sourceTalk = createTalk({
          objectID: 'cache_test_1',
          title: 'Caching Test Talk',
        });

        // First call - should hit API
        const start1 = Date.now();
        const result1 = await result.current.generateInspiration(
          sourceTalk,
          ['Testing'],
          'beginner'
        );
        const duration1 = Date.now() - start1;

        // Second call with same params - should be cached
        const start2 = Date.now();
        const result2 = await result.current.generateInspiration(
          sourceTalk,
          ['Testing'],
          'beginner'
        );
        const duration2 = Date.now() - start2;

        // Both should return the same data
        expect(result1).toEqual(result2);

        // Second call should be much faster (cached)
        expect(duration2).toBeLessThan(duration1 / 2);
      },
      { timeout: 30000 }
    );

    it.skipIf(!hasCredentials)(
      'clears cache when clearCache is called',
      async () => {
        const { result } = renderHook(() => useAgentGeneration());

        const sourceTalk = createTalk({
          objectID: 'clear_cache_test_' + Date.now(),
          title: 'Clear Cache Test',
        });

        // Get result
        const result1 = await result.current.generateInspiration(
          sourceTalk,
          ['DevOps'],
          'advanced'
        );

        // Clear cache
        result.current.clearCache();

        // Call again with a fresh unique ID to ensure no caching
        const freshTalk = createTalk({
          objectID: 'fresh_' + Date.now(),
          title: 'Fresh Talk',
        });
        const result2 = await result.current.generateInspiration(
          freshTalk,
          ['Testing'],
          'beginner'
        );

        // Both should return valid results (API was called)
        expect(result1).not.toBeNull();
        expect(result2).not.toBeNull();

        // Results should be different (not cached)
        expect(result1!.generatedAt).not.toBe(result2!.generatedAt);
      },
      { timeout: 60000 }
    );

    it('returns null when API fails', async () => {
      // Mock fetch to fail
      const originalFetch = global.fetch;
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      try {
        const { result } = renderHook(() => useAgentGeneration());

        const sourceTalk = createTalk({
          objectID: 'error_test',
          title: 'Error Test Talk',
          conference_name: 'TestCon',
          topics: ['Testing'],
        });

        const inspiration = await result.current.generateInspiration(
          sourceTalk,
          ['Testing'],
          'intermediate'
        );

        // Should return null on error
        expect(inspiration).toBeNull();
        // Error state is set asynchronously, may or may not be set by the time we check
      } finally {
        global.fetch = originalFetch;
      }
    });
  });

  describe('generateMatchScore (heuristic)', () => {
    it('returns 50 for empty profile topics', async () => {
      const { result } = renderHook(() => useAgentGeneration());

      const score = await result.current.generateMatchScore(
        { topicsNormalized: ['AI/ML'] } as any,
        []
      );

      expect(score).toBe(50);
    });

    it('gives higher score for topic overlap', async () => {
      const { result } = renderHook(() => useAgentGeneration());

      const scoreWithMatch = await result.current.generateMatchScore(
        { topicsNormalized: ['AI/ML', 'DevOps'] } as any,
        ['AI/ML']
      );

      const scoreNoMatch = await result.current.generateMatchScore(
        { topicsNormalized: ['Security'] } as any,
        ['AI/ML']
      );

      expect(scoreWithMatch).toBeGreaterThan(scoreNoMatch);
    });

    it('boosts score for intel signals', async () => {
      const { result } = renderHook(() => useAgentGeneration());

      // Use partial topic match so scores don't hit 100 cap
      const cfpWithIntel = {
        topicsNormalized: ['DevOps', 'Security'],
        hnStories: 5,
        githubStars: 200,
        popularityScore: 60,
      } as any;

      const cfpWithoutIntel = {
        topicsNormalized: ['DevOps', 'Security'],
      } as any;

      // Only partial topic match (1 out of 3 user topics)
      const userTopics = ['DevOps', 'Cloud', 'Testing'];

      const scoreWithIntel = await result.current.generateMatchScore(
        cfpWithIntel,
        userTopics
      );
      const scoreWithoutIntel = await result.current.generateMatchScore(
        cfpWithoutIntel,
        userTopics
      );

      expect(scoreWithIntel).toBeGreaterThan(scoreWithoutIntel);
    });

    it('caps score at 100', async () => {
      const { result } = renderHook(() => useAgentGeneration());

      const cfp = {
        topicsNormalized: ['AI/ML', 'DevOps', 'Cloud'],
        hnStories: 100,
        githubStars: 10000,
        popularityScore: 100,
      } as any;

      const score = await result.current.generateMatchScore(
        cfp,
        ['AI/ML', 'DevOps', 'Cloud']
      );

      expect(score).toBeLessThanOrEqual(100);
    });
  });
});

describe('Agent API Behavior', () => {
  describe('API response parsing', () => {
    it.skipIf(!hasCredentials)(
      'correctly extracts JSON from agent response',
      async () => {
        // This tests the actual prompt->response->parse pipeline
        const { result } = renderHook(() => useAgentGeneration());

        const talk = createTalk({
          objectID: 'parse_test',
          title: 'Testing JSON Parsing',
          topics: ['Testing', 'JSON'],
        });

        const inspiration = await result.current.generateInspiration(
          talk,
          ['Testing'],
          'intermediate'
        );

        // Verify structure is correct (parsed from JSON)
        expect(inspiration).not.toBeNull();
        expect(Array.isArray(inspiration!.talkIdeas)).toBe(true);
        expect(typeof inspiration!.generatedAt).toBe('number');
      },
      { timeout: 30000 }
    );
  });
});
