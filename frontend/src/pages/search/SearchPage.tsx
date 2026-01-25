/**
 * SearchPage - Multi-index search with CFPs, Talks, and Speakers
 *
 * Full InstantSearch experience as a separate route.
 */

import { useState, useMemo, useCallback } from 'react';
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
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [activeTab, setActiveTab] = useState<ResultType>('all');
  const navigate = useNavigate();
  const { isFavoriteTalk, toggleFavoriteTalk, markTalkWatched } = useProfile();
  const { clickCFP, clickTalk } = useInsights();

  const handleBack = () => {
    navigate('/');
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
      <header className="search-page-header">
        <button className="search-page-back" onClick={handleBack} aria-label="Go back">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h1 className="search-page-title">Search</h1>
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
              initialQuery={initialQuery}
              showTitle={activeTab === 'all'}
              onCFPClick={handleCFPClick}
            />
          </InstantSearch>
        )}

        {(activeTab === 'all' || activeTab === 'talks') && (
          <InstantSearch searchClient={searchClient} indexName={ALGOLIA_TALKS_INDEX}>
            <TalkSearchSection
              initialQuery={initialQuery}
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
              initialQuery={initialQuery}
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
  initialQuery: string;
  showTitle: boolean;
  onCFPClick?: (cfp: CFP, position: number, queryID?: string) => void;
}

function CFPSearchSection({ initialQuery, showTitle, onCFPClick }: CFPSearchSectionProps) {
  useConfigure({
    hitsPerPage: showTitle ? 6 : 20,
    clickAnalytics: true, // Enable queryID in response
  });
  const { query, refine } = useSearchBox();
  const { items: hits } = useHits<CFP>();
  const { results } = useInstantSearch();
  const queryID = results?.queryID;

  // Set initial query on mount
  useMemo(() => {
    if (initialQuery && query !== initialQuery) {
      refine(initialQuery);
    }
  }, [initialQuery]);

  const handleClick = useCallback((cfp: CFP, position: number) => {
    onCFPClick?.(cfp, position, queryID);
  }, [onCFPClick, queryID]);

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">CFPs ({hits.length})</h2>}
      {!showTitle && <SearchInput query={query} refine={refine} placeholder="Search CFPs..." />}
      {!showTitle && <CFPFacets />}

      <div className="search-results">
        {hits.length === 0 ? (
          <p className="search-no-results">No CFPs found</p>
        ) : (
          hits.map((cfp, index) => (
            <CFPResultCard
              key={cfp.objectID}
              cfp={cfp}
              onClick={() => handleClick(cfp, index + 1)}
            />
          ))
        )}
      </div>
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
  initialQuery: string;
  showTitle: boolean;
  onTalkClick?: (talk: Talk, position: number, queryID?: string) => void;
  isFavorite: (id: string) => boolean;
  onToggleFavorite: (id: string) => void;
}

function TalkSearchSection({ initialQuery, showTitle, onTalkClick, isFavorite, onToggleFavorite }: TalkSearchSectionProps) {
  useConfigure({
    hitsPerPage: showTitle ? 6 : 20,
    clickAnalytics: true,
  });
  const { query, refine } = useSearchBox();
  const { items: hits } = useHits<Talk>();
  const { results } = useInstantSearch();
  const queryID = results?.queryID;

  useMemo(() => {
    if (initialQuery && query !== initialQuery) {
      refine(initialQuery);
    }
  }, [initialQuery]);

  const handleClick = useCallback((talk: Talk, position: number) => {
    onTalkClick?.(talk, position, queryID);
  }, [onTalkClick, queryID]);

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">Talks ({hits.length})</h2>}
      {!showTitle && <SearchInput query={query} refine={refine} placeholder="Search talks..." />}

      <div className="search-results">
        {hits.length === 0 ? (
          <p className="search-no-results">No talks found</p>
        ) : (
          hits.map((talk, index) => (
            <TalkResultCard
              key={talk.objectID}
              talk={talk}
              isFavorite={isFavorite(talk.objectID)}
              onClick={() => handleClick(talk, index + 1)}
              onToggleFavorite={() => onToggleFavorite(talk.objectID)}
            />
          ))
        )}
      </div>
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
  initialQuery: string;
  showTitle: boolean;
  onSpeakerClick?: (speaker: Speaker) => void;
}

function SpeakerSearchSection({ initialQuery, showTitle, onSpeakerClick }: SpeakerSearchSectionProps) {
  useConfigure({ hitsPerPage: showTitle ? 6 : 20 });
  const { query, refine } = useSearchBox();
  const { items: hits } = useHits<Speaker>();

  useMemo(() => {
    if (initialQuery && query !== initialQuery) {
      refine(initialQuery);
    }
  }, [initialQuery]);

  return (
    <section className="search-section">
      {showTitle && <h2 className="search-section-title">Speakers ({hits.length})</h2>}
      {!showTitle && <SearchInput query={query} refine={refine} placeholder="Search speakers..." />}

      <div className="search-results speakers-grid">
        {hits.length === 0 ? (
          <p className="search-no-results">No speakers found</p>
        ) : (
          hits.map((speaker) => (
            <SpeakerResultCard
              key={speaker.objectID}
              speaker={speaker}
              onClick={() => onSpeakerClick?.(speaker)}
            />
          ))
        )}
      </div>
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

  return (
    <article className="search-result-card speaker-result" onClick={onClick}>
      <div className="search-result-badge speaker-badge">Speaker</div>
      <div className="speaker-avatar">{initials}</div>
      <h3 className="search-result-title">{speaker.name}</h3>
      {speaker.company && <p className="speaker-company">{speaker.company}</p>}
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

// ========== Shared Components ==========
function SearchInput({
  query,
  refine,
  placeholder,
}: {
  query: string;
  refine: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className="search-input-wrapper">
      <svg className="search-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        type="search"
        value={query}
        onChange={(e) => refine(e.target.value)}
        placeholder={placeholder}
        className="search-input"
        autoFocus
      />
    </div>
  );
}
