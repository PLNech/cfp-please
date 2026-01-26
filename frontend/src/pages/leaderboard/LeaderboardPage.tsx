/**
 * LeaderboardPage - Competitive speaker rankings with gamification
 *
 * Features:
 * - Hero section with trophy
 * - Podium for top 3 (gold/silver/bronze)
 * - Ranked grid for positions 4-20
 * - Category carousels (Rising Stars, Most Prolific, etc.)
 */

import { useState, useMemo } from 'react';
import { Header } from '../../components/layout';
import { CarouselRow } from '../../components/carousel';
import { SpeakerModal, LeaderboardCard, SpeakerCard } from '../../components/speakers';
import { useProfile } from '../../hooks/useProfile';
import {
  useSpeakersLeaderboard,
  useRisingStars,
  type LeaderboardSort,
} from '../../hooks/useSpeakers';
import type { Speaker } from '../../types';
import './LeaderboardPage.css';

export function LeaderboardPage() {
  const { profile, hasProfile, openProfile } = useProfile();
  const [selectedSpeaker, setSelectedSpeaker] = useState<Speaker | null>(null);
  const [sortBy, setSortBy] = useState<LeaderboardSort>('influence');

  // Fetch main leaderboard
  const { speakers: allSpeakers, loading } = useSpeakersLeaderboard(sortBy, 50);

  // Category carousels
  const { speakers: risingStars, loading: risingLoading } = useRisingStars(15);
  const { speakers: prolificSpeakers } = useSpeakersLeaderboard('talks', 15);
  const { speakers: viewedSpeakers } = useSpeakersLeaderboard('views', 15);
  const { speakers: veteranSpeakers } = useSpeakersLeaderboard('years', 15);

  // Split into podium and grid
  const podium = useMemo(() => allSpeakers.slice(0, 3), [allSpeakers]);
  const grid = useMemo(() => allSpeakers.slice(3, 20), [allSpeakers]);

  // Compute stats
  const stats = useMemo(() => {
    if (allSpeakers.length === 0) return { total: 0, totalViews: 0, totalTalks: 0 };
    return {
      total: allSpeakers.length,
      totalViews: allSpeakers.reduce((sum, s) => sum + (s.total_views || 0), 0),
      totalTalks: allSpeakers.reduce((sum, s) => sum + (s.talk_count || 0), 0),
    };
  }, [allSpeakers]);

  const formatNumber = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${Math.floor(n / 1000)}K`;
    return n.toString();
  };

  return (
    <div className="leaderboard-page">
      <Header
        profile={profile}
        hasProfile={hasProfile}
        onProfileClick={openProfile}
      />

      <main className="leaderboard-main">
        {/* Hero Section */}
        <section className="leaderboard-hero">
          <div className="leaderboard-hero-content">
            <div className="leaderboard-trophy">🏆</div>
            <h1 className="leaderboard-title">Speaker Leaderboard</h1>
            <p className="leaderboard-subtitle">
              Celebrating the voices that shape our community
            </p>

            {/* Stats ribbon */}
            <div className="leaderboard-stats-ribbon">
              <div className="leaderboard-stat-item">
                <span className="stat-value">{formatNumber(stats.total)}</span>
                <span className="stat-label">Speakers</span>
              </div>
              <div className="leaderboard-stat-item">
                <span className="stat-value">{formatNumber(stats.totalTalks)}</span>
                <span className="stat-label">Talks</span>
              </div>
              <div className="leaderboard-stat-item">
                <span className="stat-value">{formatNumber(stats.totalViews)}</span>
                <span className="stat-label">Views</span>
              </div>
            </div>

            {/* Sort selector */}
            <div className="leaderboard-sort">
              <span className="sort-label">Rank by:</span>
              <div className="sort-buttons">
                {(['influence', 'talks', 'views', 'years'] as LeaderboardSort[]).map((option) => (
                  <button
                    key={option}
                    className={`sort-btn ${sortBy === option ? 'active' : ''}`}
                    onClick={() => setSortBy(option)}
                  >
                    {option === 'influence' && '🎯 Influence'}
                    {option === 'talks' && '🎤 Talks'}
                    {option === 'views' && '👁 Views'}
                    {option === 'years' && '📅 Experience'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Podium - Top 3 */}
        {!loading && podium.length >= 3 && (
          <section className="leaderboard-podium">
            <h2 className="sr-only">Top 3 Speakers</h2>
            <div className="podium-container">
              {/* #2 - Silver (left) */}
              <div className="podium-place podium-silver" onClick={() => setSelectedSpeaker(podium[1])}>
                <div className="podium-medal">🥈</div>
                <div className="podium-avatar">
                  <img
                    src={podium[1].image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(podium[1].name)}&size=120&background=C0C0C0&color=fff`}
                    alt={podium[1].name}
                  />
                </div>
                <h3 className="podium-name">{podium[1].name}</h3>
                <p className="podium-company">{podium[1].company}</p>
                <div className="podium-score">{formatNumber(podium[1].total_views)} views</div>
                <div className="podium-stand podium-stand-2">2</div>
              </div>

              {/* #1 - Gold (center, elevated) */}
              <div className="podium-place podium-gold" onClick={() => setSelectedSpeaker(podium[0])}>
                <div className="podium-medal">🥇</div>
                <div className="podium-avatar">
                  <img
                    src={podium[0].image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(podium[0].name)}&size=120&background=FFD700&color=fff`}
                    alt={podium[0].name}
                  />
                </div>
                <h3 className="podium-name">{podium[0].name}</h3>
                <p className="podium-company">{podium[0].company}</p>
                <div className="podium-score">{formatNumber(podium[0].total_views)} views</div>
                <div className="podium-stand podium-stand-1">1</div>
              </div>

              {/* #3 - Bronze (right) */}
              <div className="podium-place podium-bronze" onClick={() => setSelectedSpeaker(podium[2])}>
                <div className="podium-medal">🥉</div>
                <div className="podium-avatar">
                  <img
                    src={podium[2].image_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(podium[2].name)}&size=120&background=CD7F32&color=fff`}
                    alt={podium[2].name}
                  />
                </div>
                <h3 className="podium-name">{podium[2].name}</h3>
                <p className="podium-company">{podium[2].company}</p>
                <div className="podium-score">{formatNumber(podium[2].total_views)} views</div>
                <div className="podium-stand podium-stand-3">3</div>
              </div>
            </div>
          </section>
        )}

        {/* Ranked Grid #4-20 */}
        {!loading && grid.length > 0 && (
          <section className="leaderboard-grid-section">
            <h2 className="leaderboard-section-title">Rankings</h2>
            <div className="leaderboard-grid">
              {grid.map((speaker, index) => (
                <LeaderboardCard
                  key={speaker.objectID}
                  speaker={speaker}
                  position={index + 4}
                  onClick={() => setSelectedSpeaker(speaker)}
                />
              ))}
            </div>
          </section>
        )}

        {/* Loading state */}
        {loading && (
          <div className="leaderboard-loading">
            <div className="loading-spinner" />
            <p>Loading leaderboard...</p>
          </div>
        )}

        {/* Category Carousels */}
        <div className="leaderboard-carousels">
          {/* Rising Stars */}
          {risingStars.length > 0 && (
            <CarouselRow icon="⭐" title="Rising Stars" loading={risingLoading}>
              {risingStars.map((speaker) => (
                <SpeakerCard
                  key={speaker.objectID}
                  speaker={speaker}
                  onClick={() => setSelectedSpeaker(speaker)}
                />
              ))}
            </CarouselRow>
          )}

          {/* Most Prolific */}
          {prolificSpeakers.length > 0 && (
            <CarouselRow icon="🎤" title="Most Prolific">
              {prolificSpeakers.map((speaker) => (
                <SpeakerCard
                  key={speaker.objectID}
                  speaker={speaker}
                  onClick={() => setSelectedSpeaker(speaker)}
                />
              ))}
            </CarouselRow>
          )}

          {/* Most Viewed */}
          {viewedSpeakers.length > 0 && (
            <CarouselRow icon="👁" title="Most Viewed">
              {viewedSpeakers.map((speaker) => (
                <SpeakerCard
                  key={speaker.objectID}
                  speaker={speaker}
                  onClick={() => setSelectedSpeaker(speaker)}
                />
              ))}
            </CarouselRow>
          )}

          {/* Veterans */}
          {veteranSpeakers.length > 0 && (
            <CarouselRow icon="🏅" title="Veterans">
              {veteranSpeakers.map((speaker) => (
                <SpeakerCard
                  key={speaker.objectID}
                  speaker={speaker}
                  onClick={() => setSelectedSpeaker(speaker)}
                />
              ))}
            </CarouselRow>
          )}
        </div>
      </main>

      {/* Speaker Modal */}
      {selectedSpeaker && (
        <SpeakerModal
          speaker={selectedSpeaker}
          onClose={() => setSelectedSpeaker(null)}
        />
      )}
    </div>
  );
}

export default LeaderboardPage;
