/**
 * SpeakerCard - Netflix-style speaker card
 *
 * Displays speaker avatar, name, company, stats, and achievement badges.
 * Algolia speakers get a special badge for inspiration.
 */

import type { Speaker } from '../../types';
import { SpeakerAvatar } from './SpeakerAvatar';

interface SpeakerCardProps {
  speaker: Speaker;
  isFollowing?: boolean;
  onClick?: () => void;
  onFollow?: (speakerId: string) => void;
}

export function SpeakerCard({ speaker, isFollowing, onClick, onFollow }: SpeakerCardProps) {
  const formatViews = (views: number) => {
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`;
    if (views >= 1000) return `${Math.floor(views / 1000)}K`;
    return views.toString();
  };

  const handleFollowClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onFollow) {
      onFollow(speaker.objectID);
    }
  };

  return (
    <article className={`speaker-card ${speaker.is_algolia_speaker ? 'is-algolia-speaker' : ''}`} onClick={onClick}>
      {/* Algolia badge for internal speakers */}
      {speaker.is_algolia_speaker && (
        <div className="speaker-card-algolia-badge" title="Algolia Speaker">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none"/>
          </svg>
        </div>
      )}

      {/* Avatar */}
      <div className="speaker-card-avatar">
        <SpeakerAvatar speaker={speaker} size="md" />
      </div>

      <h3 className="speaker-card-name">{speaker.name}</h3>

      {speaker.company && (
        <p className="speaker-card-company">{speaker.company}</p>
      )}

      <div className="speaker-card-stats">
        <span title="Talks">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          {speaker.talk_count}
        </span>
        <span title="Total views">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          {formatViews(speaker.total_views)}
        </span>
      </div>

      {speaker.achievements && speaker.achievements.length > 0 && (
        <div className="speaker-card-achievements">
          {speaker.achievements.slice(0, 2).map((achievement) => (
            <span key={achievement} className="speaker-achievement-badge">
              {achievement}
            </span>
          ))}
        </div>
      )}

      {onFollow && (
        <button
          className={`speaker-card-follow ${isFollowing ? 'is-following' : ''}`}
          onClick={handleFollowClick}
          aria-label={isFollowing ? 'Unfollow speaker' : 'Follow speaker'}
        >
          {isFollowing ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Following
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Follow
            </>
          )}
        </button>
      )}
    </article>
  );
}
