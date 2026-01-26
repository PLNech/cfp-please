/**
 * SearchPage - Multi-index search with CFPs, Talks, and Speakers
 *
 * Full InstantSearch experience with same header as TalkFlixHome.
 * URL-synced search query across all indexes.
 */

import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { liteClient as algoliasearch } from 'algoliasearch/lite';
import { InstantSearch, useHits, useSearchBox, useConfigure, useRefinementList, useInstantSearch } from 'react-instantsearch';
import {
  ALGOLIA_APP_ID,
  ALGOLIA_SEARCH_KEY,
  ALGOLIA_INDEX_NAME,
  ALGOLIA_TALKS_INDEX,
  ALGOLIA_SPEAKERS_INDEX,
} from '../../config';
import type { CFP, Talk, Speaker } from '../../types';
import { useProfile } from '../../hooks/useProfile';
import { useInsights } from '../../hooks/useInsights';
import './SearchPage.css';

const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);

type ResultType = 'all' | 'cfps' | 'talks' | 'speakers';

interface SearchPageProps {
  onCFPClick?: (cfp: CFP) => void;
  onTalkClick?: (talk: Talk) => void;
  onSpeakerClick?: (speaker: Speaker) => void;
}

export function SearchPage({ onCFPClick, onTalkClick, onSpeakerClick }: SearchPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [query, setQuery] = useState(initialQuery);
  const [activeTab, setActiveTab] = useState<ResultType>('all');
  const navigate = useNavigate();
  const { profile, openProfile, isFavoriteTalk, toggleFavoriteTalk, markTalkWatched } = useProfile();
  const { clickCFP, clickTalk } = useInsights();
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Ctrl+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Auto-focus on desktop
  useEffect(() => {
    if (window.innerWidth >= 1024) {
      searchInputRef.current?.focus();
    }
  }, []);

  // Sync query with URL
  useEffect(() => {
    const urlQuery = searchParams.get('q') || '';
    if (urlQuery !== query) {
      setQuery(urlQuery);
    }
  }, [searchParams]);

  // Update URL when query changes (debounced)
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (query !== (searchParams.get('q') || '')) {
        setSearchParams(query ? { q: query } : {}, { replace: true });
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [query, searchParams, setSearchParams]);

  const handleBack = () => {
    navigate('/');
  };

  const handleQueryChange = (newQuery: string) => {
    setQuery(newQuery);
  };

  // Track CFP click with position and queryID for click analytics
  const handleCFPClick = useCallback((cfp: CFP, position: number, queryID?: string) => {
    clickCFP(cfp.objectID, position, queryID);
    onCFPClick?.(cfp);
  }, [clickCFP, onCFPClick]);

  // Track Talk click with position and queryID for click analytics
  const handleTalkClick = useCallback((talk: Talk, position: number, queryID?: string) => {
    clickTalk(talk.objectID, position, queryID);
    markTalkWatched(talk.objectID);
    onTalkClick?.(talk);
  }, [clickTalk, markTalkWatched, onTalkClick]);

  return (
    <div className="search-page">
      {/* Same header as TalkFlixHome */}
      <header className="talkflix-header">
        <button className="search-page-back-btn" onClick={handleBack} aria-label="Go back">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>

        <div className="talkflix-logo" onClick={handleBack} style={{ cursor: 'pointer' }}>
          <span className="talkflix-logo-icon">🎤</span>
          <span className="talkflix-logo-text">TalkFlix</span>
        </div>

        {/* Search input - synced with URL */}
        <div className="search-page-searchbar">
          <svg className="search-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={searchInputRef}
            type="search"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Search CFPs, talks, speakers..."
            className="search-page-input"
          />
          {query && (
            <button className="search-clear-btn" onClick={() => handleQueryChange('')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}
        </div>

        {/* Profile button */}
        <button className="talkflix-profile-btn" onClick={openProfile}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          {profile.topics.length > 0 && <span className="profile-badge">{profile.topics.length}</span>}
        </button>
      </header>

      {/* Tabs for filtering result type */}
      <div className="search-tabs">
        {(['all', 'cfps', 'talks', 'speakers'] as ResultType[]).map((tab) => (
          <button
            key={tab}
            className={`search-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'all' && 'All'}
            {tab === 'cfps' && 'CFPs'}
            {tab === 'talks' && 'Talks'}
            {tab === 'speakers' && 'Speakers'}
          </button>
        ))}
      </div>

      {/* Multi-index search */}
      <div className="search-content">
        {(activeTab === 'all' || activeTab === 'cfps') && (
          <InstantSearch searchClient={searchClient} indexName={ALGOLIA_INDEX_NAME}>
            <CFPSearchSection
              query={query}
              showTitle={activeTab === 'all'}
              onCFPClick={handleCFPClick}
            />
          </InstantSearch>
        )}

        {(activeTab === 'all' || activeTab === 'talks') && (
          <InstantSearch searchClient={searchClient} indexName={ALGOLIA_TALKS_INDEX}>
            <TalkSearchSection
              query={query}
              showTitle={activeTab === 'all'}
              onTalkClick={handleTalkClick}
              isFavorite={isFavoriteTalk}
              onToggleFavorite={toggleFavoriteTalk}
            />
          </InstantSearch>
        )}

        {(activeTab === 'all' || activeTab === 'speakers') && (
          <InstantSearch searchClient={searchClient} indexName={ALGOLIA_SPEAKERS_INDEX}>
            <SpeakerSearchSection
              query={query}
              showTitle={activeTab === 'all'}
              onSpeakerClick={onSpeakerClick}
            />
          </InstantSearch>
        )}
      </div>
    </div>
  );
}

// ========== CFP Section ==========
interface CFPSearchSectionProps {
  query: string;
  showTitle: boolean;
  onCFPClick?: (cfp: CFP, position: number, queryID?: string) => void;
}

function CFPSearchSection({ query: externalQuery, showTitle, onCFPClick }: CFPSearchSectionProps) {
  useConfigure({
    hitsPerPage: showTitle ? 24 : 20, // Fetch enough for carousel pages
    clickAnalytics: true,
  });
  const { refine } = useSearchBox();
  const { items: hits } = useHits<CFP>();
  const { results } = useInstantSearch();
  const queryID = results?.queryID;
  const totalHits = results?.nbHits ?? 0;

  // Sync external query with InstantSearch
  useEffect(() => {
    refine(externalQuery);
  }, [externalQuery, refine]);

  const handleClick = useCallback((cfp: CFP, position: number) => {
    onCFPClick?.(cfp, position, queryID);
  }, [onCFPClick, queryID]);

  // Folded empty state for "all" tab
  if (showTitle && totalHits === 0) {
    return (
      <section className="search-section search-section-empty">
        <h2 className="search-section-title search-section-title-empty">CFPs (0)</h2>
      </section>
    );
  }

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">CFPs ({totalHits})</h2>}
      {!showTitle && <CFPFacets />}

      {hits.length === 0 ? (
        <p className="search-no-results">No CFPs found matching your search</p>
      ) : showTitle ? (
        <CarouselResults totalHits={Math.min(totalHits, hits.length)} itemWidth={300}>
          {hits.map((cfp, index) => (
            <CFPResultCard
              key={cfp.objectID}
              cfp={cfp}
              onClick={() => handleClick(cfp, index + 1)}
            />
          ))}
        </CarouselResults>
      ) : (
        <div className="search-results search-results-grid">
          {hits.map((cfp, index) => (
            <CFPResultCard
              key={cfp.objectID}
              cfp={cfp}
              onClick={() => handleClick(cfp, index + 1)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function CFPFacets() {
  const { items, refine } = useRefinementList({ attribute: 'topicsNormalized', limit: 10 });

  if (items.length === 0) return null;

  return (
    <div className="search-facets">
      <span className="search-facets-label">Topics:</span>
      {items.slice(0, 6).map((item) => (
        <button
          key={item.value}
          className={`search-facet ${item.isRefined ? 'active' : ''}`}
          onClick={() => refine(item.value)}
        >
          {item.label} ({item.count})
        </button>
      ))}
    </div>
  );
}

function CFPResultCard({ cfp, onClick }: { cfp: CFP; onClick: () => void }) {
  // Truncate description to ~80 chars for card display
  const truncateDesc = (desc?: string, maxLen = 80) => {
    if (!desc) return null;
    return desc.length > maxLen ? desc.slice(0, maxLen).trim() + '...' : desc;
  };

  return (
    <article className="search-result-card" onClick={onClick}>
      <div className="search-result-badge cfp-badge">CFP</div>
      <h3 className="search-result-title">{cfp.name}</h3>
      {cfp.description && (
        <p className="search-result-description">{truncateDesc(cfp.description)}</p>
      )}
      <p className="search-result-meta">
        {cfp.location?.city && <span>{cfp.location.city}</span>}
        {cfp.daysUntilCfpClose !== undefined && cfp.daysUntilCfpClose >= 0 && (
          <span className={`deadline ${cfp.daysUntilCfpClose <= 7 ? 'urgent' : ''}`}>
            {cfp.daysUntilCfpClose === 0 ? 'Last day!' : `${cfp.daysUntilCfpClose}d left`}
          </span>
        )}
      </p>
      {cfp.topicsNormalized?.length > 0 && (
        <div className="search-result-tags">
          {cfp.topicsNormalized.slice(0, 3).map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>
      )}
    </article>
  );
}

// ========== Talk Section ==========
interface TalkSearchSectionProps {
  query: string;
  showTitle: boolean;
  onTalkClick?: (talk: Talk, position: number, queryID?: string) => void;
  isFavorite: (id: string) => boolean;
  onToggleFavorite: (id: string) => void;
}

function TalkSearchSection({ query: externalQuery, showTitle, onTalkClick, isFavorite, onToggleFavorite }: TalkSearchSectionProps) {
  useConfigure({
    hitsPerPage: showTitle ? 24 : 20, // Fetch enough for carousel pages
    clickAnalytics: true,
  });
  const { refine } = useSearchBox();
  const { items: hits } = useHits<Talk>();
  const { results } = useInstantSearch();
  const queryID = results?.queryID;
  const totalHits = results?.nbHits ?? 0;

  // Sync external query with InstantSearch
  useEffect(() => {
    refine(externalQuery);
  }, [externalQuery, refine]);

  const handleClick = useCallback((talk: Talk, position: number) => {
    onTalkClick?.(talk, position, queryID);
  }, [onTalkClick, queryID]);

  // Folded empty state for "all" tab
  if (showTitle && totalHits === 0) {
    return (
      <section className="search-section search-section-empty">
        <h2 className="search-section-title search-section-title-empty">Talks (0)</h2>
      </section>
    );
  }

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">Talks ({totalHits})</h2>}

      {hits.length === 0 ? (
        <p className="search-no-results">No talks found matching your search</p>
      ) : showTitle ? (
        <CarouselResults totalHits={Math.min(totalHits, hits.length)} itemWidth={300}>
          {hits.map((talk, index) => (
            <TalkResultCard
              key={talk.objectID}
              talk={talk}
              isFavorite={isFavorite(talk.objectID)}
              onClick={() => handleClick(talk, index + 1)}
              onToggleFavorite={() => onToggleFavorite(talk.objectID)}
            />
          ))}
        </CarouselResults>
      ) : (
        <div className="search-results search-results-grid">
          {hits.map((talk, index) => (
            <TalkResultCard
              key={talk.objectID}
              talk={talk}
              isFavorite={isFavorite(talk.objectID)}
              onClick={() => handleClick(talk, index + 1)}
              onToggleFavorite={() => onToggleFavorite(talk.objectID)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function TalkResultCard({
  talk,
  isFavorite,
  onClick,
  onToggleFavorite,
}: {
  talk: Talk;
  isFavorite: boolean;
  onClick: () => void;
  onToggleFavorite: () => void;
}) {
  const views = talk.view_count
    ? talk.view_count >= 1000000
      ? `${(talk.view_count / 1000000).toFixed(1)}M`
      : talk.view_count >= 1000
      ? `${Math.floor(talk.view_count / 1000)}K`
      : talk.view_count.toString()
    : null;

  return (
    <article className="search-result-card talk-result" onClick={onClick}>
      <div className="search-result-badge talk-badge">Talk</div>
      {talk.thumbnail_url && (
        <img src={talk.thumbnail_url} alt="" className="talk-result-thumb" loading="lazy" />
      )}
      <div className="talk-result-content">
        <h3 className="search-result-title">{talk.title}</h3>
        <p className="search-result-meta">
          {talk.speaker && <span>{talk.speaker}</span>}
          {talk.conference_name && <span>{talk.conference_name}</span>}
          {views && <span>{views} views</span>}
        </p>
      </div>
      <button
        className={`result-favorite ${isFavorite ? 'active' : ''}`}
        onClick={(e) => {
          e.stopPropagation();
          onToggleFavorite();
        }}
        aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill={isFavorite ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
        </svg>
      </button>
    </article>
  );
}

// ========== Speaker Section ==========
interface SpeakerSearchSectionProps {
  query: string;
  showTitle: boolean;
  onSpeakerClick?: (speaker: Speaker) => void;
}

function SpeakerSearchSection({ query: externalQuery, showTitle, onSpeakerClick }: SpeakerSearchSectionProps) {
  useConfigure({ hitsPerPage: showTitle ? 24 : 20 }); // Fetch enough for carousel pages
  const { refine } = useSearchBox();
  const { items: hits } = useHits<Speaker>();
  const { results } = useInstantSearch();
  const totalHits = results?.nbHits ?? 0;

  // Sync external query with InstantSearch
  useEffect(() => {
    refine(externalQuery);
  }, [externalQuery, refine]);

  // Folded empty state for "all" tab
  if (showTitle && totalHits === 0) {
    return (
      <section className="search-section search-section-empty">
        <h2 className="search-section-title search-section-title-empty">Speakers (0)</h2>
      </section>
    );
  }

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">Speakers ({totalHits})</h2>}

      {hits.length === 0 ? (
        <p className="search-no-results">No speakers found matching your search</p>
      ) : showTitle ? (
        <CarouselResults totalHits={Math.min(totalHits, hits.length)} itemWidth={220}>
          {hits.map((speaker) => (
            <SpeakerResultCard
              key={speaker.objectID}
              speaker={speaker}
              onClick={() => onSpeakerClick?.(speaker)}
            />
          ))}
        </CarouselResults>
      ) : (
        <div className="search-results search-results-grid speakers-grid">
          {hits.map((speaker) => (
            <SpeakerResultCard
              key={speaker.objectID}
              speaker={speaker}
              onClick={() => onSpeakerClick?.(speaker)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SpeakerResultCard({ speaker, onClick }: { speaker: Speaker; onClick: () => void }) {
  const initials = speaker.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const formatViews = (views: number) => {
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`;
    if (views >= 1000) return `${Math.floor(views / 1000)}K`;
    return views.toString();
  };

  // Gravatar fallback using name hash (deterministic color)
  const gravatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(speaker.name)}&background=random&color=fff&size=100`;

  return (
    <article className="search-result-card speaker-result" onClick={onClick}>
      <div className="search-result-badge speaker-badge">Speaker</div>
      {speaker.image_url ? (
        <img
          src={speaker.image_url}
          alt={speaker.name}
          className="speaker-avatar speaker-avatar-img"
          loading="lazy"
        />
      ) : (
        <div
          className="speaker-avatar speaker-avatar-fallback"
          style={{ backgroundImage: `url(${gravatarUrl})` }}
        >
          {initials}
        </div>
      )}
      <h3 className="search-result-title">{speaker.name}</h3>
      {speaker.tagline && <p className="speaker-tagline">{speaker.tagline}</p>}
      {!speaker.tagline && speaker.company && <p className="speaker-company">{speaker.company}</p>}
      <p className="search-result-meta">
        <span title="Talks">{speaker.talk_count} talks</span>
        <span title="Views">{formatViews(speaker.total_views)} views</span>
      </p>
      {speaker.achievements?.length > 0 && (
        <div className="speaker-achievements">
          {speaker.achievements.slice(0, 2).map((a) => (
            <span key={a} className="achievement-badge">{a}</span>
          ))}
        </div>
      )}
    </article>
  );
}

// ========== Carousel Component ==========
interface CarouselResultsProps {
  children: ReactNode[];
  itemWidth?: number;
  totalHits: number;
}

function CarouselResults({ children, itemWidth = 300, totalHits }: CarouselResultsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 6;
  const totalPages = Math.ceil(totalHits / itemsPerPage);
  const gap = 16; // var(--space-4)

  const scrollToPage = (page: number) => {
    if (!scrollRef.current) return;
    const scrollAmount = page * (itemWidth + gap) * itemsPerPage;
    scrollRef.current.scrollTo({ left: scrollAmount, behavior: 'smooth' });
    setCurrentPage(page);
  };

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const scrollLeft = scrollRef.current.scrollLeft;
    const pageWidth = (itemWidth + gap) * itemsPerPage;
    const newPage = Math.round(scrollLeft / pageWidth);
    if (newPage !== currentPage) {
      setCurrentPage(newPage);
    }
  };

  const canGoPrev = currentPage > 0;
  const canGoNext = currentPage < totalPages - 1;

  return (
    <div className="search-results-wrapper">
      <button
        className="carousel-nav carousel-prev"
        onClick={() => scrollToPage(currentPage - 1)}
        disabled={!canGoPrev}
        aria-label="Previous page"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      <div
        ref={scrollRef}
        className="search-results"
        onScroll={handleScroll}
      >
        {children}
      </div>

      <button
        className="carousel-nav carousel-next"
        onClick={() => scrollToPage(currentPage + 1)}
        disabled={!canGoNext}
        aria-label="Next page"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      {totalPages > 1 && (
        <div className="carousel-pagination">
          {Array.from({ length: totalPages }).map((_, i) => (
            <button
              key={i}
              className={`carousel-dot ${i === currentPage ? 'active' : ''}`}
              onClick={() => scrollToPage(i)}
              aria-label={`Go to page ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Search input moved to header - unified search bar across page
