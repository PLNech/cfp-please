/**
 * useInterview - Agentic profile interview with client-side tool handling
 *
 * Real conversational AI that dynamically interviews the user
 * to build a rich profile for CFP matching. Uses the Profile Interview agent
 * with save_profile client-side tool.
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, INTERVIEW_AGENT_ID } from '../config';
import { generateMessageId, generateConversationId } from '../utils/anonymousId';
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

interface ToolInvocation {
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  state: 'call' | 'result';
}

interface SaveProfileArgs {
  role: string;
  company?: string | null;
  techStack?: string[];
  sideProjects?: string[];
  interests: string[];
  speakingTopics?: string[];
  speakingExperience?: 'none' | 'meetups' | 'regional' | 'international';
  goals?: string[];
  homeCity: string;
  homeCountry: string;
  maxTravelHours?: number | null;
  travelWants?: string[];
  travelAvoids?: string[];
  preferRemote?: boolean;
  requireTravelCovered?: boolean;
  requireHotelCovered?: boolean;
  requireHonorarium?: boolean;
  preferredFormats?: ('in-person' | 'virtual' | 'hybrid')[];
}

/**
 * Validate the profile data from the agent
 */
function validateProfile(args: SaveProfileArgs): { success: boolean; errors?: string[]; profile?: InterviewProfile } {
  const errors: string[] = [];

  // Required fields
  if (!args.role || args.role.trim().length < 2) {
    errors.push('Role is required (at least 2 characters)');
  }
  if (!args.interests || args.interests.length === 0) {
    errors.push('At least one interest topic is required');
  }
  if (!args.homeCity || args.homeCity.trim().length < 2) {
    errors.push('Home city is required');
  }
  if (!args.homeCountry || args.homeCountry.trim().length < 2) {
    errors.push('Home country is required');
  }

  // Validate experience level enum
  const validExperience = ['none', 'meetups', 'regional', 'international'];
  if (args.speakingExperience && !validExperience.includes(args.speakingExperience)) {
    errors.push(`Invalid speaking experience: must be one of ${validExperience.join(', ')}`);
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  // Build the validated profile
  const profile: InterviewProfile = {
    role: args.role.trim(),
    company: args.company?.trim() || undefined,
    techStack: args.techStack?.filter(Boolean) || [],
    sideProjects: args.sideProjects?.filter(Boolean) || [],
    interests: args.interests.filter(Boolean),
    speakingTopics: args.speakingTopics?.filter(Boolean) || [],
    speakingExperience: args.speakingExperience,
    goals: args.goals?.filter(Boolean) || [],
    homeCity: args.homeCity.trim(),
    homeCountry: args.homeCountry.trim(),
    maxTravelHours: args.maxTravelHours ?? null,
    travelWants: args.travelWants?.filter(Boolean) || [],
    travelAvoids: args.travelAvoids?.filter(Boolean) || [],
    preferRemote: args.preferRemote ?? false,
    requireTravelCovered: args.requireTravelCovered ?? false,
    requireHotelCovered: args.requireHotelCovered ?? false,
    requireHonorarium: args.requireHonorarium ?? false,
    preferredFormats: args.preferredFormats || [],
    interviewedAt: Date.now(),
  };

  return { success: true, profile };
}

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
  const messagesHistoryRef = useRef<Array<{ id: string; role: string; parts: Array<{ type: string; text: string }>; tool_invocations?: ToolInvocation[] }>>([]);

  // Generate contextual suggestions based on last assistant message
  const generateSuggestions = (assistantMessage: string): string[] => {
    const lower = assistantMessage.toLowerCase();

    // Role/job questions
    if (lower.includes('role') || lower.includes('what do you do') || lower.includes('tell me about')) {
      return ['Staff MLE at a startup', 'Frontend Engineer', 'DevRel/Advocate', 'Engineering Manager'];
    }

    // Tech stack questions
    if (lower.includes('technolog') || lower.includes('stack') || lower.includes('tools') || lower.includes('work with')) {
      return ['Python & AI/ML', 'React & TypeScript', 'Go & Kubernetes', 'Rust & Systems'];
    }

    // Speaking experience
    if (lower.includes('spoken') || lower.includes('speaking') || lower.includes('present') || lower.includes('experience')) {
      return ["Never, but I'd love to start!", 'A few meetups', 'Regional conferences', 'International stages'];
    }

    // Interests/topics
    if (lower.includes('passionate') || lower.includes('interest') || lower.includes('topic') || lower.includes('talk about') || lower.includes('excite')) {
      return ['AI & Agents', 'Developer Experience', 'Open Source', 'Performance'];
    }

    // Location
    if (lower.includes('based') || lower.includes('live') || lower.includes('location') || lower.includes('city') || lower.includes('country')) {
      return ['Paris, France', 'San Francisco, USA', 'Berlin, Germany', 'London, UK'];
    }

    // Travel
    if (lower.includes('travel') || lower.includes('destination') || lower.includes('bucket list') || lower.includes('visit')) {
      return ['Japan!', 'US conferences', 'Northern Europe', 'Anywhere with good coffee'];
    }

    // Goals
    if (lower.includes('goal') || lower.includes('hope to') || lower.includes('want to') || lower.includes('achieve')) {
      return ['Land my first talk', 'Speak internationally', 'Share expertise', 'Build personal brand'];
    }

    // Benefits / deal-breakers
    if (lower.includes('travel covered') || lower.includes('hotel') || lower.includes('honorarium') || lower.includes('expense') || lower.includes('deal-breaker')) {
      return ['Yes, travel must be covered', 'Hotel is a must', 'Flexible on expenses', 'Paid speaking preferred'];
    }

    // Interview complete
    if (lower.includes('profile') || lower.includes('saved') || lower.includes('ready') || lower.includes('all set')) {
      return ['Show me matching CFPs!', 'Find talks to inspire me'];
    }

    // Default
    return [];
  };

  // Call Agent Studio API
  const callAgent = async (
    newUserMessage: string
  ): Promise<{ message: string; toolCalls?: ToolInvocation[]; rawData?: Record<string, unknown> }> => {
    // Initialize conversation ID if starting new conversation
    if (!conversationIdRef.current) {
      conversationIdRef.current = generateConversationId();
    }

    // Add user message to history
    const userMsgForApi = {
      id: generateMessageId(),
      role: 'user',
      parts: [{ type: 'text', text: newUserMessage }],
    };
    messagesHistoryRef.current = [...messagesHistoryRef.current, userMsgForApi];

    const response = await fetch(
      `https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents/${INTERVIEW_AGENT_ID}/completions?compatibilityMode=ai-sdk-5&stream=false`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Algolia-Application-Id': ALGOLIA_APP_ID,
          'X-Algolia-API-Key': ALGOLIA_SEARCH_KEY,
        },
        body: JSON.stringify({
          id: conversationIdRef.current,
          messages: messagesHistoryRef.current,
        }),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `API error: ${response.status}`);
    }

    const data = await response.json();

    // Extract text from AI SDK v5 format
    let message = '';
    if (data.content) {
      message = data.content;
    } else if (data.parts) {
      message = data.parts
        .filter((p: { type: string }) => p.type === 'text')
        .map((p: { text: string }) => p.text)
        .join('');
    } else if (data.message) {
      message = data.message;
    }

    return {
      message,
      toolCalls: data.tool_invocations as ToolInvocation[] | undefined,
      rawData: data,
    };
  };

  // Send tool result back to agent
  const sendToolResult = async (
    toolCallId: string,
    result: { success: boolean; message: string; errors?: string[] },
    previousAssistantMessage: string,
    toolInvocations: ToolInvocation[]
  ): Promise<string> => {
    // Add assistant message with tool invocations to history
    const assistantMsgForApi = {
      id: generateMessageId(),
      role: 'assistant',
      parts: [{ type: 'text', text: previousAssistantMessage }],
      tool_invocations: toolInvocations,
    };
    messagesHistoryRef.current = [...messagesHistoryRef.current, assistantMsgForApi];

    // Add tool result
    const toolResultForApi = {
      id: generateMessageId(),
      role: 'tool',
      tool_call_id: toolCallId,
      parts: [{ type: 'text', text: JSON.stringify(result) }],
    };
    messagesHistoryRef.current = [...messagesHistoryRef.current, toolResultForApi];

    const response = await fetch(
      `https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents/${INTERVIEW_AGENT_ID}/completions?compatibilityMode=ai-sdk-5&stream=false`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Algolia-Application-Id': ALGOLIA_APP_ID,
          'X-Algolia-API-Key': ALGOLIA_SEARCH_KEY,
        },
        body: JSON.stringify({
          id: conversationIdRef.current,
          messages: messagesHistoryRef.current,
        }),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `API error: ${response.status}`);
    }

    const data = await response.json();

    // Extract follow-up message
    if (data.content) return data.content;
    if (data.parts) {
      return data.parts
        .filter((p: { type: string }) => p.type === 'text')
        .map((p: { text: string }) => p.text)
        .join('');
    }
    return data.message || '';
  };

  // Start the interview
  const startInterview = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    messagesHistoryRef.current = [];
    conversationIdRef.current = null;

    try {
      const initialMessage = "Hi! I'm looking for help finding the right CFPs for me.";
      const { message } = await callAgent(initialMessage);

      const userMsg: InterviewMessage = {
        id: generateMessageId(),
        role: 'user',
        content: initialMessage,
        timestamp: Date.now(),
      };

      const welcomeMsg: InterviewMessage = {
        id: generateMessageId(),
        role: 'assistant',
        content: message,
        timestamp: Date.now(),
      };

      // Add assistant message to history
      messagesHistoryRef.current = [
        ...messagesHistoryRef.current,
        { id: welcomeMsg.id, role: 'assistant', parts: [{ type: 'text', text: message }] },
      ];

      setState({
        messages: [userMsg, welcomeMsg],
        suggestions: generateSuggestions(message),
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
      id: generateMessageId(),
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
      const { message, toolCalls } = await callAgent(response);

      let finalMessage = message;
      let isComplete = false;
      let profile: InterviewProfile | null = null;

      // Handle save_profile tool call
      if (toolCalls) {
        for (const toolCall of toolCalls) {
          if (toolCall.tool_name === 'save_profile' && toolCall.state === 'call') {
            const args = toolCall.args as unknown as SaveProfileArgs;
            const validation = validateProfile(args);

            if (validation.success && validation.profile) {
              // Success! Send confirmation to agent
              const followUp = await sendToolResult(
                toolCall.tool_call_id,
                { success: true, message: 'Profile saved successfully!' },
                message,
                toolCalls
              );
              finalMessage = followUp;
              isComplete = true;
              profile = validation.profile;
            } else {
              // Validation failed - send errors for retry
              const followUp = await sendToolResult(
                toolCall.tool_call_id,
                {
                  success: false,
                  message: 'Validation failed',
                  errors: validation.errors,
                },
                message,
                toolCalls
              );
              finalMessage = followUp;
            }
          }
        }
      }

      // Add assistant response to history
      messagesHistoryRef.current = [
        ...messagesHistoryRef.current,
        { id: generateMessageId(), role: 'assistant', parts: [{ type: 'text', text: finalMessage }] },
      ];

      const assistantMsg: InterviewMessage = {
        id: generateMessageId(),
        role: 'assistant',
        content: finalMessage,
        timestamp: Date.now(),
      };

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMsg],
        suggestions: isComplete
          ? ['Show me matching CFPs', 'Find talks to inspire me', 'Explore speakers']
          : generateSuggestions(finalMessage),
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
  }, []);

  // Reset interview
  const resetInterview = useCallback(() => {
    conversationIdRef.current = null;
    messagesHistoryRef.current = [];
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
