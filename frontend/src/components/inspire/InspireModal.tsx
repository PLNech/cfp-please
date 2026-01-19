/**
 * InspireModal - "Your Talk Could Be Here" fullscreen modal
 *
 * Shows AI-generated talk ideas based on a source talk and user profile.
 * Includes matching CFPs with "why submit" explanations.
 */

import { useState, useEffect } from 'react';
import type { Talk, CFP } from '../../types';
import { useAgentGeneration, type InspirationResult } from '../../hooks/useAgentGeneration';
import { useProfile } from '../../hooks/useProfile';
import { TalkIdeasPanel } from './TalkIdeasPanel';
import './InspireModal.css';

interface InspireModalProps {
  talk: Talk;
  matchingCFPs?: CFP[];
  onClose: () => void;
  onSelectCFP?: (cfp: CFP) => void;
  onSpeakerClick?: (speakerName: string) => void;
  onConferenceClick?: (conferenceName: string) => void;
}

export function InspireModal({ talk, matchingCFPs = [], onClose, onSelectCFP, onSpeakerClick, onConferenceClick }: InspireModalProps) {
  const { profile } = useProfile();
  const { generateInspiration, isGenerating, error } = useAgentGeneration();
  const [result, setResult] = useState<InspirationResult | null>(null);

  // Generate inspiration on mount
  useEffect(() => {
    const generate = async () => {
      const inspiration = await generateInspiration(
        talk,
        profile.topics,
        profile.experienceLevel
      );
      if (inspiration) {
        // Add matching CFPs to the result
        setResult({
          ...inspiration,
          matchingCFPs: matchingCFPs.slice(0, 3).map(cfp => ({
            cfp,
            matchScore: calculateQuickMatch(cfp, profile.topics),
            whySubmit: generateWhySubmit(cfp, talk),
          })),
        });
      }
    };
    generate();
  }, [talk, profile.topics, profile.experienceLevel, matchingCFPs, generateInspiration]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  return (
    <div className="inspire-modal-overlay" onClick={onClose}>
      <div className="inspire-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="inspire-modal-header">
          <div className="inspire-modal-source">
            <span className="inspire-modal-label">Inspired by</span>
            <h3 className="inspire-modal-source-title">{talk.title}</h3>
            <span className="inspire-modal-source-meta">
              {talk.speaker && (
                <>
                  <button
                    className="inspire-modal-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSpeakerClick?.(talk.speaker!);
                    }}
                  >
                    {talk.speaker}
                  </button>
                  {' • '}
                </>
              )}
              {talk.conference_name && (
                <button
                  className="inspire-modal-link"
                  onClick={(e) => {
                    e.stopPropagation();
                    onConferenceClick?.(talk.conference_name!);
                  }}
                >
                  {talk.conference_name}
                </button>
              )}
            </span>
          </div>
          <button className="inspire-modal-close" onClick={onClose}>
            <span aria-hidden="true">&times;</span>
          </button>
        </div>

        {/* Content */}
        <div className="inspire-modal-content">
          {isGenerating ? (
            <div className="inspire-modal-loading">
              <div className="inspire-modal-spinner" />
              <p>Generating talk ideas...</p>
              <p className="inspire-modal-loading-hint">
                Analyzing "{talk.title}" for inspiration
              </p>
            </div>
          ) : error ? (
            <div className="inspire-modal-error">
              <p>Failed to generate ideas</p>
              <p className="inspire-modal-error-detail">{error}</p>
              <button onClick={onClose}>Close</button>
            </div>
          ) : result ? (
            <>
              {/* Talk Ideas */}
              <TalkIdeasPanel ideas={result.talkIdeas} />

              {/* Matching CFPs */}
              {result.matchingCFPs.length > 0 && (
                <div className="inspire-modal-cfps">
                  <h3 className="inspire-modal-section-title">
                    Submit to These CFPs
                  </h3>
                  <div className="inspire-modal-cfp-list">
                    {result.matchingCFPs.map(({ cfp, matchScore, whySubmit }) => (
                      <div
                        key={cfp.objectID}
                        className="inspire-modal-cfp-card"
                        onClick={() => onSelectCFP?.(cfp)}
                      >
                        <div className="inspire-modal-cfp-header">
                          <span className="inspire-modal-cfp-name">{cfp.name}</span>
                          <span className="inspire-modal-cfp-score">
                            {matchScore}% match
                          </span>
                        </div>
                        <p className="inspire-modal-cfp-why">{whySubmit}</p>
                        <div className="inspire-modal-cfp-meta">
                          {cfp.location?.city && (
                            <span>{cfp.location.city}</span>
                          )}
                          {cfp.cfpEndDateISO && (
                            <span>Closes {formatDeadline(cfp.cfpEndDateISO)}</span>
                          )}
                        </div>
                        {cfp.cfpUrl && (
                          <a
                            href={cfp.cfpUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inspire-modal-cfp-submit"
                            onClick={e => e.stopPropagation()}
                          >
                            Submit Now
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ===== Helper Functions =====

function calculateQuickMatch(cfp: CFP, userTopics: string[]): number {
  if (!userTopics.length) return 50;

  const cfpTopics = cfp.topicsNormalized || cfp.topics || [];
  const overlap = userTopics.filter(t =>
    cfpTopics.some(ct => ct.toLowerCase().includes(t.toLowerCase()))
  );

  let score = Math.min(100, 40 + (overlap.length / userTopics.length) * 60);

  if (cfp.hnStories && cfp.hnStories > 0) score += 5;
  if (cfp.popularityScore && cfp.popularityScore > 50) score += 5;

  return Math.round(Math.min(100, score));
}

function generateWhySubmit(cfp: CFP, sourceTalk: Talk): string {
  const reasons: string[] = [];

  // Topic match
  const cfpTopics = cfp.topicsNormalized || cfp.topics || [];
  const talkTopics = sourceTalk.topics || [];
  const sharedTopics = talkTopics.filter(t =>
    cfpTopics.some(ct => ct.toLowerCase().includes(t.toLowerCase()))
  );
  if (sharedTopics.length > 0) {
    reasons.push(`covers ${sharedTopics[0]}`);
  }

  // Popularity signals
  if (cfp.hnStories && cfp.hnStories > 0) {
    reasons.push('trending on HN');
  }

  // Location/format
  if (cfp.eventFormat === 'virtual' || cfp.eventFormat === 'hybrid') {
    reasons.push('remote-friendly');
  }

  if (reasons.length === 0) {
    return 'Great opportunity to share your perspective';
  }

  return `Perfect fit: ${reasons.join(', ')}`;
}

function formatDeadline(isoDate: string): string {
  const deadline = new Date(isoDate);
  const now = new Date();
  const daysUntil = Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

  if (daysUntil < 0) return 'Closed';
  if (daysUntil === 0) return 'Today!';
  if (daysUntil === 1) return 'Tomorrow';
  if (daysUntil <= 7) return `in ${daysUntil} days`;

  return deadline.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
