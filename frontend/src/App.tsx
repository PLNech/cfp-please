import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { TalkFlixHome } from './pages/TalkFlixHome';
import { SearchPage } from './pages/search';
import { SpeakerModal } from './components/speakers';
import type { CFP, Talk, Speaker } from './types';
import './App.css';

// Intel section for CFP detail modal
function CFPIntelSection({ cfp }: { cfp: CFP }) {
  const hasIntel = cfp.hnStories || cfp.githubRepos || cfp.redditPosts || cfp.devtoArticles;
  if (!hasIntel) return null;

  return (
    <div className="cfp-detail-intel">
      <h3 className="cfp-detail-section-title">Community Buzz</h3>
      <div className="cfp-detail-intel-grid">
        {cfp.hnStories && cfp.hnStories > 0 && (
          <a
            href={`https://hn.algolia.com/?q=${encodeURIComponent(cfp.name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-detail-intel-card intel-hn"
          >
            <div className="intel-card-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                <path d="M0 0v24h24V0H0zm12.3 12.5v5.2h-1.3v-5.2L7.5 6.3h1.5l2.7 5 2.6-5h1.5l-3.5 6.2z"/>
              </svg>
            </div>
            <div className="intel-card-stats">
              <span className="intel-card-value">{cfp.hnStories}</span>
              <span className="intel-card-label">HN stories</span>
            </div>
            {cfp.hnPoints && <span className="intel-card-extra">{cfp.hnPoints.toLocaleString()} pts</span>}
          </a>
        )}

        {cfp.githubRepos && cfp.githubRepos > 0 && (
          <a
            href={`https://github.com/search?q=${encodeURIComponent(cfp.name)}&type=repositories`}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-detail-intel-card intel-github"
          >
            <div className="intel-card-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </div>
            <div className="intel-card-stats">
              <span className="intel-card-value">{cfp.githubRepos}</span>
              <span className="intel-card-label">repos</span>
            </div>
            {cfp.githubStars && <span className="intel-card-extra">{cfp.githubStars.toLocaleString()} ★</span>}
          </a>
        )}

        {cfp.redditPosts && cfp.redditPosts > 0 && (
          <a
            href={`https://www.reddit.com/search/?q=${encodeURIComponent(cfp.name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-detail-intel-card intel-reddit"
          >
            <div className="intel-card-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
              </svg>
            </div>
            <div className="intel-card-stats">
              <span className="intel-card-value">{cfp.redditPosts}</span>
              <span className="intel-card-label">posts</span>
            </div>
            {cfp.redditSubreddits && cfp.redditSubreddits.length > 0 && (
              <span className="intel-card-extra">r/{cfp.redditSubreddits[0]}</span>
            )}
          </a>
        )}

        {cfp.devtoArticles && cfp.devtoArticles > 0 && (
          <a
            href={`https://dev.to/search?q=${encodeURIComponent(cfp.name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-detail-intel-card intel-devto"
          >
            <div className="intel-card-icon">DEV</div>
            <div className="intel-card-stats">
              <span className="intel-card-value">{cfp.devtoArticles}</span>
              <span className="intel-card-label">articles</span>
            </div>
          </a>
        )}
      </div>

      {cfp.popularityScore && cfp.popularityScore > 0 && (
        <div className="cfp-detail-popularity">
          <span className="popularity-label">Popularity Score</span>
          <div className="popularity-bar">
            <div
              className="popularity-fill"
              style={{ width: `${Math.min(100, cfp.popularityScore)}%` }}
            />
          </div>
          <span className="popularity-value">{cfp.popularityScore.toFixed(0)}/100</span>
        </div>
      )}
    </div>
  );
}

function App() {
  const [selectedCfp, setSelectedCfp] = useState<CFP | null>(null);
  const [selectedSpeaker, setSelectedSpeaker] = useState<Speaker | null>(null);

  const handleCfpClick = (cfp: CFP) => {
    setSelectedCfp(cfp);
  };

  const handleTalkClick = (talk: Talk) => {
    // Open YouTube video in new tab
    window.open(talk.url, '_blank', 'noopener');
  };

  const handleSpeakerClick = (speaker: Speaker) => {
    setSelectedSpeaker(speaker);
  };

  return (
    <BrowserRouter basename="/cfp-please">
      <Routes>
        <Route
          path="/"
          element={
            <TalkFlixHome
              onCFPClick={handleCfpClick}
              onTalkClick={handleTalkClick}
            />
          }
        />
        <Route
          path="/search"
          element={
            <SearchPage
              onCFPClick={handleCfpClick}
              onTalkClick={handleTalkClick}
              onSpeakerClick={handleSpeakerClick}
            />
          }
        />
      </Routes>

      {/* CFP Detail Modal */}
      {selectedCfp && (
        <div className="cfp-detail-overlay talkflix-modal" onClick={() => setSelectedCfp(null)}>
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
                <div className={`cfp-detail-item ${
                  selectedCfp.daysUntilCfpClose !== undefined && selectedCfp.daysUntilCfpClose <= 3 ? 'cfp-detail-item--critical' :
                  selectedCfp.daysUntilCfpClose !== undefined && selectedCfp.daysUntilCfpClose <= 7 ? 'cfp-detail-item--warning' : ''
                }`}>
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
                    {selectedCfp.daysUntilCfpClose !== undefined && (
                      <div className={`cfp-deadline-urgency ${
                        selectedCfp.daysUntilCfpClose === 0 ? 'urgency-critical' :
                        selectedCfp.daysUntilCfpClose <= 3 ? 'urgency-high' :
                        selectedCfp.daysUntilCfpClose <= 7 ? 'urgency-medium' :
                        selectedCfp.daysUntilCfpClose <= 14 ? 'urgency-low' : ''
                      }`}>
                        {selectedCfp.daysUntilCfpClose === 0 ? '🔥 LAST DAY!' :
                         selectedCfp.daysUntilCfpClose === 1 ? '⚡ Tomorrow!' :
                         selectedCfp.daysUntilCfpClose <= 3 ? `🏃 ${selectedCfp.daysUntilCfpClose} days left!` :
                         selectedCfp.daysUntilCfpClose <= 7 ? `📅 This week (${selectedCfp.daysUntilCfpClose}d)` :
                         selectedCfp.daysUntilCfpClose <= 14 ? `📆 Next week (${selectedCfp.daysUntilCfpClose}d)` :
                         selectedCfp.daysUntilCfpClose <= 30 ? `${selectedCfp.daysUntilCfpClose} days left` : ''}
                      </div>
                    )}
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

            <CFPIntelSection cfp={selectedCfp} />

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

      {/* Speaker Detail Modal */}
      {selectedSpeaker && (
        <SpeakerModal speaker={selectedSpeaker} onClose={() => setSelectedSpeaker(null)} />
      )}
    </BrowserRouter>
  );
}

export default App;
