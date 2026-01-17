import { useState } from 'react';
import { liteClient as algoliasearch } from 'algoliasearch/lite';
import { InstantSearch, Configure, useHits } from 'react-instantsearch';
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

function App() {
  const [selectedCfp, setSelectedCfp] = useState<CFP | null>(null);
  const [viewMode, setViewMode] = useState<'chat' | 'map' | 'split'>('split');

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
          <h1 className="app-title">
            <span className="app-title-icon">📣</span>
            CFP Finder
          </h1>
          <p className="app-subtitle">Find your next speaking opportunity</p>

          <div className="view-toggle">
            <button
              className={`view-btn ${viewMode === 'chat' ? 'active' : ''}`}
              onClick={() => setViewMode('chat')}
            >
              Chat
            </button>
            <button
              className={`view-btn ${viewMode === 'split' ? 'active' : ''}`}
              onClick={() => setViewMode('split')}
            >
              Split
            </button>
            <button
              className={`view-btn ${viewMode === 'map' ? 'active' : ''}`}
              onClick={() => setViewMode('map')}
            >
              Map
            </button>
          </div>
        </header>

        <main className={`app-main view-${viewMode}`}>
          {/* Filters sidebar */}
          <Filters />

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

        {/* Selected CFP detail modal */}
        {selectedCfp && (
          <div className="cfp-detail-overlay" onClick={() => setSelectedCfp(null)}>
            <div className="cfp-detail" onClick={(e) => e.stopPropagation()}>
              <button className="cfp-detail-close" onClick={() => setSelectedCfp(null)}>
                &times;
              </button>
              <h2>{selectedCfp.name}</h2>
              {selectedCfp.description && <p>{selectedCfp.description}</p>}
              <div className="cfp-detail-meta">
                <p>
                  <strong>Location:</strong>{' '}
                  {[selectedCfp.location?.city, selectedCfp.location?.country]
                    .filter(Boolean)
                    .join(', ') || 'TBD'}
                </p>
                {selectedCfp.cfpEndDateISO && (
                  <p>
                    <strong>CFP Closes:</strong>{' '}
                    {new Date(selectedCfp.cfpEndDateISO).toLocaleDateString()}
                  </p>
                )}
                {selectedCfp.eventStartDateISO && (
                  <p>
                    <strong>Event Date:</strong>{' '}
                    {new Date(selectedCfp.eventStartDateISO).toLocaleDateString()}
                  </p>
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
                    className="btn btn-primary"
                  >
                    Submit Talk
                  </a>
                )}
                {selectedCfp.url && (
                  <a
                    href={selectedCfp.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary"
                  >
                    Visit Event Site
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </InstantSearch>
  );
}

export default App;
