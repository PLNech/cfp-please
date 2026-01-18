/**
 * SpeakerModal - Full speaker profile modal
 *
 * Shows detailed stats, achievements, topics, and talks carousel.
 */

import { useTalksByIds } from '../../hooks/useTalksByIds';
import { TalkCard } from '../cards/TalkCard';
import type { Speaker, Talk } from '../../types';

interface SpeakerModalProps {
  speaker: Speaker;
  isFollowing?: boolean;
  onClose: () => void;
  onFollow?: (speakerId: string) => void;
  onTalkClick?: (talk: Talk) => void;
  isFavoriteTalk?: (talkId: string) => boolean;
  onToggleFavoriteTalk?: (talkId: string) => void;
}

export function SpeakerModal({
  speaker,
  isFollowing,
  onClose,
  onFollow,
  onTalkClick,
  isFavoriteTalk,
  onToggleFavoriteTalk,
}: SpeakerModalProps) {
  // Fetch speaker's top talks
  const { talks, loading } = useTalksByIds(speaker.top_talk_ids || [], 10);

  const initials = speaker.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const formatViews = (views: number) => {
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`;
    if (views >= 1000) return `${Math.floor(views / 1000)}K`;
    return views.toString();
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="speaker-modal-overlay" onClick={handleBackdropClick}>
      <div className="speaker-modal">
        <button className="speaker-modal-close" onClick={onClose} aria-label="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* Header */}
        <div className="speaker-modal-header">
          <div className="speaker-modal-avatar">{initials}</div>
          <div className="speaker-modal-info">
            <h2 className="speaker-modal-name">{speaker.name}</h2>
            {speaker.company && (
              <p className="speaker-modal-company">{speaker.company}</p>
            )}
            {onFollow && (
              <button
                className={`speaker-modal-follow ${isFollowing ? 'is-following' : ''}`}
                onClick={() => onFollow(speaker.objectID)}
              >
                {isFollowing ? 'Following' : 'Follow'}
              </button>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="speaker-modal-stats">
          <div className="speaker-stat">
            <span className="speaker-stat-value">{speaker.talk_count}</span>
            <span className="speaker-stat-label">Talks</span>
          </div>
          <div className="speaker-stat">
            <span className="speaker-stat-value">{formatViews(speaker.total_views)}</span>
            <span className="speaker-stat-label">Total Views</span>
          </div>
          <div className="speaker-stat">
            <span className="speaker-stat-value">{speaker.conference_count || speaker.conferences?.length || 0}</span>
            <span className="speaker-stat-label">Conferences</span>
          </div>
          <div className="speaker-stat">
            <span className="speaker-stat-value">{speaker.active_years || speaker.years_active?.length || 0}</span>
            <span className="speaker-stat-label">Years Active</span>
          </div>
        </div>

        {/* Achievements */}
        {speaker.achievements && speaker.achievements.length > 0 && (
          <div className="speaker-modal-section">
            <h3 className="speaker-modal-section-title">Achievements</h3>
            <div className="speaker-modal-achievements">
              {speaker.achievements.map((achievement) => (
                <span key={achievement} className="speaker-achievement-badge large">
                  {achievement}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Topics */}
        {speaker.topics && speaker.topics.length > 0 && (
          <div className="speaker-modal-section">
            <h3 className="speaker-modal-section-title">Topics</h3>
            <div className="speaker-modal-topics">
              {speaker.topics.slice(0, 8).map((topic) => (
                <span key={topic} className="topic-tag">
                  {topic}
                  {speaker.topic_counts?.[topic] && (
                    <span className="topic-count">{speaker.topic_counts[topic]}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Conferences */}
        {speaker.conferences && speaker.conferences.length > 0 && (
          <div className="speaker-modal-section">
            <h3 className="speaker-modal-section-title">Conferences</h3>
            <div className="speaker-modal-conferences">
              {speaker.conferences.slice(0, 6).map((conf) => (
                <span key={conf} className="conference-tag">
                  {conf}
                  {speaker.conference_counts?.[conf] && (
                    <span className="conf-count">{speaker.conference_counts[conf]}x</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Top Talks */}
        {(talks.length > 0 || loading) && (
          <div className="speaker-modal-section">
            <h3 className="speaker-modal-section-title">Top Talks</h3>
            <div className="speaker-modal-talks">
              {loading ? (
                <div className="speaker-modal-loading">Loading talks...</div>
              ) : (
                talks.map((talk, index) => (
                  <TalkCard
                    key={talk.objectID}
                    talk={talk}
                    position={index + 1}
                    isFavorite={isFavoriteTalk?.(talk.objectID)}
                    onClick={() => onTalkClick?.(talk)}
                    onToggleFavorite={onToggleFavoriteTalk}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* Social Links */}
        {(speaker.twitter || speaker.linkedin || speaker.github || speaker.profile_url) && (
          <div className="speaker-modal-links">
            {speaker.twitter && (
              <a href={`https://twitter.com/${speaker.twitter}`} target="_blank" rel="noopener noreferrer">
                Twitter
              </a>
            )}
            {speaker.linkedin && (
              <a href={speaker.linkedin} target="_blank" rel="noopener noreferrer">
                LinkedIn
              </a>
            )}
            {speaker.github && (
              <a href={`https://github.com/${speaker.github}`} target="_blank" rel="noopener noreferrer">
                GitHub
              </a>
            )}
            {speaker.profile_url && (
              <a href={speaker.profile_url} target="_blank" rel="noopener noreferrer">
                Website
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
