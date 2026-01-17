"""Algolia indexer for CFP data."""

import os
from typing import Optional

from algoliasearch.search.client import SearchClientSync
from algoliasearch.search.models.batch_request import BatchRequest
from algoliasearch.search.models.action import Action
from rich.console import Console

from cfp_pipeline.models import CFP

console = Console()


def get_algolia_client() -> SearchClientSync:
    """Get Algolia client from environment variables."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")

    if not app_id or not api_key:
        raise ValueError(
            "ALGOLIA_APP_ID and ALGOLIA_API_KEY must be set in environment"
        )

    return SearchClientSync(app_id, api_key)


def configure_index(client: SearchClientSync, index_name: str) -> None:
    """Configure index settings for optimal CFP search."""
    console.print(f"[cyan]Configuring index '{index_name}'...[/cyan]")

    settings = {
        # Searchable attributes in priority order
        "searchableAttributes": [
            "name",
            "topics,topicsNormalized",
            "description",
            "location.city,location.region,location.country",
        ],
        # Facets for filtering
        "attributesForFaceting": [
            "filterOnly(cfpStatus)",
            "searchable(topics)",
            "searchable(topicsNormalized)",
            "searchable(location.region)",
            "searchable(location.country)",
            "searchable(location.continent)",
            "searchable(location.city)",
        ],
        # Custom ranking: urgency first
        "customRanking": [
            "asc(daysUntilCfpClose)",
            "asc(cfpEndDate)",
        ],
        # Relevance tuning
        "typoTolerance": True,
        "minWordSizefor1Typo": 4,
        "minWordSizefor2Typos": 8,
        # Highlighting
        "attributesToHighlight": ["name", "description", "topics"],
        # Return all attributes by default
        "attributesToRetrieve": ["*"],
        # Pagination
        "hitsPerPage": 20,
        "paginationLimitedTo": 1000,
    }

    client.set_settings(index_name, settings)
    console.print(f"[green]Index '{index_name}' configured successfully[/green]")


def index_cfps(
    client: SearchClientSync,
    index_name: str,
    cfps: list[CFP],
    batch_size: int = 100,
) -> int:
    """Index CFPs to Algolia in batches.

    Returns:
        Number of records indexed.
    """
    console.print(f"[cyan]Indexing {len(cfps)} CFPs to '{index_name}'...[/cyan]")

    records = [cfp.to_algolia_record() for cfp in cfps]
    total_indexed = 0

    # Batch indexing
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        requests = [
            BatchRequest(action=Action.UPDATEOBJECT, body=record)
            for record in batch
        ]

        response = client.batch(index_name, {"requests": requests})
        total_indexed += len(batch)
        console.print(
            f"  [dim]Indexed batch {i // batch_size + 1}: "
            f"{len(batch)} records (task: {response.task_id})[/dim]"
        )

    console.print(f"[green]Indexed {total_indexed} CFPs successfully[/green]")
    return total_indexed


def clear_index(client: SearchClientSync, index_name: str) -> None:
    """Clear all records from an index (use with caution)."""
    console.print(f"[yellow]Clearing index '{index_name}'...[/yellow]")
    client.clear_objects(index_name)
    console.print(f"[green]Index '{index_name}' cleared[/green]")


def get_index_stats(client: SearchClientSync, index_name: str) -> dict:
    """Get statistics about an index."""
    # Use browse to count records
    try:
        response = client.search_single_index(
            index_name,
            {"query": "", "hitsPerPage": 0},
        )
        return {
            "index_name": index_name,
            "num_records": response.nb_hits,
        }
    except Exception as e:
        return {
            "index_name": index_name,
            "error": str(e),
        }
