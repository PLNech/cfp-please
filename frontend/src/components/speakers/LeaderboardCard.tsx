/**
 * LeaderboardCard - Ranked speaker card for leaderboard display
 *
 * Shows position badge with medal colors for top 3, compact stats, and achievements.
 * Click opens SpeakerModal.
 */

import type { Speaker } from '../../types';
import { SpeakerAvatar } from './SpeakerAvatar';

interface LeaderboardCardProps {
  speaker: Speaker;
  position: number;
  onClick?: () => void;
}

/**
 * Get medal styling for position
 */
function getMedalStyle(position: number): { color: string; bg: string; emoji: string } {
  switch (position) {
    case 1:
      return { color: '#FFD700', bg: 'rgba(255, 215, 0, 0.15)', emoji: '🥇' };
    case 2:
      return { color: '#C0C0C0', bg: 'rgba(192, 192, 192, 0.15)', emoji: '🥈' };
    case 3:
      return { color: '#CD7F32', bg: 'rgba(205, 127, 50, 0.15)', emoji: '🥉' };
    default:
      return { color: 'var(--color-text-muted)', bg: 'transparent', emoji: '' };
  }
}

export function LeaderboardCard({ speaker, position, onClick }: LeaderboardCardProps) {
  const medal = getMedalStyle(position);

  const formatViews = (views: number) => {
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`;
    if (views >= 1000) return `${Math.floor(views / 1000)}K`;
    return views.toString();
  };

  return (
    <article
      className={`leaderboard-card ${position <= 3 ? 'leaderboard-card--medal' : ''}`}
      onClick={onClick}
      style={{
        '--medal-color': medal.color,
        '--medal-bg': medal.bg,
      } as React.CSSProperties}
    >
      {/* Position badge */}
      <div className={`leaderboard-position ${position <= 3 ? 'leaderboard-position--medal' : ''}`}>
        {medal.emoji || `#${position}`}
      </div>

      {/* Avatar */}
      <SpeakerAvatar speaker={speaker} size="sm" className="leaderboard-avatar" />

      {/* Info */}
      <div className="leaderboard-info">
        <h3 className="leaderboard-name">{speaker.name}</h3>
        {speaker.company && (
          <p className="leaderboard-company">@{speaker.company}</p>
        )}
      </div>

      {/* Stats row */}
      <div className="leaderboard-stats">
        <span className="leaderboard-stat" title="Talks">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          {speaker.talk_count}
        </span>
        <span className="leaderboard-stat" title="Total views">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          {formatViews(speaker.total_views)}
        </span>
        {speaker.active_years && (
          <span className="leaderboard-stat" title="Years active">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            {speaker.active_years}y
          </span>
        )}
      </div>

      {/* Achievements */}
      {speaker.achievements && speaker.achievements.length > 0 && (
        <div className="leaderboard-achievements">
          {speaker.achievements.slice(0, 2).map((achievement) => (
            <span key={achievement} className="leaderboard-badge">
              {achievement}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
