import { useState } from 'react';
import { liteClient as algoliasearch } from 'algoliasearch/lite';
import { InstantSearch, Configure, useHits, useStats } from 'react-instantsearch';
import { ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY, ALGOLIA_INDEX_NAME } from './config';
import { Chat, CFPMap, Filters } from './components';
import type { CFP } from './types';
import './App.css';

// Initialize Algolia client
const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);

// Wrapper to access hits for the map
function MapWithHits({ onSelect, selectedCfp }: { onSelect: (cfp: CFP) => void; selectedCfp: CFP | null }) {
  const { items } = useHits<CFP>();
  return <CFPMap hits={items} onMarkerClick={onSelect} selectedCfp={selectedCfp} />;
}

// Stats display with personality
function StatsBar() {
  const { nbHits } = useStats();
  const messages = [
    `${nbHits} stages await your brilliance`,
    `${nbHits} opportunities to share your story`,
    `${nbHits} conferences need YOUR voice`,
    `${nbHits} chances to inspire others`,
  ];
  const message = messages[Math.floor(Date.now() / 60000) % messages.length];
  return <span className="stats-bar">{message}</span>;
}

function App() {
  const [selectedCfp, setSelectedCfp] = useState<CFP | null>(null);
  const [viewMode, setViewMode] = useState<'chat' | 'map' | 'split'>('split');
  const [showFilters, setShowFilters] = useState(false);

  const handleCfpSelect = (cfp: CFP) => {
    setSelectedCfp(cfp);
  };

  return (
    <InstantSearch
      searchClient={searchClient}
      indexName={ALGOLIA_INDEX_NAME}
      future={{ preserveSharedStateOnUnmount: true }}
    >
      {/* Configure default filters: only open CFPs */}
      <Configure
        hitsPerPage={50}
        filters={`cfpEndDate > ${Math.floor(Date.now() / 1000)}`}
        getRankingInfo
      />

      <div className="app">
        <header className="app-header">
          <div className="app-brand">
            <h1 className="app-title">
              <span className="app-title-icon">🎤</span>
              <span className="app-title-text">CFP, Please!</span>
            </h1>
            <p className="app-tagline">Your next stage is calling</p>
          </div>

          <div className="app-header-center">
            <StatsBar />
          </div>

          <div className="app-header-actions">
            <button
              className="filter-toggle-btn"
              onClick={() => setShowFilters(!showFilters)}
              aria-label="Toggle filters"
            >
              <span>⚡</span>
              <span className="filter-toggle-text">Filter</span>
            </button>

            <div className="view-toggle">
              <button
                className={`view-btn ${viewMode === 'chat' ? 'active' : ''}`}
                onClick={() => setViewMode('chat')}
                title="Chat with AI"
              >
                💬
              </button>
              <button
                className={`view-btn ${viewMode === 'split' ? 'active' : ''}`}
                onClick={() => setViewMode('split')}
                title="Split view"
              >
                ⚡
              </button>
              <button
                className={`view-btn ${viewMode === 'map' ? 'active' : ''}`}
                onClick={() => setViewMode('map')}
                title="World map"
              >
                🌍
              </button>
            </div>
          </div>
        </header>

        <main className={`app-main view-${viewMode}`}>
          {/* Filters sidebar */}
          <div className={`filters-wrapper ${showFilters ? 'filters-visible' : ''}`}>
            <Filters />
          </div>

          {/* Chat panel */}
          {(viewMode === 'chat' || viewMode === 'split') && (
            <div className="chat-panel">
              <Chat onCfpSelect={handleCfpSelect} />
            </div>
          )}

          {/* Map panel */}
          {(viewMode === 'map' || viewMode === 'split') && (
            <div className="map-panel">
              <MapWithHits onSelect={handleCfpSelect} selectedCfp={selectedCfp} />
            </div>
          )}
        </main>

        {/* Mobile bottom nav */}
        <nav className="mobile-nav">
          <button
            className={`mobile-nav-btn ${viewMode === 'chat' ? 'active' : ''}`}
            onClick={() => setViewMode('chat')}
          >
            <span className="mobile-nav-icon">💬</span>
            <span className="mobile-nav-label">Discover</span>
          </button>
          <button
            className={`mobile-nav-btn ${viewMode === 'map' ? 'active' : ''}`}
            onClick={() => setViewMode('map')}
          >
            <span className="mobile-nav-icon">🌍</span>
            <span className="mobile-nav-label">Explore</span>
          </button>
          <button
            className={`mobile-nav-btn ${showFilters ? 'active' : ''}`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <span className="mobile-nav-icon">⚡</span>
            <span className="mobile-nav-label">Filter</span>
          </button>
        </nav>

        {/* Selected CFP detail modal */}
        {selectedCfp && (
          <div className="cfp-detail-overlay" onClick={() => setSelectedCfp(null)}>
            <div className="cfp-detail" onClick={(e) => e.stopPropagation()}>
              <button className="cfp-detail-close" onClick={() => setSelectedCfp(null)}>
                ✕
              </button>

              {/* Urgency banner */}
              {selectedCfp.daysUntilCfpClose !== undefined && selectedCfp.daysUntilCfpClose <= 7 && (
                <div className="cfp-detail-urgency">
                  🔥 {selectedCfp.daysUntilCfpClose === 0
                    ? "Last day to submit!"
                    : selectedCfp.daysUntilCfpClose === 1
                    ? "1 day left - go go go!"
                    : `${selectedCfp.daysUntilCfpClose} days left`}
                </div>
              )}

              <h2 className="cfp-detail-title">{selectedCfp.name}</h2>

              {selectedCfp.description && (
                <p className="cfp-detail-desc">{selectedCfp.description}</p>
              )}

              <div className="cfp-detail-grid">
                <div className="cfp-detail-item">
                  <span className="cfp-detail-icon">📍</span>
                  <div>
                    <div className="cfp-detail-label">Location</div>
                    <div className="cfp-detail-value">
                      {[selectedCfp.location?.city, selectedCfp.location?.country]
                        .filter(Boolean)
                        .join(', ') || 'Location TBD'}
                    </div>
                  </div>
                </div>

                {selectedCfp.cfpEndDateISO && (
                  <div className="cfp-detail-item">
                    <span className="cfp-detail-icon">⏰</span>
                    <div>
                      <div className="cfp-detail-label">CFP Deadline</div>
                      <div className="cfp-detail-value">
                        {new Date(selectedCfp.cfpEndDateISO).toLocaleDateString('en-US', {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {selectedCfp.eventStartDateISO && (
                  <div className="cfp-detail-item">
                    <span className="cfp-detail-icon">📅</span>
                    <div>
                      <div className="cfp-detail-label">Event Date</div>
                      <div className="cfp-detail-value">
                        {new Date(selectedCfp.eventStartDateISO).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {selectedCfp.topicsNormalized?.length > 0 && (
                <div className="cfp-detail-topics">
                  {selectedCfp.topicsNormalized.map((topic) => (
                    <span key={topic} className="topic-tag">
                      {topic}
                    </span>
                  ))}
                </div>
              )}

              <div className="cfp-detail-actions">
                {selectedCfp.cfpUrl && (
                  <a
                    href={selectedCfp.cfpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary btn-lg"
                  >
                    🚀 Submit Your Talk
                  </a>
                )}
                {selectedCfp.url && (
                  <a
                    href={selectedCfp.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary"
                  >
                    Learn More
                  </a>
                )}
              </div>

              <p className="cfp-detail-encouragement">
                You've got something valuable to share. Go for it! 💪
              </p>
            </div>
          </div>
        )}
      </div>
    </InstantSearch>
  );
}

export default App;
