/**
 * Agent Studio hook for conversational CFP search
 */

import { useState, useCallback, useRef } from 'react';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, AGENT_ID } from '../config';

interface AgentMessage {
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

    // Add user message to history
    messagesRef.current = [
      ...messagesRef.current,
      { role: 'user', content: userMessage }
    ];

    try {
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
            messages: messagesRef.current,
            conversationId: conversationIdRef.current,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `API error: ${response.status}`);
      }

      const data = await response.json();

      // Store conversation ID for continuity
      if (data.conversationId) {
        conversationIdRef.current = data.conversationId;
      }

      // AI SDK v4 format: content is the message text
      const assistantMessage = data.content || data.message || '';
      messagesRef.current = [
        ...messagesRef.current,
        { role: 'assistant', content: assistantMessage }
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
