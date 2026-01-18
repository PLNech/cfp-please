/**
 * Header - TalkFlix top bar
 *
 * Logo + Search + Profile trigger
 */

import type { UserProfile } from '../../types';

interface HeaderProps {
  profile: UserProfile;
  hasProfile: boolean;
  onProfileClick: () => void;
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
}

export function Header({
  profile,
  hasProfile,
  onProfileClick,
  searchQuery = '',
  onSearchChange,
}: HeaderProps) {
  return (
    <header className="talkflix-header">
      <div className="header-brand">
        <h1 className="header-logo">
          <span className="header-logo-icon">🎤</span>
          TalkFlix
        </h1>
        <span className="header-tagline">Find your next talk</span>
      </div>

      <div className="header-search">
        <svg
          className="header-search-icon"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="search"
          placeholder="Search CFPs, talks, speakers..."
          value={searchQuery}
          onChange={(e) => onSearchChange?.(e.target.value)}
          className="header-search-input"
        />
      </div>

      <button
        className={`header-profile ${hasProfile ? 'header-profile-active' : ''}`}
        onClick={onProfileClick}
        aria-label="Open profile settings"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
        {hasProfile && (
          <span className="header-profile-badge">{profile.topics.length}</span>
        )}
      </button>
    </header>
  );
}
