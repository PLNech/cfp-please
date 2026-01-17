import {
  useRefinementList,
  useClearRefinements,
  useCurrentRefinements,
} from 'react-instantsearch';

interface FilterSectionProps {
  attribute: string;
  title: string;
  limit?: number;
}

function FilterSection({ attribute, title, limit = 10 }: FilterSectionProps) {
  const { items, refine } = useRefinementList({
    attribute,
    limit,
    sortBy: ['count:desc'],
  });

  if (items.length === 0) return null;

  return (
    <div className="filter-section">
      <h4 className="filter-title">{title}</h4>
      <ul className="filter-list">
        {items.map((item) => (
          <li key={item.value} className="filter-item">
            <label className="filter-label">
              <input
                type="checkbox"
                checked={item.isRefined}
                onChange={() => refine(item.value)}
                className="filter-checkbox"
              />
              <span className="filter-value">{item.label}</span>
              <span className="filter-count">{item.count}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ActiveFilters() {
  const { items } = useCurrentRefinements();
  const { refine: clearAll, canRefine } = useClearRefinements();

  if (!canRefine) return null;

  return (
    <div className="active-filters">
      <div className="active-filters-header">
        <span>Active filters</span>
        <button onClick={clearAll} className="clear-all-btn">
          Clear all
        </button>
      </div>
      <div className="active-filters-list">
        {items.map((item) =>
          item.refinements.map((refinement) => (
            <button
              key={`${item.attribute}-${refinement.value}`}
              className="active-filter-tag"
              onClick={() => item.refine(refinement)}
            >
              {refinement.label} &times;
            </button>
          ))
        )}
      </div>
    </div>
  );
}

export function Filters() {
  return (
    <aside className="filters-container">
      <h3 className="filters-heading">Refine Results</h3>

      <ActiveFilters />

      <FilterSection
        attribute="topicsNormalized"
        title="Topics"
        limit={15}
      />

      <FilterSection
        attribute="location.region"
        title="Region"
      />

      <FilterSection
        attribute="location.country"
        title="Country"
        limit={15}
      />

      <FilterSection
        attribute="location.continent"
        title="Continent"
      />

      <FilterSection
        attribute="eventFormat"
        title="Format"
      />

      <FilterSection
        attribute="languages"
        title="Languages"
        limit={10}
      />
    </aside>
  );
}
