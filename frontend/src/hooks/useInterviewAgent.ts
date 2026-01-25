/**
 * useInterviewAgent - Profile Interview agent with client-side tool handling
 *
 * Multi-turn conversation that collects user preferences, validates via
 * client-side tool, and saves to localStorage on success.
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, INTERVIEW_AGENT_ID } from '../config';
import { generateMessageId, generateConversationId } from '../utils/anonymousId';
import type { InterviewProfile } from '../types';

interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface ToolCall {
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

interface ValidationResult {
  success: boolean;
  errors?: string[];
  profile?: InterviewProfile;
}

/**
 * Validate the profile data from the agent
 */
function validateProfile(args: SaveProfileArgs): ValidationResult {
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

  // Validate arrays aren't too long
  if (args.techStack && args.techStack.length > 20) {
    errors.push('Too many tech stack items (max 20)');
  }
  if (args.interests && args.interests.length > 10) {
    errors.push('Too many interests (max 10)');
  }
  if (args.speakingTopics && args.speakingTopics.length > 10) {
    errors.push('Too many speaking topics (max 10)');
  }

  // Validate experience level enum
  const validExperience = ['none', 'meetups', 'regional', 'international'];
  if (args.speakingExperience && !validExperience.includes(args.speakingExperience)) {
    errors.push(`Invalid speaking experience: must be one of ${validExperience.join(', ')}`);
  }

  // Validate formats enum
  const validFormats = ['in-person', 'virtual', 'hybrid'];
  if (args.preferredFormats) {
    for (const format of args.preferredFormats) {
      if (!validFormats.includes(format)) {
        errors.push(`Invalid format: ${format}. Must be one of ${validFormats.join(', ')}`);
      }
    }
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

interface InterviewAgentResult {
  message: string;
  toolCalled: boolean;
  validationResult?: ValidationResult;
}

export function useInterviewAgent() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingProfile, setPendingProfile] = useState<InterviewProfile | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  const messagesRef = useRef<AgentMessage[]>([]);

  const sendMessage = useCallback(
    async (
      userMessage: string,
      onProfileValidated?: (profile: InterviewProfile) => void
    ): Promise<InterviewAgentResult | null> => {
      setIsLoading(true);
      setError(null);

      // Initialize conversation ID if starting new conversation
      if (!conversationIdRef.current) {
        conversationIdRef.current = generateConversationId();
      }

      // Add user message with unique ID
      const userMsgId = generateMessageId();
      messagesRef.current = [
        ...messagesRef.current,
        { id: userMsgId, role: 'user', content: userMessage },
      ];

      try {
        // Build messages in AI SDK 5 format
        const apiMessages = messagesRef.current.map((m) => ({
          id: m.id,
          role: m.role,
          parts: [{ type: 'text', text: m.content }],
        }));

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
              messages: apiMessages,
            }),
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || `API error: ${response.status}`);
        }

        const data = await response.json();

        // Extract assistant message
        let assistantMessage = '';
        if (data.content) {
          assistantMessage = data.content;
        } else if (data.parts) {
          assistantMessage = data.parts
            .filter((p: { type: string }) => p.type === 'text')
            .map((p: { text: string }) => p.text)
            .join('');
        } else if (data.message) {
          assistantMessage = data.message;
        }

        // Check for client-side tool calls
        let toolCalled = false;
        let validationResult: ValidationResult | undefined;

        if (data.tool_invocations) {
          for (const invocation of data.tool_invocations as ToolCall[]) {
            if (invocation.tool_name === 'save_profile' && invocation.state === 'call') {
              toolCalled = true;
              const args = invocation.args as unknown as SaveProfileArgs;

              // Validate the profile
              validationResult = validateProfile(args);

              if (validationResult.success && validationResult.profile) {
                // Profile is valid - save it
                setPendingProfile(validationResult.profile);
                if (onProfileValidated) {
                  onProfileValidated(validationResult.profile);
                }

                // Send tool result back to agent
                const toolResultResponse = await fetch(
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
                      messages: [
                        ...apiMessages,
                        {
                          id: generateMessageId(),
                          role: 'assistant',
                          parts: [{ type: 'text', text: assistantMessage }],
                          tool_invocations: data.tool_invocations,
                        },
                        {
                          id: generateMessageId(),
                          role: 'tool',
                          tool_call_id: invocation.tool_call_id,
                          content: JSON.stringify({
                            success: true,
                            message: 'Profile saved successfully! Your preferences have been stored.',
                          }),
                        },
                      ],
                    }),
                  }
                );

                if (toolResultResponse.ok) {
                  const followUp = await toolResultResponse.json();
                  // Update assistant message with follow-up
                  if (followUp.content) {
                    assistantMessage = followUp.content;
                  } else if (followUp.parts) {
                    assistantMessage = followUp.parts
                      .filter((p: { type: string }) => p.type === 'text')
                      .map((p: { text: string }) => p.text)
                      .join('');
                  }
                }
              } else {
                // Validation failed - send errors back to agent for retry
                const toolResultResponse = await fetch(
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
                      messages: [
                        ...apiMessages,
                        {
                          id: generateMessageId(),
                          role: 'assistant',
                          parts: [{ type: 'text', text: assistantMessage }],
                          tool_invocations: data.tool_invocations,
                        },
                        {
                          id: generateMessageId(),
                          role: 'tool',
                          tool_call_id: invocation.tool_call_id,
                          content: JSON.stringify({
                            success: false,
                            errors: validationResult.errors,
                            message: `Validation failed. Please ask the user for: ${validationResult.errors?.join(', ')}`,
                          }),
                        },
                      ],
                    }),
                  }
                );

                if (toolResultResponse.ok) {
                  const followUp = await toolResultResponse.json();
                  // Update assistant message with retry prompt
                  if (followUp.content) {
                    assistantMessage = followUp.content;
                  } else if (followUp.parts) {
                    assistantMessage = followUp.parts
                      .filter((p: { type: string }) => p.type === 'text')
                      .map((p: { text: string }) => p.text)
                      .join('');
                  }
                }
              }
            }
          }
        }

        // Add assistant message to history
        const assistantMsgId = generateMessageId();
        messagesRef.current = [
          ...messagesRef.current,
          { id: assistantMsgId, role: 'assistant', content: assistantMessage },
        ];

        return {
          message: assistantMessage,
          toolCalled,
          validationResult,
        };
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        setError(errorMessage);
        console.error('Interview Agent error:', err);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const resetConversation = useCallback(() => {
    conversationIdRef.current = null;
    messagesRef.current = [];
    setPendingProfile(null);
  }, []);

  const getMessages = useCallback(() => {
    return [...messagesRef.current];
  }, []);

  return {
    sendMessage,
    resetConversation,
    getMessages,
    isLoading,
    error,
    pendingProfile,
  };
}
