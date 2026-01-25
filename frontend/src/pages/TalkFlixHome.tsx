/**
 * TalkFlixHome - Netflix-inspired CFP discovery page
 *
 * Browse-first GenUX: carousels of CFPs and talks, hero section,
 * personalization via profile, agent works invisibly.
 */

import React, { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import createGlobe from 'cobe';
import { Header, ProfileSidebar } from '../components/layout';
import { HeroSection } from '../components/hero';
import { CarouselRow } from '../components/carousel';
import { TalkCard } from '../components/cards';
import { IntelBadges, TrendingIndicator } from '../components/intel';
import { InspireModal } from '../components/inspire';
import { TalkPlayer } from '../components/player';
import { useProfile } from '../hooks/useProfile';
import { useCarouselData, buildCarouselConfigs } from '../hooks/useCarouselData';
import { useInsights } from '../hooks/useInsights';
import { useRelatedTalks, useTrendingTalks, useTrendingCFPs } from '../hooks/useRecommend';
import { useTalksByIds } from '../hooks/useTalksByIds';
import { useTopSpeakers, useSpeakersByTopic } from '../hooks/useSpeakers';
import { calculateMatchScore } from '../hooks/useMatchScore';
import { SpeakerCard, SpeakerModal } from '../components/speakers';
import type { CFP, Talk, Speaker } from '../types';
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
    markTalkWatched,
    toggleFavoriteTalk,
    isFavoriteTalk,
    toggleFavoriteSpeaker,
    isFollowingSpeaker,
    setInterview,
  } = useProfile();

  const [inspireTalk, setInspireTalk] = useState<Talk | null>(null);
  const [selectedTalk, setSelectedTalk] = useState<Talk | null>(null);
  const [playerTalk, setPlayerTalk] = useState<Talk | null>(null);
  const [selectedSpeaker, setSelectedSpeaker] = useState<Speaker | null>(null);

  const navigate = useNavigate();

  // Navigate to search with speaker or conference query
  const handleSpeakerSearch = useCallback((speakerName: string) => {
    navigate(`/search?q=${encodeURIComponent(speakerName)}`);
  }, [navigate]);

  const handleConferenceSearch = useCallback((conferenceName: string) => {
    navigate(`/search?q=${encodeURIComponent(conferenceName)}`);
  }, [navigate]);

  // Insights for click tracking + conversion events
  const { clickTalk, clickCFP, clickInspire, viewCarousel, watchTalk, convertCFP } = useInsights();

  // Related talks for selected talk
  const { relatedTalks, loading: relatedLoading } = useRelatedTalks(
    selectedTalk?.objectID || null
  );

  // Continue Watching - fetch talks from watchedTalks
  const { talks: continueTalks, loading: continueLoading } = useTalksByIds(
    profile.watchedTalks,
    10
  );

  // Favorites - fetch talks from favoriteTalks
  const { talks: favoriteTalks, loading: favoritesLoading } = useTalksByIds(
    profile.favoriteTalks,
    20
  );

  // Top speakers
  const { speakers: topSpeakers, loading: speakersLoading } = useTopSpeakers(15);

  // Trending from Recommend models
  const { relatedTalks: trendingTalks, loading: trendingTalksLoading } = useTrendingTalks(12);
  const { relatedCFPs: trendingCFPs, loading: trendingCFPsLoading } = useTrendingCFPs(12);

  // Topic-specific speakers (if profile has topics)
  const primaryTopic = profile.topics.length > 0 ? profile.topics[0] : null;
  const { speakers: topicSpeakers, loading: topicSpeakersLoading } = useSpeakersByTopic(
    primaryTopic,
    10
  );

  // Build carousel configs based on profile
  const configs = useMemo(() => buildCarouselConfigs(profile), [profile]);

  // Fetch carousel data
  const { carousels, hero, heroLoading } = useCarouselData(configs, profile);

  // Track carousel views when data loads
  useEffect(() => {
    carousels.forEach((data, id) => {
      if (!data.loading && data.items.length > 0) {
        const objectIDs = data.items.map((item) => item.objectID).filter(Boolean) as string[];
        viewCarousel(id, objectIDs);
      }
    });
  }, [carousels, viewCarousel]);

  const handleSubmit = useCallback(() => {
    if (hero?.objectID) {
      convertCFP(hero.objectID); // Track CFP submission conversion
    }
    if (hero?.cfpUrl) {
      window.open(hero.cfpUrl, '_blank', 'noopener');
    } else if (hero?.url) {
      window.open(hero.url, '_blank', 'noopener');
    }
  }, [hero, convertCFP]);

  const handleSeeTalks = useCallback(() => {
    // Scroll to talks carousel
    const talksRow = document.querySelector('[data-carousel="viral-talks"]');
    talksRow?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const handleTalkClick = useCallback((talk: Talk, position?: number) => {
    clickTalk(talk.objectID, position);
    markTalkWatched(talk.objectID);
    setSelectedTalk(talk);
    setPlayerTalk(talk); // Open the player modal
    onTalkClick?.(talk);
  }, [clickTalk, markTalkWatched, onTalkClick]);

  const handleCFPClick = useCallback((cfp: CFP, position?: number) => {
    clickCFP(cfp.objectID, position);
    onCFPClick?.(cfp);
  }, [clickCFP, onCFPClick]);

  const handleInspireClick = useCallback((talk: Talk) => {
    clickInspire(talk.objectID);
    setInspireTalk(talk);
  }, [clickInspire]);

  // Handle autocomplete selections
  const handleAutocompleteSelect = useCallback((cfp: CFP) => {
    clickCFP(cfp.objectID);
    onCFPClick?.(cfp);
  }, [clickCFP, onCFPClick]);

  const handleAutocompleteTalkSelect = useCallback((talk: Talk) => {
    handleTalkClick(talk);
  }, [handleTalkClick]);

  const handleAutocompleteSpeakerSelect = useCallback((speaker: Speaker) => {
    setSelectedSpeaker(speaker);
  }, []);

  return (
    <div className="talkflix">
      <Header
        profile={profile}
        hasProfile={hasProfile}
        onProfileClick={openProfile}
        onCFPSelect={handleAutocompleteSelect}
        onTalkSelect={handleAutocompleteTalkSelect}
        onSpeakerSelect={handleAutocompleteSpeakerSelect}
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
          {/* Continue Watching - only if user has watched talks */}
          {continueTalks.length > 0 && (
            <div data-carousel="continue-watching">
              <CarouselRow
                icon="⏯️"
                title="Continue Watching"
                loading={continueLoading}
              >
                {continueTalks.map((talk, index) => (
                  <TalkCard
                    key={talk.objectID}
                    talk={talk}
                    position={index + 1}
                    isFavorite={isFavoriteTalk(talk.objectID)}
                    onClick={() => handleTalkClick(talk, index + 1)}
                    onInspire={() => handleInspireClick(talk)}
                    onToggleFavorite={toggleFavoriteTalk}
                    onTrackClick={clickTalk}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {/* Your Favorites - only if user has favorites */}
          {favoriteTalks.length > 0 && (
            <div data-carousel="favorites">
              <CarouselRow
                icon="❤️"
                title="Your Favorites"
                loading={favoritesLoading}
              >
                {favoriteTalks.map((talk, index) => (
                  <TalkCard
                    key={talk.objectID}
                    talk={talk}
                    position={index + 1}
                    isFavorite={true}
                    onClick={() => handleTalkClick(talk, index + 1)}
                    onInspire={() => handleInspireClick(talk)}
                    onToggleFavorite={toggleFavoriteTalk}
                    onTrackClick={clickTalk}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {/* Trending Talks - from Recommend model */}
          {(trendingTalks.length > 0 || trendingTalksLoading) && (
            <div data-carousel="trending-talks">
              <CarouselRow
                icon="🔥"
                title="Trending Talks"
                loading={trendingTalksLoading}
              >
                {trendingTalks.map((talk, index) => (
                  <TalkCard
                    key={talk.objectID}
                    talk={talk}
                    position={index + 1}
                    isFavorite={isFavoriteTalk(talk.objectID)}
                    onClick={() => handleTalkClick(talk, index + 1)}
                    onInspire={() => handleInspireClick(talk)}
                    onToggleFavorite={toggleFavoriteTalk}
                    onTrackClick={clickTalk}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {/* Trending CFPs - from Recommend model */}
          {(trendingCFPs.length > 0 || trendingCFPsLoading) && (
            <div data-carousel="trending-cfps">
              <CarouselRow
                icon="📈"
                title="Trending CFPs"
                loading={trendingCFPsLoading}
              >
                {trendingCFPs.map((cfp, index) => (
                  <CFPCarouselCard
                    key={cfp.objectID}
                    cfp={cfp}
                    matchScore={hasProfile ? calculateMatchScore(cfp, profile).score : undefined}
                    matchReasons={hasProfile ? calculateMatchScore(cfp, profile).reasons : undefined}
                    onClick={() => handleCFPClick(cfp, index + 1)}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {configs.map((config) => {
            const data = carousels.get(config.id);
            const isTalksRow = config.index === 'cfps_talks';

            // Only render carousels that have data (or are still loading)
            const hasItems = data?.items && data.items.length > 0;
            const isLoading = data?.loading ?? true;
            if (!hasItems && !isLoading) return null;

            return (
              <div key={config.id} data-carousel={config.id}>
                <CarouselRow
                  icon={config.icon}
                  title={config.title}
                  loading={isLoading}
                >
                  {data?.items.map((item, index) =>
                    isTalksRow ? (
                      <TalkCard
                        key={item.objectID}
                        talk={item as Talk}
                        position={index + 1}
                        isFavorite={isFavoriteTalk(item.objectID)}
                        onClick={() => handleTalkClick(item as Talk, index + 1)}
                        onInspire={() => handleInspireClick(item as Talk)}
                        onToggleFavorite={toggleFavoriteTalk}
                        onTrackClick={clickTalk}
                      />
                    ) : (
                      <CFPCarouselCard
                        key={item.objectID}
                        cfp={item as CFP}
                        matchScore={hasProfile ? calculateMatchScore(item as CFP, profile).score : undefined}
                        matchReasons={hasProfile ? calculateMatchScore(item as CFP, profile).reasons : undefined}
                        onClick={() => handleCFPClick(item as CFP, index + 1)}
                      />
                    )
                  )}
                </CarouselRow>
              </div>
            );
          })}

          {/* Related Talks - shown when a talk is selected */}
          {selectedTalk && relatedTalks.length > 0 && (
            <div data-carousel="related-talks">
              <CarouselRow
                icon="🔗"
                title={`More like "${selectedTalk.title.slice(0, 30)}..."`}
                loading={relatedLoading}
              >
                {relatedTalks.map((talk, index) => (
                  <TalkCard
                    key={talk.objectID}
                    talk={talk}
                    position={index + 1}
                    isFavorite={isFavoriteTalk(talk.objectID)}
                    onClick={() => handleTalkClick(talk, index + 1)}
                    onInspire={() => handleInspireClick(talk)}
                    onToggleFavorite={toggleFavoriteTalk}
                    onTrackClick={clickTalk}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {/* Top Speakers */}
          {topSpeakers.length > 0 && (
            <div data-carousel="top-speakers">
              <CarouselRow
                icon="🏆"
                title="Top Speakers"
                loading={speakersLoading}
              >
                {topSpeakers.map((speaker) => (
                  <SpeakerCard
                    key={speaker.objectID}
                    speaker={speaker}
                    isFollowing={isFollowingSpeaker(speaker.objectID)}
                    onClick={() => setSelectedSpeaker(speaker)}
                    onFollow={toggleFavoriteSpeaker}
                  />
                ))}
              </CarouselRow>
            </div>
          )}

          {/* Topic Experts - if profile has topics */}
          {primaryTopic && topicSpeakers.length > 0 && (
            <div data-carousel="topic-speakers">
              <CarouselRow
                icon="🎯"
                title={`${primaryTopic} Experts`}
                loading={topicSpeakersLoading}
              >
                {topicSpeakers.map((speaker) => (
                  <SpeakerCard
                    key={speaker.objectID}
                    speaker={speaker}
                    isFollowing={isFollowingSpeaker(speaker.objectID)}
                    onClick={() => setSelectedSpeaker(speaker)}
                    onFollow={toggleFavoriteSpeaker}
                  />
                ))}
              </CarouselRow>
            </div>
          )}
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
        onInterviewComplete={setInterview}
      />

      {/* Inspire Modal */}
      {inspireTalk && (
        <InspireModal
          talk={inspireTalk}
          matchingCFPs={carousels.get('hot-deadlines')?.items as CFP[] || []}
          onClose={() => setInspireTalk(null)}
          onSelectCFP={onCFPClick}
          onSpeakerClick={handleSpeakerSearch}
          onConferenceClick={handleConferenceSearch}
        />
      )}

      {/* Speaker Modal */}
      {selectedSpeaker && (
        <SpeakerModal
          speaker={selectedSpeaker}
          isFollowing={isFollowingSpeaker(selectedSpeaker.objectID)}
          onClose={() => setSelectedSpeaker(null)}
          onFollow={toggleFavoriteSpeaker}
          onTalkClick={(talk) => setPlayerTalk(talk)}
          onConferenceClick={handleConferenceSearch}
          isFavoriteTalk={isFavoriteTalk}
          onToggleFavoriteTalk={toggleFavoriteTalk}
        />
      )}

      {/* Talk Player Modal */}
      {playerTalk && (
        <TalkPlayer
          talk={playerTalk}
          isOpen={!!playerTalk}
          onClose={() => setPlayerTalk(null)}
          onTrackWatch={(talkId) => {
            markTalkWatched(talkId);
            watchTalk(talkId); // Conversion event for Algolia Insights
          }}
        />
      )}
    </div>
  );
}

// Compact CFP card for carousels
interface CFPCarouselCardProps {
  cfp: CFP;
  matchScore?: number;
  matchReasons?: string[];
  onClick?: () => void;
}

// Pick a random city image (consistent per CFP using objectID as seed)
function pickCityImage(cfp: CFP): string | null {
  if (!cfp.city_image_urls?.length) return null;
  // Use objectID hash for consistent random selection
  let hash = 0;
  for (let i = 0; i < cfp.objectID.length; i++) {
    hash = cfp.objectID.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % cfp.city_image_urls.length;
  return cfp.city_image_urls[index];
}

// Globe overlay for CFP cards - shows location with subtle globe in corner
function CardGlobe({ lat, lng }: { lat: number; lng: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const globeRef = useRef<ReturnType<typeof createGlobe> | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    // Center globe view on the marker location
    const targetPhi = ((-lng - 90) * Math.PI) / 180;
    const targetTheta = (lat * Math.PI) / 180;

    globeRef.current = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: 640,
      height: 640,
      phi: targetPhi,
      theta: targetTheta,
      dark: 1,
      diffuse: 1.5,
      mapSamples: 16000,
      mapBrightness: 8,
      baseColor: [0.2, 0.25, 0.3],
      markerColor: [1, 0.3, 0.3],
      glowColor: [0.15, 0.2, 0.25],
      markers: [{ location: [lat, lng], size: 0.12 }],
      onRender: (state) => {
        state.phi = targetPhi;
        state.theta = targetTheta;
      },
    });

    return () => {
      if (globeRef.current) {
        globeRef.current.destroy();
        globeRef.current = null;
      }
    };
  }, [lat, lng]);

  return <canvas ref={canvasRef} className="cfp-card-globe" />;
}

function CFPCarouselCard({ cfp, matchScore, matchReasons, onClick }: CFPCarouselCardProps) {
  const urgency = getUrgencyLevel(cfp.daysUntilCfpClose);
  const urgencyColor = getUrgencyColor(urgency);
  const cityImage = useMemo(() => pickCityImage(cfp), [cfp]);
  const hasCityImage = !!cityImage;
  const hasGeoLoc = cfp._geoloc?.lat && cfp._geoloc?.lng;

  return (
    <article
      className={`cfp-carousel-card ${hasCityImage ? 'has-city-image' : ''} ${hasGeoLoc ? 'has-globe' : ''}`}
      onClick={onClick}
      style={{ '--urgency-color': urgencyColor } as React.CSSProperties}
    >
      <div className="cfp-carousel-card-header">
        {cityImage ? (
          <>
            <img
              src={cityImage}
              alt={cfp.location?.city || ''}
              className="cfp-carousel-card-city-bg"
              loading="lazy"
            />
            <div className="cfp-carousel-card-city-overlay" />
            {cfp.iconUrl && (
              <img
                src={cfp.iconUrl}
                alt=""
                className="cfp-carousel-card-icon-overlay"
                loading="lazy"
              />
            )}
          </>
        ) : cfp.iconUrl ? (
          <img
            src={cfp.iconUrl}
            alt=""
            className="cfp-carousel-card-icon"
            loading="lazy"
          />
        ) : (
          <div className="cfp-carousel-card-gradient">
            <span className="cfp-carousel-card-gradient-text">
              {cfp.name.split(' ').slice(0, 2).join(' ')}
            </span>
          </div>
        )}
        {/* Globe overlay when geolocation available */}
        {hasGeoLoc && <CardGlobe lat={cfp._geoloc!.lat} lng={cfp._geoloc!.lng} />}
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
            <span
              className={`cfp-carousel-card-match ${matchScore >= 70 ? 'match-high' : matchScore >= 50 ? 'match-medium' : 'match-low'}`}
              title={matchReasons?.length ? matchReasons.join(' • ') : undefined}
            >
              {matchScore}% match
            </span>
          )}
          <IntelBadges cfp={cfp} compact />
        </div>
      </div>
    </article>
  );
}
