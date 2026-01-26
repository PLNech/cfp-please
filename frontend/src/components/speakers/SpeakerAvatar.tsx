/**
 * SpeakerAvatar - Reusable speaker avatar with smart fallback chain
 *
 * Tries multiple sources in priority order:
 * 1. image_url (from Sessionize enrichment)
 * 2. GitHub avatar
 * 3. Twitter via unavatar.io
 * 4. LinkedIn via unavatar.io
 * 5. Gravatar (for Algolia speakers with email patterns)
 * 6. UI Avatars (generated from name - always works)
 */

import { useState, useEffect, useMemo } from 'react';
import md5 from 'blueimp-md5';
import type { Speaker } from '../../types';

type AvatarSize = 'sm' | 'md' | 'lg' | 'xl' | number;

interface SpeakerAvatarProps {
  speaker: Speaker;
  size?: AvatarSize;
  borderColor?: string;
  className?: string;
}

const SIZE_MAP: Record<string, number> = {
  sm: 40,
  md: 64,
  lg: 80,
  xl: 120,
};

/**
 * Generate potential Algolia email patterns for Gravatar lookup
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
    const initials = firstName.split('-').map((p) => p[0]).join('');
    patterns.push(`${initials}@algolia.com`);
  }

  return patterns;
}

/**
 * Generate ordered list of avatar URLs to try
 */
function getAvatarUrls(speaker: Speaker, size: number): string[] {
  const urls: string[] = [];

  // 1. Direct image_url (from Sessionize enrichment)
  if (speaker.image_url) {
    urls.push(speaker.image_url);
  }

  // 2. GitHub avatar (very reliable if username exists)
  if (speaker.github) {
    urls.push(`https://github.com/${speaker.github}.png?size=${size}`);
  }

  // 3. Twitter avatar via unavatar.io
  if (speaker.twitter) {
    urls.push(`https://unavatar.io/twitter/${speaker.twitter}?fallback=false`);
  }

  // 4. LinkedIn via unavatar.io
  if (speaker.linkedin) {
    const linkedinMatch = speaker.linkedin.match(/linkedin\.com\/in\/([^\/\?]+)/);
    if (linkedinMatch) {
      urls.push(`https://unavatar.io/linkedin/${linkedinMatch[1]}?fallback=false`);
    }
  }

  // 5. Gravatar with Algolia email patterns
  if (speaker.is_algolia_speaker) {
    const emailPatterns = getAlgoliaEmailPatterns(speaker.name);
    for (const email of emailPatterns) {
      const hash = md5(email.toLowerCase().trim());
      urls.push(`https://gravatar.com/avatar/${hash}?d=404&s=${size}`);
    }
  }

  // 6. UI Avatars as ultimate fallback (always works)
  const encodedName = encodeURIComponent(speaker.name);
  urls.push(
    `https://ui-avatars.com/api/?name=${encodedName}&size=${size}&background=667eea&color=fff&bold=true`
  );

  return urls;
}

export function SpeakerAvatar({
  speaker,
  size = 'md',
  borderColor,
  className = '',
}: SpeakerAvatarProps) {
  const [urlIndex, setUrlIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);

  // Compute pixel size
  const pixelSize = typeof size === 'number' ? size : SIZE_MAP[size] || 64;

  // Get initials for loading/fallback display
  const initials = useMemo(
    () =>
      speaker.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase(),
    [speaker.name]
  );

  // Get ordered avatar URLs
  const avatarUrls = useMemo(
    () => getAvatarUrls(speaker, pixelSize),
    [speaker, pixelSize]
  );

  const currentUrl = avatarUrls[urlIndex];

  // Reset state when speaker changes
  useEffect(() => {
    setUrlIndex(0);
    setLoaded(false);
  }, [speaker.objectID]);

  // Handle load error - try next URL
  const handleError = () => {
    const nextIndex = urlIndex + 1;
    if (nextIndex < avatarUrls.length) {
      setUrlIndex(nextIndex);
      setLoaded(false);
    }
  };

  const handleLoad = () => {
    setLoaded(true);
  };

  const containerStyle: React.CSSProperties = {
    width: pixelSize,
    height: pixelSize,
    borderRadius: '50%',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'var(--color-bg-alt)',
    color: 'var(--color-text-muted)',
    fontSize: pixelSize * 0.35,
    fontWeight: 600,
    flexShrink: 0,
    ...(borderColor && { border: `3px solid ${borderColor}` }),
  };

  return (
    <div className={`speaker-avatar ${className}`} style={containerStyle}>
      {currentUrl && (
        <img
          key={currentUrl}
          src={currentUrl}
          alt={speaker.name}
          onError={handleError}
          onLoad={handleLoad}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            opacity: loaded ? 1 : 0,
            transition: 'opacity 0.2s',
          }}
        />
      )}
      {/* Show initials while loading or if all URLs fail */}
      {!loaded && initials}
    </div>
  );
}
