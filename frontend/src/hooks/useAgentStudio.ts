/**
 * Agent Studio hook for conversational CFP search
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, AGENT_ID } from '../config';
import { getAnonymousUserId, generateMessageId, generateConversationId } from '../utils/anonymousId';

interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface ToolInvocation {
  tool_call_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  result?: {
    hits?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  state: 'call' | 'result';
}

interface CFPSource {
  objectID?: string;
  name: string;
  description?: string;
  topicsNormalized?: string[];
  location?: {
    city?: string;
    country?: string;
    region?: string;
  };
  cfpEndDateISO?: string;
  daysUntilCfpClose?: number;
  cfpUrl?: string;
  url?: string;
}

interface AgentResponse {
  message: string;
  sources: CFPSource[];
  conversationId?: string;
  clientToolCalls: Array<{
    toolName: string;
    args: Record<string, unknown>;
  }>;
}

export function useAgentStudio() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightedCfps, setHighlightedCfps] = useState<Set<string>>(new Set());
  const [selectedCfpId, setSelectedCfpId] = useState<string | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  const messagesRef = useRef<AgentMessage[]>([]);

  const sendMessage = useCallback(async (userMessage: string): Promise<AgentResponse | null> => {
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
      { id: userMsgId, role: 'user', content: userMessage }
    ];

    try {
      // Build messages in AI SDK 5 format with IDs
      const apiMessages = messagesRef.current.map(m => ({
        id: m.id,
        role: m.role,
        parts: [{ type: 'text', text: m.content }],
      }));

      const response = await fetch(
        `https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1/agents/${AGENT_ID}/completions?compatibilityMode=ai-sdk-5&stream=false`,
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

      // AI SDK v5 format: extract text from parts
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

      // Add assistant message with unique ID
      const assistantMsgId = generateMessageId();
      messagesRef.current = [
        ...messagesRef.current,
        { id: assistantMsgId, role: 'assistant', content: assistantMessage }
      ];

      // Extract sources from tool_invocations
      let sources: CFPSource[] = [];
      const clientToolCalls: AgentResponse['clientToolCalls'] = [];

      if (data.tool_invocations) {
        for (const invocation of data.tool_invocations as ToolInvocation[]) {
          // Algolia search results
          if (invocation.tool_name === 'cfp_search' && invocation.result?.hits) {
            sources = invocation.result.hits as unknown as CFPSource[];
          }

          // Client-side tool calls - handle locally
          if (invocation.tool_name === 'highlight_cfps') {
            const objectIDs = invocation.args.objectIDs as string[] | undefined;
            if (objectIDs) {
              setHighlightedCfps(new Set(objectIDs));
              clientToolCalls.push({
                toolName: 'highlight_cfps',
                args: invocation.args,
              });
            }
          }

          if (invocation.tool_name === 'show_cfp_details') {
            const objectID = invocation.args.objectID as string | undefined;
            if (objectID) {
              setSelectedCfpId(objectID);
              clientToolCalls.push({
                toolName: 'show_cfp_details',
                args: invocation.args,
              });
            }
          }
        }
      }

      return {
        message: assistantMessage,
        sources,
        conversationId: data.id,
        clientToolCalls,
      };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Agent Studio error:', err);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const resetConversation = useCallback(() => {
    conversationIdRef.current = null;
    messagesRef.current = [];
    setHighlightedCfps(new Set());
    setSelectedCfpId(null);
  }, []);

  const clearHighlights = useCallback(() => {
    setHighlightedCfps(new Set());
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedCfpId(null);
  }, []);

  return {
    sendMessage,
    resetConversation,
    clearHighlights,
    clearSelection,
    isLoading,
    error,
    highlightedCfps,
    selectedCfpId,
  };
}
