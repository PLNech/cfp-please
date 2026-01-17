import { useState, useRef, useEffect } from 'react';
import type { KeyboardEvent } from 'react';
import { useSearchBox, useHits } from 'react-instantsearch';
import type { CFP } from '../types';
import { CFPCard } from './CFPCard';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  hits?: CFP[];
  timestamp: Date;
}

interface ChatProps {
  onCfpSelect?: (cfp: CFP) => void;
}

export function Chat({ onCfpSelect }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi! I can help you find conference CFPs. Try asking me things like:\n\n• \"Show me AI conferences in Europe\"\n• \"What's closing soon in the US?\"\n• \"Find frontend conferences with workshops\"",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { refine: setQuery, query } = useSearchBox();
  const { items: hits } = useHits<CFP>();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // When search results change after a query, show them as assistant message
  useEffect(() => {
    if (query && hits.length > 0 && isLoading) {
      const resultCount = hits.length;
      let responseContent = `Found ${resultCount} conference${resultCount === 1 ? '' : 's'}`;

      // Add summary of results
      const closingSoon = hits.filter((h) => (h.daysUntilCfpClose ?? 999) <= 14);
      if (closingSoon.length > 0) {
        responseContent += `. ${closingSoon.length} closing soon!`;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: responseContent,
          hits: hits.slice(0, 5), // Show top 5 in chat
          timestamp: new Date(),
        },
      ]);
      setIsLoading(false);
    }
  }, [hits, query, isLoading]);

  const handleSubmit = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    // Extract search intent from natural language
    // For now, simple keyword extraction - Agent Studio will handle NLU
    const searchQuery = extractSearchQuery(input);
    setQuery(searchQuery);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message chat-message-${msg.role}`}>
            <div className="chat-message-content">{msg.content}</div>
            {msg.hits && msg.hits.length > 0 && (
              <div className="chat-message-hits">
                {msg.hits.map((hit) => (
                  <CFPCard
                    key={hit.objectID}
                    hit={hit}
                    onClick={onCfpSelect}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="chat-message chat-message-assistant">
            <div className="chat-loading">Searching...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about CFPs..."
          rows={2}
          disabled={isLoading}
        />
        <button
          className="chat-submit"
          onClick={handleSubmit}
          disabled={isLoading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}

// Simple query extraction - will be replaced by Agent Studio NLU
function extractSearchQuery(input: string): string {
  const lowered = input.toLowerCase();

  // Extract key terms
  const terms: string[] = [];

  // Topic keywords
  const topics = ['ai', 'ml', 'frontend', 'backend', 'devops', 'cloud', 'security', 'data', 'mobile', 'react', 'kubernetes', 'python', 'javascript'];
  for (const topic of topics) {
    if (lowered.includes(topic)) {
      terms.push(topic);
    }
  }

  // Location keywords
  const locations = ['europe', 'usa', 'us', 'asia', 'america', 'uk', 'germany', 'france', 'midwest', 'california'];
  for (const loc of locations) {
    if (lowered.includes(loc)) {
      terms.push(loc);
    }
  }

  // If no specific terms found, use the original input
  return terms.length > 0 ? terms.join(' ') : input;
}
