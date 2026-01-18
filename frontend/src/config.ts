// Algolia configuration
export const ALGOLIA_APP_ID = import.meta.env.VITE_ALGOLIA_APP_ID || 'TDNMRH8LS3';
export const ALGOLIA_SEARCH_KEY = import.meta.env.VITE_ALGOLIA_SEARCH_KEY || '';
export const ALGOLIA_INDEX_NAME = import.meta.env.VITE_ALGOLIA_INDEX_NAME || 'cfps';
export const ALGOLIA_TALKS_INDEX = import.meta.env.VITE_ALGOLIA_TALKS_INDEX || 'cfps_talks';

// Agent Studio configuration
export const AGENT_ID = import.meta.env.VITE_AGENT_ID || '9f27077f-f2bb-465f-a5cd-80cb8928995e';

// Feature flags
export const ENABLE_TALKS = true;
