/**
 * TalkCard - YouTube talk card with thumbnail
 *
 * Netflix-style card showing talk thumbnail, title, speaker, and views.
 */

import type { Talk } from '../../types';

interface TalkCardProps {
  talk: Talk;
  matchScore?: number; // 0-100 if profile set
  onClick?: () => void;
  onInspire?: () => void;
}

export function TalkCard({ talk, matchScore, onClick, onInspire }: TalkCardProps) {
  const formattedViews = formatViews(talk.view_count);
  const duration = formatDuration(talk.duration_seconds);

  return (
    <article className="talk-card" onClick={onClick}>
      <div className="talk-card-thumbnail">
        {talk.thumbnail_url ? (
          <img
            src={talk.thumbnail_url}
            alt={talk.title}
            loading="lazy"
          />
        ) : (
          <div className="talk-card-placeholder">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        )}

        {duration && <span className="talk-card-duration">{duration}</span>}

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
