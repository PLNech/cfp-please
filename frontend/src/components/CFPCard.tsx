import { formatDistanceToNow } from 'date-fns';
import type { CFP } from '../types';
import { getUrgencyLevel, getUrgencyColor } from '../types';

interface CFPCardProps {
  hit: CFP;
  onClick?: (cfp: CFP) => void;
  isHighlighted?: boolean;
}

export function CFPCard({ hit, onClick, isHighlighted }: CFPCardProps) {
  const urgency = getUrgencyLevel(hit.daysUntilCfpClose);
  const urgencyColor = getUrgencyColor(urgency);

  const locationStr = [hit.location?.city, hit.location?.country]
    .filter(Boolean)
    .join(', ') || hit.location?.raw || 'Location TBD';

  const deadlineStr = hit.cfpEndDateISO
    ? `Closes ${formatDistanceToNow(new Date(hit.cfpEndDateISO), { addSuffix: true })}`
    : 'Deadline TBD';

  return (
    <article
      className={`cfp-card${isHighlighted ? ' cfp-card-highlighted' : ''}`}
      onClick={() => onClick?.(hit)}
      style={{
        borderLeft: `4px solid ${urgencyColor}`,
      }}
    >
      <header className="cfp-card-header">
        <h3 className="cfp-card-title">{hit.name}</h3>
        <span
          className="cfp-card-deadline"
          style={{ color: urgencyColor }}
        >
          {deadlineStr}
        </span>
      </header>

      {hit.description && (
        <p className="cfp-card-description">
          {hit.description.length > 150
            ? `${hit.description.slice(0, 150)}...`
            : hit.description}
        </p>
      )}

      <div className="cfp-card-meta">
        <span className="cfp-card-location">{locationStr}</span>
        {hit.eventStartDateISO && (
          <span className="cfp-card-event-date">
            Event: {new Date(hit.eventStartDateISO).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </span>
        )}
      </div>

      {hit.topicsNormalized?.length > 0 && (
        <div className="cfp-card-topics">
          {hit.topicsNormalized.slice(0, 4).map((topic) => (
            <span key={topic} className="cfp-card-topic">
              {topic}
            </span>
          ))}
        </div>
      )}

      <div className="cfp-card-actions">
        {hit.cfpUrl && (
          <a
            href={hit.cfpUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-card-link"
            onClick={(e) => e.stopPropagation()}
          >
            Submit Talk
          </a>
        )}
        {hit.url && (
          <a
            href={hit.url}
            target="_blank"
            rel="noopener noreferrer"
            className="cfp-card-link cfp-card-link-secondary"
            onClick={(e) => e.stopPropagation()}
          >
            Event Site
          </a>
        )}
      </div>
    </article>
  );
}
