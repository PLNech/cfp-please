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

// Note: System prompt / agent instructions should be configured in the Agent Studio Dashboard
// The interview agent needs the following capabilities:
// - Ask about role, tech stack, interests, speaking experience, goals, travel preferences
// - End with [INTERVIEW_COMPLETE] marker and JSON profile

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
      // Agent instructions should be configured in Dashboard
      // Send a user message to start the conversation
      const initialMessage = 'Hi! I\'m looking for help finding the right CFPs for me.';
      const response = await callAgent([
        { role: 'user', content: initialMessage }
      ]);

      const userMsg: InterviewMessage = {
        id: generateId(),
        role: 'user',
        content: initialMessage,
        timestamp: Date.now(),
      };

      const welcomeMsg: InterviewMessage = {
        id: generateId(),
        role: 'assistant',
        content: cleanMessage(response),
        timestamp: Date.now(),
      };

      setState({
        messages: [userMsg, welcomeMsg],
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
      // Build message history for API (system messages filtered by callAgent)
      const apiMessages = [
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
