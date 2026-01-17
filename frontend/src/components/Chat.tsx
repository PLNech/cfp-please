import { useState, useRef, useEffect } from 'react';
import type { KeyboardEvent } from 'react';
import type { CFP } from '../types';
import { CFPCard } from './CFPCard';
import { useAgentStudio } from '../hooks/useAgentStudio';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: CFP[];
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
      content: "Hi! I'm your CFP finder. Ask me things like:\n\n• \"AI conferences in Europe closing soon\"\n• \"Frontend talks in the Midwest\"\n• \"Security conferences with workshops\"",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { sendMessage, isLoading, highlightedCfps } = useAgentStudio();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const query = input;
    setInput('');

    // Call Agent Studio
    const response = await sendMessage(query);

    if (response) {
      // Map sources to CFP format - use actual objectID from response
      const cfpSources: CFP[] = (response.sources || []).map((s) => ({
        objectID: s.objectID || `source-${Math.random().toString(36).slice(2)}`,
        name: s.name || 'Unknown',
        description: s.description,
        topicsNormalized: s.topicsNormalized || [],
        topics: s.topicsNormalized || [],
        location: s.location || {},
        cfpEndDateISO: s.cfpEndDateISO,
        daysUntilCfpClose: s.daysUntilCfpClose,
        cfpUrl: s.cfpUrl,
        url: s.url,
        languages: [],
        technologies: [],
        talkTypes: [],
        industries: [],
        source: 'agent',
        enriched: true,
      }));

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.message,
          sources: cfpSources.length > 0 ? cfpSources : undefined,
          timestamp: new Date(),
        },
      ]);
    } else {
      // Response is null - show error
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Sorry, I had trouble processing that. Please try again.`,
          timestamp: new Date(),
        },
      ]);
    }
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
            {msg.sources && msg.sources.length > 0 && (
              <div className="chat-message-hits">
                {msg.sources.map((source) => (
                  <CFPCard
                    key={source.objectID}
                    hit={source}
                    onClick={onCfpSelect}
                    isHighlighted={highlightedCfps.has(source.objectID)}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="chat-message chat-message-assistant">
            <div className="chat-loading">
              <span className="chat-loading-dot"></span>
              <span className="chat-loading-dot"></span>
              <span className="chat-loading-dot"></span>
            </div>
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
          {isLoading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
