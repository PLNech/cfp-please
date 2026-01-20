/**
 * Agent Generation hook for structured AI outputs
 *
 * Used for generating talk ideas, match scores, and other structured content.
 * Extends useAgentStudio with caching and structured prompts.
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, AGENT_ID } from '../config';
import type { Talk, CFP, InterviewProfile } from '../types';

// ===== Types =====

export interface TalkIdea {
  title: string;
  description: string;
  angle: string; // What makes this unique
}

export interface MatchingCFP {
  cfp: CFP;
  matchScore: number; // 0-100
  whySubmit: string;
}

export interface InspirationResult {
  talkIdeas: TalkIdea[];
  matchingCFPs: MatchingCFP[];
  generatedAt: number;
}

interface CacheEntry<T> {
  data: T;
  expiresAt: number;
}

// ===== Constants =====

const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

// ===== Hook =====

export function useAgentGeneration() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Simple in-memory cache
  const cacheRef = useRef<Map<string, CacheEntry<InspirationResult>>>(new Map());

  /**
   * Generate talk ideas inspired by a source talk
   */
  const generateInspiration = useCallback(async (
    sourceTalk: Talk,
    userTopics: string[] = [],
    experienceLevel: string = 'intermediate',
    interview?: InterviewProfile
  ): Promise<InspirationResult | null> => {
    // Check cache first (include interview hash for cache key)
    const interviewHash = interview ? JSON.stringify(interview).slice(0, 50) : '';
    const cacheKey = `inspire_${sourceTalk.objectID}_${userTopics.join(',')}_${experienceLevel}_${interviewHash}`;
    const cached = cacheRef.current.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.data;
    }

    setIsGenerating(true);
    setError(null);

    try {
      // Build the prompt for structured generation
      const prompt = buildInspirationPrompt(sourceTalk, userTopics, experienceLevel, interview);

      const response = await fetch(
        `https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents/${AGENT_ID}/completions?compatibilityMode=ai-sdk-4&stream=false`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Algolia-Application-Id': ALGOLIA_APP_ID,
            'X-Algolia-API-Key': ALGOLIA_SEARCH_KEY,
          },
          body: JSON.stringify({
            messages: [{ role: 'user', content: prompt }],
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      const content = data.content || data.message || '';

      // Parse the structured response
      const result = parseInspirationResponse(content, sourceTalk);

      // Cache the result
      cacheRef.current.set(cacheKey, {
        data: result,
        expiresAt: Date.now() + CACHE_TTL_MS,
      });

      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Generation failed';
      setError(errorMessage);
      console.error('Agent generation error:', err);
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, []);

  /**
   * Generate match score for a CFP based on user profile
   */
  const generateMatchScore = useCallback(async (
    cfp: CFP,
    userTopics: string[]
  ): Promise<number> => {
    // Quick heuristic match (no API call needed)
    if (!userTopics.length) return 50;

    const cfpTopics = cfp.topicsNormalized || cfp.topics || [];
    const overlap = userTopics.filter(t =>
      cfpTopics.some(ct => ct.toLowerCase().includes(t.toLowerCase()))
    );

    // Base score from topic overlap
    let score = Math.min(100, 40 + (overlap.length / userTopics.length) * 60);

    // Boost for intel signals
    if (cfp.hnStories && cfp.hnStories > 0) score += 5;
    if (cfp.githubStars && cfp.githubStars > 100) score += 5;
    if (cfp.popularityScore && cfp.popularityScore > 50) score += 5;

    return Math.round(Math.min(100, score));
  }, []);

  const clearCache = useCallback(() => {
    cacheRef.current.clear();
  }, []);

  return {
    generateInspiration,
    generateMatchScore,
    clearCache,
    isGenerating,
    error,
  };
}

// ===== Helper Functions =====

function buildInspirationPrompt(
  sourceTalk: Talk,
  userTopics: string[],
  experienceLevel: string,
  interview?: InterviewProfile
): string {
  const topicsStr = userTopics.length > 0
    ? userTopics.join(', ')
    : 'general software development';

  // Build rich profile section from interview data
  let profileSection = `USER PROFILE:
- Interests: ${topicsStr}
- Experience Level: ${experienceLevel}`;

  if (interview) {
    if (interview.role) {
      profileSection += `\n- Role: ${interview.role}`;
    }
    if (interview.techStack?.length) {
      profileSection += `\n- Tech Stack: ${interview.techStack.join(', ')}`;
    }
    if (interview.interests?.length) {
      profileSection += `\n- Deep Interests: ${interview.interests.join(', ')}`;
    }
    if (interview.speakingExperience) {
      profileSection += `\n- Speaking Experience: ${interview.speakingExperience}`;
    }
    if (interview.goals?.length) {
      profileSection += `\n- Goals: ${interview.goals.join(', ')}`;
    }
    if (interview.speakingTopics?.length) {
      profileSection += `\n- Topics They Want to Speak About: ${interview.speakingTopics.join(', ')}`;
    }
    // Include any raw freeform context that might contain unique insights
    if (interview.rawResponses) {
      const freeform = Object.values(interview.rawResponses).join(' ').slice(0, 500);
      if (freeform.length > 50) {
        profileSection += `\n- Background Context: ${freeform}`;
      }
    }
  }

  return `You are a conference talk idea generator. Based on the following talk, generate 3 unique talk ideas that the user could submit to conferences.

SOURCE TALK:
- Title: "${sourceTalk.title}"
- Speaker: ${sourceTalk.speaker || 'Unknown'}
- Conference: ${sourceTalk.conference_name || 'Unknown'}
- Topics: ${(sourceTalk.topics || []).join(', ') || 'Not specified'}

${profileSection}

Generate 3 talk ideas that:
1. Are inspired by the source talk but offer a fresh perspective
2. Leverage the user's unique background and experience${interview?.role ? ` as a ${interview.role}` : ''}
3. Match their stated interests and goals
4. Would be relevant for tech conferences in 2026

For each idea, provide:
- A compelling title (max 10 words)
- A 1-2 sentence description
- What makes this angle unique (considering the user's specific background)

Format your response as JSON:
{
  "talkIdeas": [
    {
      "title": "...",
      "description": "...",
      "angle": "..."
    }
  ]
}

Only respond with valid JSON, no other text.`;
}

function parseInspirationResponse(content: string, sourceTalk: Talk): InspirationResult {
  // Try to parse JSON from response
  try {
    // Find JSON in the response (it might have surrounding text)
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      return {
        talkIdeas: parsed.talkIdeas || [],
        matchingCFPs: [], // Will be populated separately
        generatedAt: Date.now(),
      };
    }
  } catch (e) {
    console.warn('Failed to parse JSON response, using fallback');
  }

  // Fallback: generate default ideas based on source talk
  return {
    talkIdeas: [
      {
        title: `${sourceTalk.conference_name || 'Conference'} Lessons Learned`,
        description: `Share key insights and practical takeaways from ${sourceTalk.title}`,
        angle: 'Personal experience and real-world application',
      },
      {
        title: `Beyond ${(sourceTalk.topics?.[0]) || 'the Basics'}: Advanced Patterns`,
        description: 'Deep dive into advanced techniques building on foundational concepts',
        angle: 'Expert-level insights for practitioners',
      },
      {
        title: `The Future of ${(sourceTalk.topics?.[0]) || 'Tech'}`,
        description: 'Explore emerging trends and where the field is heading',
        angle: 'Forward-looking perspective with predictions',
      },
    ],
    matchingCFPs: [],
    generatedAt: Date.now(),
  };
}
