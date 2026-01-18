/**
 * Skeleton - Loading placeholder components
 *
 * Netflix-style shimmer animations for cards, carousels, and hero sections.
 */

import './Skeleton.css';

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
}

export function Skeleton({
  className = '',
  width,
  height,
  borderRadius,
}: SkeletonProps) {
  const style: React.CSSProperties = {
    width,
    height,
    borderRadius,
  };

  return <div className={`skeleton ${className}`} style={style} />;
}

// Pre-built skeleton variants
export function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <Skeleton className="skeleton-card-image" height={120} />
      <div className="skeleton-card-content">
        <Skeleton height={16} width="80%" />
        <Skeleton height={12} width="60%" />
        <Skeleton height={12} width="40%" />
      </div>
    </div>
  );
}

export function SkeletonTalkCard() {
  return (
    <div className="skeleton-talk-card">
      <Skeleton className="skeleton-talk-thumbnail" />
      <div className="skeleton-talk-content">
        <Skeleton height={14} width="90%" />
        <Skeleton height={12} width="70%" />
        <div className="skeleton-talk-meta">
          <Skeleton height={10} width={60} />
          <Skeleton height={10} width={40} />
        </div>
      </div>
    </div>
  );
}

export function SkeletonCFPCard() {
  return (
    <div className="skeleton-cfp-card">
      <Skeleton className="skeleton-cfp-header" height={60} />
      <div className="skeleton-cfp-content">
        <Skeleton height={16} width="85%" />
        <Skeleton height={12} width="50%" />
        <div className="skeleton-cfp-footer">
          <Skeleton height={20} width={70} borderRadius={4} />
          <Skeleton height={16} width={40} />
        </div>
      </div>
    </div>
  );
}

export function SkeletonCarouselRow({ count = 6 }: { count?: number }) {
  return (
    <div className="skeleton-carousel-row">
      <div className="skeleton-carousel-header">
        <Skeleton height={20} width={150} />
        <Skeleton height={14} width={60} />
      </div>
      <div className="skeleton-carousel-items">
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonHero() {
  return (
    <div className="skeleton-hero">
      <div className="skeleton-hero-content">
        <Skeleton height={12} width={100} />
        <Skeleton height={32} width="60%" />
        <Skeleton height={16} width="40%" />
        <div className="skeleton-hero-countdown">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={48} width={48} borderRadius={8} />
          ))}
        </div>
        <div className="skeleton-hero-actions">
          <Skeleton height={44} width={140} borderRadius={8} />
          <Skeleton height={44} width={120} borderRadius={8} />
        </div>
      </div>
    </div>
  );
}
