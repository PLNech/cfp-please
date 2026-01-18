/**
 * TalkCard - YouTube talk card with thumbnail
 *
 * Netflix-style card showing talk thumbnail, title, speaker, and views.
 */

import type { Talk } from '../../types';

interface TalkCardProps {
  talk: Talk;
  matchScore?: number; // 0-100 if profile set
  position?: number; // Position in list (for analytics)
  isFavorite?: boolean;
  onClick?: () => void;
  onInspire?: () => void;
  onToggleFavorite?: (talkId: string) => void;
  onTrackClick?: (objectID: string, position?: number) => void;
}

// Generate a consistent gradient based on text (for missing thumbnails)
function generateGradient(text: string): string {
  // Simple hash function
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = text.charCodeAt(i) + ((hash << 5) - hash);
  }

  // Generate two colors from hash
  const hue1 = Math.abs(hash % 360);
  const hue2 = (hue1 + 40 + (hash % 60)) % 360; // Complementary-ish

  return `linear-gradient(135deg, hsl(${hue1}, 70%, 35%) 0%, hsl(${hue2}, 60%, 25%) 100%)`;
}

export function TalkCard({ talk, matchScore, position, isFavorite, onClick, onInspire, onToggleFavorite, onTrackClick }: TalkCardProps) {
  const formattedViews = formatViews(talk.view_count);
  const duration = formatDuration(talk.duration_seconds);
  const gradient = generateGradient(talk.conference_name || talk.title);

  const handleClick = () => {
    // Track click for Insights/Recommend
    if (onTrackClick && talk.objectID) {
      onTrackClick(talk.objectID, position);
    }
    onClick?.();
  };

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onToggleFavorite && talk.objectID) {
      onToggleFavorite(talk.objectID);
    }
  };

  return (
    <article className="talk-card" onClick={handleClick}>
      <div className="talk-card-thumbnail">
        {talk.thumbnail_url ? (
          <img
            src={talk.thumbnail_url}
            alt={talk.title}
            loading="lazy"
          />
        ) : (
          <div className="talk-card-gradient" style={{ background: gradient }}>
            <span className="talk-card-gradient-text">
              {(talk.conference_name || talk.title).slice(0, 2).toUpperCase()}
            </span>
          </div>
        )}

        {duration && <span className="talk-card-duration">{duration}</span>}

        {/* Favorite heart button */}
        {onToggleFavorite && (
          <button
            className={`talk-card-favorite ${isFavorite ? 'is-favorite' : ''}`}
            onClick={handleFavoriteClick}
            title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill={isFavorite ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
            </svg>
          </button>
        )}

        {onInspire && (
          <button
            className="talk-card-inspire"
            onClick={(e) => {
              e.stopPropagation();
              onInspire();
            }}
            title="Get talk ideas inspired by this"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
            Inspire Me
          </button>
        )}
      </div>

      <div className="talk-card-content">
        <h3 className="talk-card-title" title={talk.title}>
          {talk.title}
        </h3>

        <p className="talk-card-meta">
          {talk.speaker && <span className="talk-card-speaker">{talk.speaker}</span>}
          {talk.speaker && talk.conference_name && ' • '}
          <span className="talk-card-conference">{talk.conference_name}</span>
        </p>

        <div className="talk-card-stats">
          {formattedViews && (
            <span className="talk-card-views" title={`${talk.view_count?.toLocaleString()} views`}>
              {formattedViews} views
            </span>
          )}
          {talk.year && <span className="talk-card-year">{talk.year}</span>}
        </div>

        {matchScore !== undefined && matchScore > 0 && (
          <span className="talk-card-match">{matchScore}% Match</span>
        )}
      </div>
    </article>
  );
}

function formatViews(count?: number): string | null {
  if (!count) return null;
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(0)}K`;
  return count.toString();
}

function formatDuration(seconds?: number): string | null {
  if (!seconds) return null;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins >= 60) {
    const hours = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    return `${hours}:${remainingMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
