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
 *
 * Scoring breakdown:
 * - Base: 30 points
 * - Topic match: up to 30 points
 * - Interview profile: up to 25 points (tech stack, interests, travel)
 * - Experience level: up to 10 points
 * - Format match: up to 5 points
 * - Popularity: up to 10 points
 */
export function calculateMatchScore(cfp: CFP, profile: UserProfile): MatchResult {
  const hasBasicProfile = profile.topics.length > 0;
  const interview = profile.interview;

  if (!hasBasicProfile && !interview?.techStack?.length) {
    return { score: 50, reasons: ['Set your interests for personalized matches'] };
  }

  const reasons: string[] = [];
  let score = 30; // Base score

  const cfpTopics = cfp.topicsNormalized || cfp.topics || [];
  const cfpTech = cfp.technologies || [];
  const cfpLocation = cfp.location || {};

  // ===== Topic Match (up to +30) =====
  const userTopics = [...profile.topics, ...(interview?.interests || [])];
  if (userTopics.length > 0) {
    const matchedTopics = userTopics.filter((userTopic) =>
      cfpTopics.some((cfpTopic) =>
        cfpTopic.toLowerCase().includes(userTopic.toLowerCase()) ||
        userTopic.toLowerCase().includes(cfpTopic.toLowerCase())
      )
    );

    if (matchedTopics.length > 0) {
      const topicScore = Math.min(30, (matchedTopics.length / Math.min(userTopics.length, 5)) * 30);
      score += topicScore;
      reasons.push(`Topics: ${[...new Set(matchedTopics)].slice(0, 2).join(', ')}`);
    }
  }

  // ===== Interview Profile Match (up to +25) =====
  if (interview) {
    // Tech stack match (+15)
    if (interview.techStack && interview.techStack.length > 0) {
      const allCfpTech = [...cfpTopics, ...cfpTech].map((t) => t.toLowerCase());
      const matchedTech = interview.techStack.filter((tech) =>
        allCfpTech.some((cfpT) => cfpT.includes(tech.toLowerCase()))
      );
      if (matchedTech.length > 0) {
        score += Math.min(15, matchedTech.length * 5);
        if (!reasons.some((r) => r.startsWith('Topics:'))) {
          reasons.push(`Tech: ${matchedTech.slice(0, 2).join(', ')}`);
        }
      }
    }

    // Travel preferences (+10)
    const cfpCity = cfpLocation.city?.toLowerCase() || '';
    const cfpCountry = cfpLocation.country?.toLowerCase() || '';

    if (interview.travelWants && interview.travelWants.length > 0) {
      const wantedMatch = interview.travelWants.some(
        (place) =>
          cfpCity.includes(place.toLowerCase()) ||
          cfpCountry.includes(place.toLowerCase()) ||
          place.toLowerCase().includes(cfpCity) ||
          place.toLowerCase().includes(cfpCountry)
      );
      if (wantedMatch) {
        score += 10;
        reasons.push('Dream destination!');
      }
    }

    // Travel avoids penalty
    if (interview.travelAvoids && interview.travelAvoids.length > 0) {
      const avoidMatch = interview.travelAvoids.some(
        (place) =>
          cfpCity.includes(place.toLowerCase()) ||
          cfpCountry.includes(place.toLowerCase())
      );
      if (avoidMatch) {
        score -= 15;
        reasons.push('Travel constraint');
      }
    }

    // Speaking experience alignment
    if (interview.speakingExperience === 'none' && cfpTopics.some((t) =>
      t.toLowerCase().includes('beginner') || t.toLowerCase().includes('first')
    )) {
      score += 5;
      reasons.push('First-timer friendly');
    }
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
    if (!reasons.some((r) => r.includes('HN'))) reasons.push('Trending on HN');
  }
  if (cfp.githubStars && cfp.githubStars > 100) {
    score += 3;
    if (!reasons.some((r) => r.includes('GitHub'))) reasons.push('GitHub buzz');
  }
  if (cfp.popularityScore && cfp.popularityScore > 50) {
    score += 4;
  }

  // ===== Urgency Consideration =====
  if (cfp.daysUntilCfpClose !== undefined && cfp.daysUntilCfpClose <= 7) {
    reasons.push('Closing soon!');
  }

  return {
    score: Math.round(Math.max(0, Math.min(100, score))),
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
