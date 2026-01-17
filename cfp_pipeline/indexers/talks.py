"""Algolia indexer for conference talks."""

import os
from typing import Optional

from algoliasearch.search.client import SearchClientSync
from rich.console import Console

from cfp_pipeline.models.talk import Talk, talk_to_algolia

console = Console()

TALKS_INDEX_NAME = "talks"


def get_talks_index_name() -> str:
    """Get talks index name from env or default."""
    base = os.environ.get("ALGOLIA_INDEX_NAME", "cfps")
    return f"{base}_talks"  # e.g., "cfps_talks"


def configure_talks_index(client: SearchClientSync, index_name: Optional[str] = None) -> None:
    """Configure talks index settings for optimal search."""
    index_name = index_name or get_talks_index_name()

    settings = {
        # Searchable attributes (priority order)
        "searchableAttributes": [
            "title",
            "speaker,speakers",
            "conference_name",
            "description",
            "topics",
            "channel",
        ],

        # Facets for filtering
        "attributesForFaceting": [
            "filterOnly(conference_id)",  # FK filter
            "searchable(conference_name)",
            "searchable(speaker)",
            "year",
            "topics",
            "languages",
            "channel",
        ],

        # Custom ranking
        "customRanking": [
            "desc(popularity_score)",  # Popular talks first
            "desc(view_count)",
            "desc(year)",  # Recent first
        ],

        # Highlighting
        "attributesToHighlight": [
            "title",
            "speaker",
            "description",
        ],

        # Return these attributes
        "attributesToRetrieve": [
            "objectID",
            "conference_id",
            "conference_name",
            "title",
            "speaker",
            "speakers",
            "description",
            "url",
            "thumbnail_url",
            "year",
            "duration_minutes",
            "view_count",
            "topics",
        ],
    }

    console.print(f"[cyan]Configuring talks index: {index_name}[/cyan]")
    client.set_settings(index_name, settings)
    console.print("[green]Talks index configured[/green]")


def index_talks(
    client: SearchClientSync,
    talks: list[Talk],
    index_name: Optional[str] = None,
) -> int:
    """Index talks to Algolia.

    Args:
        client: Algolia client
        talks: List of Talk objects
        index_name: Optional index name override

    Returns:
        Number of talks indexed
    """
    index_name = index_name or get_talks_index_name()

    if not talks:
        console.print("[yellow]No talks to index[/yellow]")
        return 0

    # Convert to Algolia records
    records = [talk_to_algolia(talk) for talk in talks]

    console.print(f"[cyan]Indexing {len(records)} talks to {index_name}...[/cyan]")

    # Batch save (Algolia handles batching internally)
    response = client.save_objects(index_name, records)

    console.print(f"[green]Indexed {len(records)} talks[/green]")
    return len(records)


def get_talks_for_conference(
    client: SearchClientSync,
    conference_id: str,
    index_name: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Get all talks for a specific conference.

    Args:
        client: Algolia client
        conference_id: Conference objectID
        index_name: Optional index name override
        limit: Max talks to return

    Returns:
        List of talk records
    """
    index_name = index_name or get_talks_index_name()

    results = client.search_single_index(
        index_name,
        {
            "filters": f"conference_id:{conference_id}",
            "hitsPerPage": limit,
        }
    )

    return results.hits


def get_talks_stats(
    client: SearchClientSync,
    index_name: Optional[str] = None,
) -> dict:
    """Get talks index statistics."""
    index_name = index_name or get_talks_index_name()

    try:
        # Get index stats
        settings = client.get_settings(index_name)

        # Search for count
        results = client.search_single_index(
            index_name,
            {"query": "", "hitsPerPage": 0}
        )

        return {
            "index_name": index_name,
            "num_talks": results.nb_hits,
        }
    except Exception as e:
        return {"error": str(e)}


def clear_talks_index(
    client: SearchClientSync,
    index_name: Optional[str] = None,
) -> None:
    """Clear all talks from index."""
    index_name = index_name or get_talks_index_name()
    console.print(f"[yellow]Clearing talks index: {index_name}[/yellow]")
    client.clear_objects(index_name)
    console.print("[green]Talks index cleared[/green]")
