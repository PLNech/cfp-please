/**
 * TalkFlixHome - Netflix-inspired CFP discovery page
 *
 * Browse-first GenUX: carousels of CFPs and talks, hero section,
 * personalization via profile, agent works invisibly.
 */

import React, { useMemo, useCallback, useState } from 'react';
import { Header, ProfileSidebar } from '../components/layout';
import { HeroSection } from '../components/hero';
import { CarouselRow } from '../components/carousel';
import { TalkCard } from '../components/cards';
import { IntelBadges, TrendingIndicator } from '../components/intel';
import { InspireModal } from '../components/inspire';
import { useProfile } from '../hooks/useProfile';
import { useCarouselData, buildCarouselConfigs } from '../hooks/useCarouselData';
import type { CFP, Talk } from '../types';
import { getUrgencyLevel, getUrgencyColor } from '../types';

interface TalkFlixHomeProps {
  onCFPClick?: (cfp: CFP) => void;
  onTalkClick?: (talk: Talk) => void;
}

export function TalkFlixHome({ onCFPClick, onTalkClick }: TalkFlixHomeProps) {
  const {
    profile,
    hasProfile,
    isProfileOpen,
    openProfile,
    closeProfile,
    toggleTopic,
    setExperienceLevel,
    toggleFormat,
    resetProfile,
  } = useProfile();

  const [searchQuery, setSearchQuery] = useState('');
  const [inspireTalk, setInspireTalk] = useState<Talk | null>(null);

  // Build carousel configs based on profile
  const configs = useMemo(() => buildCarouselConfigs(profile), [profile]);

  // Fetch carousel data
  const { carousels, hero, heroLoading } = useCarouselData(configs, profile);

  const handleSubmit = useCallback(() => {
    if (hero?.cfpUrl) {
      window.open(hero.cfpUrl, '_blank', 'noopener');
    } else if (hero?.url) {
      window.open(hero.url, '_blank', 'noopener');
    }
  }, [hero]);

  const handleSeeTalks = useCallback(() => {
    // Scroll to talks carousel
    const talksRow = document.querySelector('[data-carousel="viral-talks"]');
    talksRow?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return (
    <div className="talkflix">
      <Header
        profile={profile}
        hasProfile={hasProfile}
        onProfileClick={openProfile}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      <main className="talkflix-main">
        {/* Hero Section */}
        <HeroSection
          cfp={hero}
          loading={heroLoading}
          onSubmit={handleSubmit}
          onSeeTalks={handleSeeTalks}
        />

        {/* Carousel Rows */}
        <div className="talkflix-rows">
          {configs.map((config) => {
            const data = carousels.get(config.id);
            const isTalksRow = config.index === 'cfps_talks';

            return (
              <div key={config.id} data-carousel={config.id}>
                <CarouselRow
                  icon={config.icon}
                  title={config.title}
                  loading={data?.loading ?? true}
                >
                  {data?.items.map((item) =>
                    isTalksRow ? (
                      <TalkCard
                        key={item.objectID}
                        talk={item as Talk}
                        onClick={() => onTalkClick?.(item as Talk)}
                        onInspire={() => setInspireTalk(item as Talk)}
                      />
                    ) : (
                      <CFPCarouselCard
                        key={item.objectID}
                        cfp={item as CFP}
                        onClick={() => onCFPClick?.(item as CFP)}
                      />
                    )
                  )}
                </CarouselRow>
              </div>
            );
          })}
        </div>
      </main>

      {/* Profile Sidebar */}
      <ProfileSidebar
        isOpen={isProfileOpen}
        onClose={closeProfile}
        profile={profile}
        onToggleTopic={toggleTopic}
        onSetExperience={setExperienceLevel}
        onToggleFormat={toggleFormat}
        onReset={resetProfile}
      />

      {/* Inspire Modal */}
      {inspireTalk && (
        <InspireModal
          talk={inspireTalk}
          matchingCFPs={carousels.get('hot-deadlines')?.items as CFP[] || []}
          onClose={() => setInspireTalk(null)}
          onSelectCFP={onCFPClick}
        />
      )}
    </div>
  );
}

// Compact CFP card for carousels
interface CFPCarouselCardProps {
  cfp: CFP;
  matchScore?: number;
  onClick?: () => void;
}

function CFPCarouselCard({ cfp, matchScore, onClick }: CFPCarouselCardProps) {
  const urgency = getUrgencyLevel(cfp.daysUntilCfpClose);
  const urgencyColor = getUrgencyColor(urgency);

  return (
    <article
      className="cfp-carousel-card"
      onClick={onClick}
      style={{ '--urgency-color': urgencyColor } as React.CSSProperties}
    >
      <div className="cfp-carousel-card-header">
        {cfp.iconUrl ? (
          <img
            src={cfp.iconUrl}
            alt=""
            className="cfp-carousel-card-icon"
            loading="lazy"
          />
        ) : (
          <div className="cfp-carousel-card-gradient" />
        )}
        <TrendingIndicator popularityScore={cfp.popularityScore} />
      </div>

      <div className="cfp-carousel-card-content">
        <h3 className="cfp-carousel-card-title" title={cfp.name}>
          {cfp.name}
        </h3>

        {cfp.location?.city && (
          <p className="cfp-carousel-card-location">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {cfp.location.city}
            {cfp.location.country && `, ${cfp.location.country}`}
          </p>
        )}

        <div className="cfp-carousel-card-meta">
          {cfp.daysUntilCfpClose !== undefined && cfp.daysUntilCfpClose >= 0 && (
            <span className={`cfp-carousel-card-deadline cfp-deadline-${urgency}`}>
              {cfp.daysUntilCfpClose === 0
                ? 'Last day!'
                : cfp.daysUntilCfpClose === 1
                  ? '1 day left'
                  : `${cfp.daysUntilCfpClose} days left`}
            </span>
          )}
        </div>

        <div className="cfp-carousel-card-footer">
          {matchScore !== undefined && matchScore > 0 && (
            <span className="cfp-carousel-card-match">{matchScore}%</span>
          )}
          <IntelBadges cfp={cfp} compact />
        </div>
      </div>
    </article>
  );
}
