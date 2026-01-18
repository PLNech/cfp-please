import { useState } from 'react';
import { TalkFlixHome } from './pages/TalkFlixHome';
import type { CFP, Talk } from './types';
import './App.css';

function App() {
  const [selectedCfp, setSelectedCfp] = useState<CFP | null>(null);

  const handleCfpClick = (cfp: CFP) => {
    setSelectedCfp(cfp);
  };

  const handleTalkClick = (talk: Talk) => {
    // Open YouTube video in new tab
    window.open(talk.url, '_blank', 'noopener');
  };

  return (
    <>
      <TalkFlixHome
        onCFPClick={handleCfpClick}
        onTalkClick={handleTalkClick}
      />

      {/* CFP Detail Modal */}
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

    </>
  );
}

export default App;
