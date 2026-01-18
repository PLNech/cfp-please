/**
 * CarouselRow - Carousel with title, icon, and "See all" link
 *
 * Wraps Carousel with consistent Netflix-style header.
 */

import React from 'react';
import { Carousel } from './Carousel';
import { SkeletonCard } from '../skeletons';

interface CarouselRowProps {
  icon: string;
  title: string;
  children: React.ReactNode;
  onSeeAll?: () => void;
  loading?: boolean;
  className?: string;
}

export function CarouselRow({
  icon,
  title,
  children,
  onSeeAll,
  loading = false,
  className = '',
}: CarouselRowProps) {
  const childCount = React.Children.count(children);

  if (!loading && childCount === 0) {
    return null; // Don't render empty rows
  }

  return (
    <section className={`carousel-row ${className}`}>
      <header className="carousel-row-header">
        <h2 className="carousel-row-title">
          <span className="carousel-row-icon">{icon}</span>
          {title}
        </h2>
        {onSeeAll && childCount > 0 && (
          <button className="carousel-row-see-all" onClick={onSeeAll}>
            See all
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </header>

      {loading ? (
        <div className="carousel-loading">
          <div className="carousel-track">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      ) : (
        <Carousel>{children}</Carousel>
      )}
    </section>
  );
}
