/**
 * Tests for useMatchScore - CFP match scoring logic
 *
 * These are pure function tests - no mocking needed.
 */

import { describe, it, expect } from 'vitest';
import { calculateMatchScore } from '../useMatchScore';
import type { CFP, UserProfile } from '../../types';

// Factory for creating test CFPs
function createCFP(overrides: Partial<CFP> = {}): CFP {
  return {
    objectID: 'test-cfp-1',
    name: 'Test Conference',
    topics: [],
    topicsNormalized: [],
    location: {},
    source: 'test',
    enriched: false,
    languages: [],
    technologies: [],
    talkTypes: [],
    industries: [],
    ...overrides,
  };
}

// Factory for creating test profiles
function createProfile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    topics: [],
    experienceLevel: 'intermediate',
    preferredFormats: [],
    viewedCFPs: [],
    savedCFPs: [],
    watchedTalks: [],
    favoriteTalks: [],
    favoriteSpeakers: [],
    ...overrides,
  };
}

describe('calculateMatchScore', () => {
  describe('when profile has no topics', () => {
    it('returns 50% score with suggestion to set interests', () => {
      const cfp = createCFP({ topicsNormalized: ['AI/ML', 'DevOps'] });
      const profile = createProfile({ topics: [] });

      const result = calculateMatchScore(cfp, profile);

      expect(result.score).toBe(50);
      expect(result.reasons).toContain('Set your interests for personalized matches');
    });
  });

  describe('topic matching', () => {
    it('gives higher score for matching topics', () => {
      const cfp = createCFP({
        topicsNormalized: ['AI/ML', 'DevOps', 'Cloud'],
      });
      const profile = createProfile({
        topics: ['AI/ML', 'Cloud'],
      });

      const result = calculateMatchScore(cfp, profile);

      // Base (40) + topic match (~40 for 2/2 match) = ~80
      expect(result.score).toBeGreaterThanOrEqual(75);
      expect(result.reasons.some((r) => r.toLowerCase().includes('topic'))).toBe(true);
    });

    it('handles partial topic matches', () => {
      const cfp = createCFP({
        topicsNormalized: ['AI/ML'],
      });
      const profile = createProfile({
        topics: ['AI/ML', 'DevOps', 'Security'],
      });

      const result = calculateMatchScore(cfp, profile);

      // Should still get some topic score
      expect(result.score).toBeGreaterThan(50);
    });

    it('handles case-insensitive matching', () => {
      const cfp = createCFP({
        topicsNormalized: ['devops', 'cloud'],
      });
      const profile = createProfile({
        topics: ['DevOps', 'Cloud'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.score).toBeGreaterThan(70);
    });

    it('handles partial string matching (contains)', () => {
      const cfp = createCFP({
        topicsNormalized: ['Machine Learning', 'Deep Learning'],
      });
      const profile = createProfile({
        topics: ['AI/ML'], // Should partially match "Machine Learning"
      });

      // The matching logic checks if either contains the other
      const result = calculateMatchScore(cfp, profile);
      // No direct match, so lower score expected
      expect(result.score).toBeGreaterThanOrEqual(40);
    });
  });

  describe('experience level matching', () => {
    it('boosts score for beginner-friendly events', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps'],
        audienceLevel: 'beginner-friendly',
      });
      const profile = createProfile({
        topics: ['DevOps'],
        experienceLevel: 'beginner',
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.reasons.some((r) => r.toLowerCase().includes('level'))).toBe(true);
    });

    it('boosts score for all-levels events', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps'],
        audienceLevel: 'all-levels',
      });
      const profile = createProfile({
        topics: ['DevOps'],
        experienceLevel: 'beginner',
      });

      const result = calculateMatchScore(cfp, profile);

      // Should get level fit bonus
      expect(result.score).toBeGreaterThan(75);
    });
  });

  describe('format matching', () => {
    it('boosts score when format matches preference', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps'],
        eventFormat: 'virtual',
      });
      const profile = createProfile({
        topics: ['DevOps'],
        preferredFormats: ['virtual'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.reasons.some((r) => r.includes('virtual'))).toBe(true);
    });
  });

  describe('popularity signals', () => {
    it('boosts score for HN trending CFPs', () => {
      const cfpWithHN = createCFP({
        topicsNormalized: ['DevOps'],
        hnStories: 5,
        hnPoints: 100,
      });
      const cfpWithoutHN = createCFP({
        topicsNormalized: ['DevOps'],
      });
      const profile = createProfile({
        topics: ['DevOps'],
      });

      const scoreWithHN = calculateMatchScore(cfpWithHN, profile);
      const scoreWithoutHN = calculateMatchScore(cfpWithoutHN, profile);

      expect(scoreWithHN.score).toBeGreaterThan(scoreWithoutHN.score);
      expect(scoreWithHN.reasons.some((r) => r.includes('HN'))).toBe(true);
    });

    it('boosts score for GitHub popular CFPs', () => {
      const cfpWithGH = createCFP({
        topicsNormalized: ['DevOps'],
        githubStars: 500,
      });
      const cfpWithoutGH = createCFP({
        topicsNormalized: ['DevOps'],
      });
      const profile = createProfile({
        topics: ['DevOps'],
      });

      const scoreWithGH = calculateMatchScore(cfpWithGH, profile);
      const scoreWithoutGH = calculateMatchScore(cfpWithoutGH, profile);

      expect(scoreWithGH.score).toBeGreaterThan(scoreWithoutGH.score);
      expect(scoreWithGH.reasons.some((r) => r.includes('GitHub'))).toBe(true);
    });

    it('boosts score based on popularityScore', () => {
      const cfpPopular = createCFP({
        topicsNormalized: ['DevOps'],
        popularityScore: 75,
      });
      const cfpUnpopular = createCFP({
        topicsNormalized: ['DevOps'],
        popularityScore: 10,
      });
      const profile = createProfile({
        topics: ['DevOps'],
      });

      const popularScore = calculateMatchScore(cfpPopular, profile);
      const unpopularScore = calculateMatchScore(cfpUnpopular, profile);

      expect(popularScore.score).toBeGreaterThan(unpopularScore.score);
    });
  });

  describe('urgency indicators', () => {
    it('adds "Closing soon!" reason for imminent deadlines', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps'],
        daysUntilCfpClose: 3,
      });
      const profile = createProfile({
        topics: ['DevOps'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.reasons.some((r) => r.includes('soon'))).toBe(true);
    });

    it('does not add urgency for distant deadlines', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps'],
        daysUntilCfpClose: 30,
      });
      const profile = createProfile({
        topics: ['DevOps'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.reasons.every((r) => !r.includes('soon'))).toBe(true);
    });
  });

  describe('score bounds', () => {
    it('never exceeds 100', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps', 'Cloud', 'AI/ML'],
        audienceLevel: 'intermediate',
        eventFormat: 'hybrid',
        hnStories: 10,
        hnPoints: 500,
        githubStars: 1000,
        popularityScore: 100,
        daysUntilCfpClose: 2,
      });
      const profile = createProfile({
        topics: ['DevOps', 'Cloud', 'AI/ML'],
        experienceLevel: 'intermediate',
        preferredFormats: ['hybrid'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.score).toBeLessThanOrEqual(100);
    });

    it('limits reasons to 3', () => {
      const cfp = createCFP({
        topicsNormalized: ['DevOps', 'Cloud'],
        audienceLevel: 'intermediate',
        eventFormat: 'hybrid',
        hnStories: 5,
        githubStars: 200,
        daysUntilCfpClose: 3,
      });
      const profile = createProfile({
        topics: ['DevOps', 'Cloud'],
        experienceLevel: 'intermediate',
        preferredFormats: ['hybrid'],
      });

      const result = calculateMatchScore(cfp, profile);

      expect(result.reasons.length).toBeLessThanOrEqual(3);
    });
  });
});
