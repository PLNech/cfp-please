/**
 * Header - TalkFlix top bar
 *
 * Logo + Autocomplete Search + Profile trigger
 * Search shows autocomplete dropdown with CFPs/Talks/Speakers.
 */

import type { UserProfile, CFP, Talk, Speaker } from '../../types';
import { Autocomplete } from '../autocomplete';

interface HeaderProps {
  profile: UserProfile;
  hasProfile: boolean;
  onProfileClick: () => void;
  onCFPSelect?: (cfp: CFP) => void;
  onTalkSelect?: (talk: Talk) => void;
  onSpeakerSelect?: (speaker: Speaker) => void;
}

export function Header({
  profile,
  hasProfile,
  onProfileClick,
  onCFPSelect,
  onTalkSelect,
  onSpeakerSelect,
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

      <div className="header-search-wrapper">
        <Autocomplete
          placeholder="Search CFPs, talks, speakers..."
          onCFPSelect={onCFPSelect}
          onTalkSelect={onTalkSelect}
          onSpeakerSelect={onSpeakerSelect}
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
