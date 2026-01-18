/**
 * HeroSection - Featured CFP with countdown timer
 *
 * Netflix-style hero showcasing urgent CFP with dramatic countdown.
 */

import { useState, useEffect } from 'react';
import type { CFP } from '../../types';
import { IntelBadges, TrendingIndicator } from '../intel/IntelBadges';

interface HeroSectionProps {
  cfp: CFP | null;
  loading?: boolean;
  onSubmit?: () => void;
  onSeeTalks?: () => void;
}

export function HeroSection({ cfp, loading = false, onSubmit, onSeeTalks }: HeroSectionProps) {
  if (loading) {
    return (
      <section className="hero hero-loading">
        <div className="hero-skeleton">
          <div className="hero-skeleton-title" />
          <div className="hero-skeleton-countdown" />
          <div className="hero-skeleton-buttons" />
        </div>
      </section>
    );
  }

  if (!cfp) {
    return null;
  }

  return (
    <section className="hero">
      <div className="hero-bg">
        {/* Gradient or image background */}
        <div className="hero-gradient" />
      </div>

      <div className="hero-content">
        <div className="hero-badges">
          <TrendingIndicator popularityScore={cfp.popularityScore} />
          <IntelBadges cfp={cfp} compact />
        </div>

        <h2 className="hero-title">{cfp.name}</h2>

        {cfp.location?.city && (
          <p className="hero-location">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {cfp.location.city}
            {cfp.location.country && `, ${cfp.location.country}`}
          </p>
        )}

        {cfp.cfpEndDate && (
          <HeroCountdown deadline={cfp.cfpEndDate} />
        )}

        <div className="hero-actions">
          <button className="hero-btn hero-btn-primary" onClick={onSubmit}>
            Submit Now
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
          <button className="hero-btn hero-btn-secondary" onClick={onSeeTalks}>
            See Talks
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
}

interface HeroCountdownProps {
  deadline: number; // Unix timestamp
}

function HeroCountdown({ deadline }: HeroCountdownProps) {
  const [timeLeft, setTimeLeft] = useState(calculateTimeLeft(deadline));

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft(deadline));
    }, 1000);

    return () => clearInterval(timer);
  }, [deadline]);

  if (timeLeft.total <= 0) {
    return <p className="hero-countdown hero-countdown-closed">CFP Closed</p>;
  }

  const urgency = timeLeft.days <= 3 ? 'critical' : timeLeft.days <= 7 ? 'warning' : 'ok';

  return (
    <div className={`hero-countdown hero-countdown-${urgency}`}>
      <span className="hero-countdown-label">CFP closes in</span>
      <div className="hero-countdown-timer">
        <CountdownUnit value={timeLeft.days} label="days" />
        <span className="hero-countdown-sep">:</span>
        <CountdownUnit value={timeLeft.hours} label="hrs" />
        <span className="hero-countdown-sep">:</span>
        <CountdownUnit value={timeLeft.minutes} label="min" />
        <span className="hero-countdown-sep">:</span>
        <CountdownUnit value={timeLeft.seconds} label="sec" />
      </div>
    </div>
  );
}

function CountdownUnit({ value, label }: { value: number; label: string }) {
  return (
    <div className="hero-countdown-unit">
      <span className="hero-countdown-value">
        {value.toString().padStart(2, '0')}
      </span>
      <span className="hero-countdown-unit-label">{label}</span>
    </div>
  );
}

function calculateTimeLeft(deadline: number) {
  const now = Math.floor(Date.now() / 1000);
  const diff = deadline - now;

  if (diff <= 0) {
    return { total: 0, days: 0, hours: 0, minutes: 0, seconds: 0 };
  }

  return {
    total: diff,
    days: Math.floor(diff / 86400),
    hours: Math.floor((diff % 86400) / 3600),
    minutes: Math.floor((diff % 3600) / 60),
    seconds: diff % 60,
  };
}
