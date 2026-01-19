/**
 * SpeakerCard - Netflix-style speaker card
 *
 * Displays speaker avatar (with Gravatar fallback), name, company, stats, and achievement badges.
 * Algolia speakers get a special badge for inspiration.
 */

import { useState, useEffect } from 'react';
import md5 from 'blueimp-md5';
import type { Speaker } from '../../types';

interface SpeakerCardProps {
  speaker: Speaker;
  isFollowing?: boolean;
  onClick?: () => void;
  onFollow?: (speakerId: string) => void;
}

/**
 * Generate avatar URLs to try, in priority order.
 * Uses multiple sources for better coverage.
 */
function getAvatarUrls(speaker: Speaker): string[] {
  const urls: string[] = [];
  const size = 80;

  // 1. GitHub avatar (most reliable if username exists)
  if (speaker.github) {
    urls.push(`https://github.com/${speaker.github}.png?size=${size}`);
  }

  // 2. Twitter avatar via unavatar.io (handles API rate limits)
  if (speaker.twitter) {
    urls.push(`https://unavatar.io/twitter/${speaker.twitter}?fallback=false`);
  }

  // 3. LinkedIn via unavatar.io
  if (speaker.linkedin) {
    // Extract username from LinkedIn URL if needed
    const linkedinMatch = speaker.linkedin.match(/linkedin\.com\/in\/([^\/\?]+)/);
    if (linkedinMatch) {
      urls.push(`https://unavatar.io/linkedin/${linkedinMatch[1]}?fallback=false`);
    }
  }

  // 4. Gravatar with potential email patterns
  const emailPatterns = speaker.is_algolia_speaker
    ? getAlgoliaEmailPatterns(speaker.name)
    : [];
  for (const email of emailPatterns) {
    const hash = md5(email.toLowerCase().trim());
    urls.push(`https://gravatar.com/avatar/${hash}?d=404&s=${size}`);
  }

  // 5. UI Avatars as fallback (always works, generates from name)
  const encodedName = encodeURIComponent(speaker.name);
  urls.push(`https://ui-avatars.com/api/?name=${encodedName}&size=${size}&background=667eea&color=fff&bold=true`);

  return urls;
}

/**
 * Generate potential Algolia email patterns for a speaker name.
 */
function getAlgoliaEmailPatterns(name: string): string[] {
  const parts = name.split(' ');
  if (parts.length < 2) return [];

  const firstName = parts[0].toLowerCase();
  const lastName = parts[parts.length - 1].toLowerCase();
  const firstClean = firstName.replace(/-/g, '');

  const patterns = [
    `${firstClean}.${lastName}@algolia.com`,
    `${firstClean}${lastName}@algolia.com`,
  ];

  if (firstName.includes('-')) {
    const initials = firstName.split('-').map(p => p[0]).join('');
    patterns.push(`${initials}@algolia.com`);
  }

  return patterns;
}

export function SpeakerCard({ speaker, isFollowing, onClick, onFollow }: SpeakerCardProps) {
  const [avatarUrlIndex, setAvatarUrlIndex] = useState(0);
  const [avatarLoaded, setAvatarLoaded] = useState(false);

  const initials = speaker.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  // Get all potential avatar URLs to try
  const avatarUrls = getAvatarUrls(speaker);
  const currentAvatarUrl = avatarUrls[avatarUrlIndex];

  // Reset when speaker changes
  useEffect(() => {
    setAvatarUrlIndex(0);
    setAvatarLoaded(false);
  }, [speaker.objectID]);

  // Handle avatar load failure - try next URL
  const handleAvatarError = () => {
    const nextIndex = avatarUrlIndex + 1;
    if (nextIndex < avatarUrls.length) {
      setAvatarUrlIndex(nextIndex);
      setAvatarLoaded(false);
    }
  };

  const handleAvatarLoad = () => {
    setAvatarLoaded(true);
  };

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

      {/* Avatar - tries multiple sources: GitHub, Twitter, LinkedIn, Gravatar, UI Avatars */}
      <div className="speaker-card-avatar">
        {currentAvatarUrl && (
          <img
            key={currentAvatarUrl}
            src={currentAvatarUrl}
            alt={speaker.name}
            onError={handleAvatarError}
            onLoad={handleAvatarLoad}
            className="speaker-card-avatar-img"
            style={{ opacity: avatarLoaded ? 1 : 0 }}
          />
        )}
        {/* Show initials while loading or as ultimate fallback */}
        {!avatarLoaded && initials}
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
