/**
 * ProfileSidebar - Slide-in interests picker
 *
 * Set topics once, everything adapts. No auth required.
 */

import type { UserProfile } from '../../types';
import { AVAILABLE_TOPICS } from '../../hooks/useProfile';

interface ProfileSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  profile: UserProfile;
  onToggleTopic: (topic: string) => void;
  onSetExperience: (level: UserProfile['experienceLevel']) => void;
  onToggleFormat: (format: 'in-person' | 'virtual' | 'hybrid') => void;
  onReset: () => void;
}

export function ProfileSidebar({
  isOpen,
  onClose,
  profile,
  onToggleTopic,
  onSetExperience,
  onToggleFormat,
  onReset,
}: ProfileSidebarProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        className={`profile-backdrop ${isOpen ? 'profile-backdrop-open' : ''}`}
        onClick={onClose}
      />

      {/* Sidebar */}
      <aside className={`profile-sidebar ${isOpen ? 'profile-sidebar-open' : ''}`}>
        <header className="profile-header">
          <h2>Personalize</h2>
          <button className="profile-close" onClick={onClose} aria-label="Close">
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
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div className="profile-content">
          {/* Topics */}
          <section className="profile-section">
            <h3>What topics excite you? <span className="profile-hint">(Pick up to 5)</span></h3>
            <div className="profile-chips">
              {AVAILABLE_TOPICS.map((topic) => (
                <button
                  key={topic}
                  className={`profile-chip ${profile.topics.includes(topic) ? 'profile-chip-selected' : ''}`}
                  onClick={() => onToggleTopic(topic)}
                  disabled={!profile.topics.includes(topic) && profile.topics.length >= 5}
                >
                  {topic}
                  {profile.topics.includes(topic) && (
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          </section>

          {/* Experience Level */}
          <section className="profile-section">
            <h3>Your experience level</h3>
            <div className="profile-options">
              {(['beginner', 'intermediate', 'advanced'] as const).map((level) => (
                <label key={level} className="profile-radio">
                  <input
                    type="radio"
                    name="experience"
                    checked={profile.experienceLevel === level}
                    onChange={() => onSetExperience(level)}
                  />
                  <span className="profile-radio-label">
                    {level.charAt(0).toUpperCase() + level.slice(1)}
                  </span>
                </label>
              ))}
            </div>
          </section>

          {/* Event Format */}
          <section className="profile-section">
            <h3>Preferred formats</h3>
            <div className="profile-options">
              {(['in-person', 'virtual', 'hybrid'] as const).map((format) => (
                <label key={format} className="profile-checkbox">
                  <input
                    type="checkbox"
                    checked={profile.preferredFormats.includes(format)}
                    onChange={() => onToggleFormat(format)}
                  />
                  <span className="profile-checkbox-label">
                    {format === 'in-person' ? 'In-Person' : format.charAt(0).toUpperCase() + format.slice(1)}
                  </span>
                </label>
              ))}
            </div>
          </section>
        </div>

        <footer className="profile-footer">
          <button className="profile-reset" onClick={onReset}>
            Reset preferences
          </button>
          <button className="profile-save" onClick={onClose}>
            Save & Personalize
          </button>
        </footer>
      </aside>
    </>
  );
}
