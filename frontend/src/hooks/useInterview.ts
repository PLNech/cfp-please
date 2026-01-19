/**
 * useInterview - Agentic profile interview
 *
 * Real conversational AI that dynamically interviews the user
 * to build a rich profile for CFP matching.
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, AGENT_ID } from '../config';
import type { InterviewProfile } from '../types';

export interface InterviewMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export interface InterviewState {
  messages: InterviewMessage[];
  suggestions: string[];
  isLoading: boolean;
  error: string | null;
  isComplete: boolean;
  profile: InterviewProfile | null;
}

// System prompt for the interview agent
const INTERVIEW_SYSTEM_PROMPT = `You are a friendly interview agent helping a developer find the perfect CFPs (Call for Papers) for tech conferences.

Your goal is to learn about the user through natural conversation to build a profile for matching them with relevant CFPs and talks. Be conversational, warm, and encouraging.

Information to gather (naturally, don't interrogate):
- Their current role and what they do day-to-day
- Technologies and tools they work with
- Topics they're passionate about or want to speak on
- Speaking experience (none, meetups, conferences, international)
- Goals (first talk, build brand, share expertise, travel, networking)
- Travel preferences (dream destinations, places to avoid due to visa/preference)

Guidelines:
- Ask 1-2 questions at a time, not a long list
- React to their answers with genuine interest
- If they mention something interesting, follow up naturally
- Be encouraging, especially for first-time speakers
- Keep responses concise (2-3 sentences max)
- After gathering enough info (usually 4-6 exchanges), wrap up warmly

When you have enough information to build their profile, end your message with exactly this marker on its own line:
[INTERVIEW_COMPLETE]

After this marker, output the extracted profile as JSON on a single line:
{"role":"...", "techStack":["..."], "interests":["..."], "speakingExperience":"none|meetups|regional|international", "goals":["..."], "travelWants":["..."], "travelAvoids":["..."]}

Start by introducing yourself briefly and asking what brings them here.`;

export function useInterview() {
  const [state, setState] = useState<InterviewState>({
    messages: [],
    suggestions: [],
    isLoading: false,
    error: null,
    isComplete: false,
    profile: null,
  });

  const conversationIdRef = useRef<string | null>(null);

  const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

  // Generate contextual suggestions based on last assistant message
  const generateSuggestions = (assistantMessage: string): string[] => {
    const lower = assistantMessage.toLowerCase();

    // Role/job questions
    if (lower.includes('role') || lower.includes('what do you do') || lower.includes('tell me about yourself')) {
      return ['Frontend Engineer', 'Backend Developer', 'DevOps/SRE', 'Tech Lead/Manager'];
    }

    // Tech stack questions
    if (lower.includes('technolog') || lower.includes('stack') || lower.includes('tools') || lower.includes('work with')) {
      return ['React & TypeScript', 'Python & AI/ML', 'Go & Kubernetes', 'Full-stack JavaScript'];
    }

    // Speaking experience
    if (lower.includes('spoken') || lower.includes('speaking') || lower.includes('present') || lower.includes('experience')) {
      return ["Never, but I'd love to start!", 'A few meetups', 'Some regional conferences', 'International stages'];
    }

    // Interests/topics
    if (lower.includes('passionate') || lower.includes('interest') || lower.includes('topic') || lower.includes('talk about')) {
      return ['AI & Machine Learning', 'Developer Experience', 'Cloud & Infrastructure', 'Open Source'];
    }

    // Goals
    if (lower.includes('goal') || lower.includes('hope to') || lower.includes('want to') || lower.includes('achieve')) {
      return ['Land my first talk', 'Speak internationally', 'Share my expertise', 'Build my brand'];
    }

    // Travel
    if (lower.includes('travel') || lower.includes('location') || lower.includes('destination') || lower.includes('where')) {
      return ['Europe would be amazing', 'Love Asia', 'US conferences', 'Anywhere with good food!'];
    }

    // Interview complete
    if (lower.includes('profile') || lower.includes('ready') || lower.includes('find') || lower.includes('match')) {
      return ['Show me matching CFPs!', 'Find talks to inspire me'];
    }

    // Default
    return [];
  };

  // Call Agent Studio API
  // Note: System prompt should be configured in Agent Dashboard, not sent via API
  const callAgent = async (messages: Array<{ role: string; content: string }>): Promise<string> => {
    // Filter out system messages - Agent Studio doesn't accept them in API calls
    // The agent's instructions should be set in the Dashboard
    const apiMessages = messages
      .filter(m => m.role !== 'system')
      .map(m => ({ role: m.role, content: m.content }));

    // Build request body, omit conversationId if null
    const body: Record<string, unknown> = { messages: apiMessages };
    if (conversationIdRef.current) {
      body.conversationId = conversationIdRef.current;
    }

    const response = await fetch(
      `https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents/${AGENT_ID}/completions?compatibilityMode=ai-sdk-4&stream=false`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Algolia-Application-Id': ALGOLIA_APP_ID,
          'X-Algolia-API-Key': ALGOLIA_SEARCH_KEY,
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `API error: ${response.status}`);
    }

    const data = await response.json();

    if (data.conversationId) {
      conversationIdRef.current = data.conversationId;
    }

    return data.content || data.message || '';
  };

  // Parse profile from agent response
  const parseProfile = (response: string): InterviewProfile | null => {
    const jsonMatch = response.match(/\{[^{}]*"role"[^{}]*\}/);
    if (!jsonMatch) return null;

    try {
      const parsed = JSON.parse(jsonMatch[0]);
      return {
        role: parsed.role,
        techStack: parsed.techStack || [],
        interests: parsed.interests || [],
        speakingTopics: parsed.interests || [],
        speakingExperience: parsed.speakingExperience,
        goals: parsed.goals || [],
        travelWants: parsed.travelWants || [],
        travelAvoids: parsed.travelAvoids || [],
        interviewedAt: Date.now(),
        rawResponses: {}, // Agent doesn't need this
      };
    } catch {
      return null;
    }
  };

  // Clean assistant message (remove JSON and markers)
  const cleanMessage = (response: string): string => {
    return response
      .replace(/\[INTERVIEW_COMPLETE\]/g, '')
      .replace(/\{[^{}]*"role"[^{}]*\}/g, '')
      .trim();
  };

  // Start the interview
  const startInterview = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const systemMessage = { role: 'system', content: INTERVIEW_SYSTEM_PROMPT };
      const response = await callAgent([systemMessage]);

      const welcomeMsg: InterviewMessage = {
        id: generateId(),
        role: 'assistant',
        content: cleanMessage(response),
        timestamp: Date.now(),
      };

      setState({
        messages: [welcomeMsg],
        suggestions: generateSuggestions(response),
        isLoading: false,
        error: null,
        isComplete: false,
        profile: null,
      });
    } catch (err) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to start interview',
      }));
    }
  }, []);

  // Send user response
  const sendResponse = useCallback(async (response: string) => {
    const userMsg: InterviewMessage = {
      id: generateId(),
      role: 'user',
      content: response,
      timestamp: Date.now(),
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMsg],
      isLoading: true,
      suggestions: [],
    }));

    try {
      // Build message history for API
      const apiMessages = [
        { role: 'system', content: INTERVIEW_SYSTEM_PROMPT },
        ...state.messages.map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content: response },
      ];

      const agentResponse = await callAgent(apiMessages);

      // Check if interview is complete
      const isComplete = agentResponse.includes('[INTERVIEW_COMPLETE]');
      const profile = isComplete ? parseProfile(agentResponse) : null;

      const assistantMsg: InterviewMessage = {
        id: generateId(),
        role: 'assistant',
        content: cleanMessage(agentResponse),
        timestamp: Date.now(),
      };

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMsg],
        suggestions: isComplete
          ? ['Show me matching CFPs', 'Find talks to inspire me', 'Explore speakers']
          : generateSuggestions(agentResponse),
        isLoading: false,
        isComplete,
        profile,
      }));
    } catch (err) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to send message',
      }));
    }
  }, [state.messages]);

  // Reset interview
  const resetInterview = useCallback(() => {
    conversationIdRef.current = null;
    setState({
      messages: [],
      suggestions: [],
      isLoading: false,
      error: null,
      isComplete: false,
      profile: null,
    });
  }, []);

  return {
    ...state,
    startInterview,
    sendResponse,
    resetInterview,
  };
}
