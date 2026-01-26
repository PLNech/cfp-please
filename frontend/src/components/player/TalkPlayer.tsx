/**
 * TalkPlayer - Privacy-minded YouTube embed player
 *
 * Uses youtube-nocookie.com for reduced tracking.
 * Click-to-load: shows thumbnail until user explicitly plays.
 */

import { useState, useEffect } from 'react';
import type { Talk } from '../../types';
import './TalkPlayer.css';

interface TalkPlayerProps {
  talk: Talk;
  isOpen: boolean;
  onClose: () => void;
  onTrackWatch?: (talkId: string) => void;
  onSpeakerClick?: (speakerName: string) => void;
  onConferenceClick?: (conferenceName: string) => void;
}

// Extract video ID from objectID or URL
function getVideoId(talk: Talk): string | null {
  if (talk.objectID.startsWith('yt_')) {
    return talk.objectID.slice(3);
  }
  // Try to extract from URL
  const match = talk.url?.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)/);
  return match?.[1] || null;
}

// Generate thumbnail URL
function getThumbnailUrl(videoId: string): string {
  return `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
}

export function TalkPlayer({ talk, isOpen, onClose, onTrackWatch, onSpeakerClick, onConferenceClick }: TalkPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const videoId = getVideoId(talk);

  if (!isOpen || !videoId) return null;

  const handlePlay = () => {
    setIsPlaying(true);
    onTrackWatch?.(talk.objectID);
  };

  const handleClose = () => {
    setIsPlaying(false);
    onClose();
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  // Escape key closes player
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="talk-player-overlay" onClick={handleBackdropClick}>
      <div className="talk-player-modal">
        {/* Close button */}
        <button className="talk-player-close" onClick={handleClose} aria-label="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* Video container */}
        <div className="talk-player-video">
          {isPlaying ? (
            // Privacy-enhanced embed (youtube-nocookie.com)
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`}
              title={talk.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : (
            // Click-to-load thumbnail
            <div className="talk-player-poster" onClick={handlePlay}>
              <img
                src={getThumbnailUrl(videoId)}
                alt={talk.title}
                onError={(e) => {
                  // Fallback to lower quality if maxres not available
                  (e.target as HTMLImageElement).src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                }}
              />
              <div className="talk-player-play-btn">
                <svg width="68" height="48" viewBox="0 0 68 48">
                  <path
                    d="M66.52 7.74c-.78-2.93-2.49-5.41-5.42-6.19C55.79.13 34 0 34 0S12.21.13 6.9 1.55c-2.93.78-4.63 3.26-5.42 6.19C.06 13.05 0 24 0 24s.06 10.95 1.48 16.26c.78 2.93 2.49 5.41 5.42 6.19C12.21 47.87 34 48 34 48s21.79-.13 27.1-1.55c2.93-.78 4.64-3.26 5.42-6.19C67.94 34.95 68 24 68 24s-.06-10.95-1.48-16.26z"
                    fill="#f00"
                  />
                  <path d="M45 24L27 14v20" fill="#fff" />
                </svg>
              </div>
              <div className="talk-player-privacy-notice">
                Click to load from YouTube
              </div>
            </div>
          )}
        </div>

        {/* Talk info */}
        <div className="talk-player-info">
          <h2 className="talk-player-title">{talk.title}</h2>
          <p className="talk-player-meta">
            {talk.speaker && (
              <button
                className="talk-player-speaker clickable"
                onClick={(e) => {
                  e.stopPropagation();
                  onSpeakerClick?.(talk.speaker!);
                  handleClose();
                }}
              >
                {talk.speaker}
              </button>
            )}
            {talk.speaker && talk.conference_name && ' • '}
            {talk.conference_name && (
              <button
                className="talk-player-conference clickable"
                onClick={(e) => {
                  e.stopPropagation();
                  // Strip years from conference name (e.g., "Agile Lyon 2026 (2024)" -> "Agile Lyon")
                  const cleanConf = talk.conference_name!.replace(/\s*\(?(?:19|20)\d{2}(?:\))?/g, '').trim();
                  console.log('[TalkPlayer] Conference clicked:', talk.conference_name, '->', cleanConf);
                  onConferenceClick?.(cleanConf);
                  handleClose();
                }}
              >
                {talk.conference_name}
              </button>
            )}
            {talk.year && <span className="talk-player-year"> ({talk.year})</span>}
          </p>
          {talk.view_count && (
            <p className="talk-player-views">
              {talk.view_count.toLocaleString()} views
            </p>
          )}

          {/* Transcript summary if available */}
          {talk.transcript_summary && (
            <div className="talk-player-summary">
              <h3>Summary</h3>
              <p>{talk.transcript_summary}</p>
            </div>
          )}

          {/* Bangers if available */}
          {talk.transcript_bangers && talk.transcript_bangers.length > 0 && (
            <div className="talk-player-bangers">
              <h3>💥 Quotable Moments</h3>
              <ul>
                {talk.transcript_bangers.slice(0, 3).map((banger, i) => (
                  <li key={i}>"{banger}"</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
