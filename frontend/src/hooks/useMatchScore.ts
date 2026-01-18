/**
 * useMatchScore - Calculate CFP match scores based on user profile
 *
 * Efficient batch scoring for carousels. Uses heuristics for instant results,
 * with optional AI enhancement for detailed explanations.
 */

import { useMemo } from 'react';
import type { CFP, UserProfile } from '../types';

export interface MatchResult {
  score: number; // 0-100
  reasons: string[];
}

/**
 * Calculate match score for a single CFP
 */
export function calculateMatchScore(cfp: CFP, profile: UserProfile): MatchResult {
  if (!profile.topics.length) {
    return { score: 50, reasons: ['Set your interests for personalized matches'] };
  }

  const reasons: string[] = [];
  let score = 40; // Base score

  // ===== Topic Match (up to +40) =====
  const cfpTopics = cfp.topicsNormalized || cfp.topics || [];
  const matchedTopics = profile.topics.filter((userTopic) =>
    cfpTopics.some((cfpTopic) =>
      cfpTopic.toLowerCase().includes(userTopic.toLowerCase()) ||
      userTopic.toLowerCase().includes(cfpTopic.toLowerCase())
    )
  );

  if (matchedTopics.length > 0) {
    const topicScore = Math.min(40, (matchedTopics.length / profile.topics.length) * 40);
    score += topicScore;
    reasons.push(`Topics: ${matchedTopics.slice(0, 2).join(', ')}`);
  }

  // ===== Experience Level Match (up to +10) =====
  const audienceLevel = cfp.audienceLevel?.toLowerCase();
  if (audienceLevel) {
    if (
      (profile.experienceLevel === 'beginner' && (audienceLevel.includes('beginner') || audienceLevel.includes('all'))) ||
      (profile.experienceLevel === 'intermediate' && !audienceLevel.includes('expert')) ||
      (profile.experienceLevel === 'advanced' && (audienceLevel.includes('advanced') || audienceLevel.includes('expert')))
    ) {
      score += 10;
      reasons.push('Level fit');
    }
  } else {
    score += 5; // Neutral if not specified
  }

  // ===== Format Match (up to +5) =====
  if (profile.preferredFormats.length > 0 && cfp.eventFormat) {
    if (profile.preferredFormats.includes(cfp.eventFormat as 'in-person' | 'virtual' | 'hybrid')) {
      score += 5;
      reasons.push(`${cfp.eventFormat} event`);
    }
  }

  // ===== Popularity Boost (up to +10) =====
  if (cfp.hnStories && cfp.hnStories > 0) {
    score += 3;
    reasons.push('Trending on HN');
  }
  if (cfp.githubStars && cfp.githubStars > 100) {
    score += 3;
    reasons.push('GitHub buzz');
  }
  if (cfp.popularityScore && cfp.popularityScore > 50) {
    score += 4;
  }

  // ===== Urgency Consideration =====
  if (cfp.daysUntilCfpClose !== undefined) {
    if (cfp.daysUntilCfpClose <= 7) {
      reasons.push('Closing soon!');
    }
  }

  return {
    score: Math.round(Math.min(100, score)),
    reasons: reasons.slice(0, 3), // Limit to 3 reasons
  };
}

/**
 * Hook to calculate match scores for multiple CFPs
 */
export function useMatchScores(cfps: CFP[], profile: UserProfile): Map<string, MatchResult> {
  return useMemo(() => {
    const scores = new Map<string, MatchResult>();

    if (!profile.topics.length) {
      return scores;
    }

    for (const cfp of cfps) {
      scores.set(cfp.objectID, calculateMatchScore(cfp, profile));
    }

    return scores;
  }, [cfps, profile]);
}

/**
 * Hook for a single CFP match score
 */
export function useMatchScore(cfp: CFP | null, profile: UserProfile): MatchResult | null {
  return useMemo(() => {
    if (!cfp) return null;
    return calculateMatchScore(cfp, profile);
  }, [cfp, profile]);
}
