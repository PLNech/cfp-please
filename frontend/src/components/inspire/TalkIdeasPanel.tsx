/**
 * TalkIdeasPanel - Displays AI-generated talk title suggestions
 *
 * Shows a list of talk ideas with titles, descriptions, and unique angles.
 * Each idea can be copied or used as a starting point.
 */

import { useState } from 'react';
import type { TalkIdea } from '../../hooks/useAgentGeneration';
import './TalkIdeasPanel.css';

interface TalkIdeasPanelProps {
  ideas: TalkIdea[];
}

export function TalkIdeasPanel({ ideas }: TalkIdeasPanelProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = async (idea: TalkIdea, index: number) => {
    const text = `${idea.title}\n\n${idea.description}\n\nUnique angle: ${idea.angle}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (ideas.length === 0) {
    return (
      <div className="talk-ideas-empty">
        <p>No ideas generated yet</p>
      </div>
    );
  }

  return (
    <div className="talk-ideas-panel">
      <h3 className="talk-ideas-title">Your Talk Could Be...</h3>
      <div className="talk-ideas-list">
        {ideas.map((idea, index) => (
          <div key={index} className="talk-idea-card">
            <div className="talk-idea-number">{index + 1}</div>
            <div className="talk-idea-content">
              <h4 className="talk-idea-title">{idea.title}</h4>
              <p className="talk-idea-description">{idea.description}</p>
              <div className="talk-idea-angle">
                <span className="talk-idea-angle-label">Unique angle:</span>
                <span className="talk-idea-angle-text">{idea.angle}</span>
              </div>
            </div>
            <button
              className={`talk-idea-copy ${copiedIndex === index ? 'copied' : ''}`}
              onClick={() => copyToClipboard(idea, index)}
              title="Copy to clipboard"
            >
              {copiedIndex === index ? 'Copied!' : 'Copy'}
            </button>
          </div>
        ))}
      </div>
      <p className="talk-ideas-hint">
        Click "Copy" to use any idea as a starting point for your CFP submission
      </p>
    </div>
  );
}
