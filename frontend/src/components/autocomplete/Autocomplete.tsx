/**
 * Autocomplete - Multi-index search autocomplete for TalkFlix
 *
 * Shows suggestions from CFPs, Talks, and Speakers indexes.
 * Dark theme matching TalkFlix design.
 */

import { useEffect, useRef } from 'react';
import { autocomplete } from '@algolia/autocomplete-js';
import { algoliasearch } from 'algoliasearch';
import { useNavigate } from 'react-router-dom';
import {
  ALGOLIA_APP_ID,
  ALGOLIA_SEARCH_KEY,
  ALGOLIA_INDEX_NAME,
  ALGOLIA_TALKS_INDEX,
  ALGOLIA_SPEAKERS_INDEX,
} from '../../config';
import type { CFP, Talk, Speaker } from '../../types';
// Import Algolia theme first, then our overrides
// @ts-expect-error - No type declarations for theme CSS
import '@algolia/autocomplete-theme-classic';
import './Autocomplete.css';

const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);

interface AutocompleteProps {
  placeholder?: string;
  onCFPSelect?: (cfp: CFP) => void;
  onTalkSelect?: (talk: Talk) => void;
  onSpeakerSelect?: (speaker: Speaker) => void;
}

export function Autocomplete({
  placeholder = 'Search CFPs, talks, speakers...',
  onCFPSelect,
  onTalkSelect,
  onSpeakerSelect,
}: AutocompleteProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Ctrl+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const input = containerRef.current?.querySelector<HTMLInputElement>('.aa-Input');
        input?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const search = autocomplete({
      container: containerRef.current,
      // Let autocomplete manage its own panel for simpler rendering
      panelPlacement: 'input-wrapper-width',
      placeholder,
      openOnFocus: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getSources({ query }): any {
        if (!query) {
          return [];
        }

        return [
          // CFPs source
          {
            sourceId: 'cfps',
            async getItems() {
              const res = await searchClient.searchSingleIndex({
                indexName: ALGOLIA_INDEX_NAME,
                searchParams: { query, hitsPerPage: 4 },
              });
              return res.hits as unknown as CFP[];
            },
            templates: {
              header({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-SourceHeader">CFPs</div>`;
              },
              item({ item, html }: { item: unknown; html: typeof String.raw }) {
                const cfp = item as CFP;
                const meta = cfp.location?.city || '';
                return html`
                  <div class="aa-ItemWrapper aa-ItemWrapper--cfp">
                    <div class="aa-ItemContent">
                      <span class="aa-ItemBadge aa-ItemBadge--cfp">CFP</span>
                      <span class="aa-ItemTitle">${cfp.name}</span>
                      ${meta ? html`<span class="aa-ItemMeta">${meta}</span>` : ''}
                    </div>
                  </div>
                `;
              },
              noResults({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-NoResults">No CFPs found</div>`;
              },
            },
            onSelect({ item }: { item: unknown }) {
              if (onCFPSelect) {
                onCFPSelect(item as CFP);
              }
            },
          },
          // Talks source
          {
            sourceId: 'talks',
            async getItems() {
              const res = await searchClient.searchSingleIndex({
                indexName: ALGOLIA_TALKS_INDEX,
                searchParams: { query, hitsPerPage: 4 },
              });
              return res.hits as unknown as Talk[];
            },
            templates: {
              header({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-SourceHeader">Talks</div>`;
              },
              item({ item, html }: { item: unknown; html: typeof String.raw }) {
                const talk = item as Talk;
                const meta = talk.speaker || '';
                return html`
                  <div class="aa-ItemWrapper aa-ItemWrapper--talk">
                    <div class="aa-ItemContent">
                      <span class="aa-ItemBadge aa-ItemBadge--talk">Talk</span>
                      <span class="aa-ItemTitle">${talk.title}</span>
                      ${meta ? html`<span class="aa-ItemMeta">${meta}</span>` : ''}
                    </div>
                  </div>
                `;
              },
              noResults({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-NoResults">No talks found</div>`;
              },
            },
            onSelect({ item }: { item: unknown }) {
              if (onTalkSelect) {
                onTalkSelect(item as Talk);
              }
            },
          },
          // Speakers source
          {
            sourceId: 'speakers',
            async getItems() {
              const res = await searchClient.searchSingleIndex({
                indexName: ALGOLIA_SPEAKERS_INDEX,
                searchParams: { query, hitsPerPage: 3 },
              });
              return res.hits as unknown as Speaker[];
            },
            templates: {
              header({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-SourceHeader">Speakers</div>`;
              },
              item({ item, html }: { item: unknown; html: typeof String.raw }) {
                const speaker = item as Speaker;
                const meta = speaker.company || '';
                return html`
                  <div class="aa-ItemWrapper aa-ItemWrapper--speaker">
                    <div class="aa-ItemContent">
                      <span class="aa-ItemBadge aa-ItemBadge--speaker">Speaker</span>
                      <span class="aa-ItemTitle">${speaker.name}</span>
                      ${meta ? html`<span class="aa-ItemMeta">${meta}</span>` : ''}
                    </div>
                  </div>
                `;
              },
              noResults({ html }: { html: typeof String.raw }) {
                return html`<div class="aa-NoResults">No speakers found</div>`;
              },
            },
            onSelect({ item }: { item: unknown }) {
              if (onSpeakerSelect) {
                onSpeakerSelect(item as Speaker);
              }
            },
          },
        ];
      },
      onSubmit({ state }) {
        // Navigate to search page with query
        navigate(`/search?q=${encodeURIComponent(state.query)}`);
      },
    });

    return () => {
      search.destroy();
    };
  }, [navigate, onCFPSelect, onTalkSelect, onSpeakerSelect, placeholder]);

  return (
    <div className="talkflix-autocomplete">
      <div ref={containerRef} className="talkflix-autocomplete-input" />
    </div>
  );
}
