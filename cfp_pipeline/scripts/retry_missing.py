#!/usr/bin/env python3
"""Retry enrichment for CFPs missing descriptions."""

import asyncio
import os
import json
from pathlib import Path

from algoliasearch.search.client import SearchClientSync
from rich.console import Console

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from enrichers.llm import enrich_from_url, infer_from_name

console = Console()

CACHE_FILE = Path(__file__).parent.parent / ".cache" / "enrichments.json"


async def retry_missing():
    """Find and retry CFPs missing descriptions."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")
    token = os.environ.get("ENABLERS_JWT")

    if not all([app_id, api_key, token]):
        console.print("[red]Missing env vars[/red]")
        return

    client = SearchClientSync(app_id, api_key)

    # Load cache
    cache = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())

    # Find missing
    response = client.browse('cfps', browse_params={
        'attributesToRetrieve': ['objectID', 'name', 'description', 'url', 'cfpUrl']
    })

    missing = []
    for hit in response.hits:
        data = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
        desc = data.get('description', '')
        if not desc or not str(desc).strip():
            missing.append(data)

    console.print(f"[cyan]Found {len(missing)} CFPs missing descriptions[/cyan]")

    # Retry each
    updated = 0
    for cfp in missing:
        name = cfp.get('name', '')
        url = cfp.get('url') or cfp.get('cfpUrl')
        obj_id = cfp.get('objectID')

        console.print(f"  Retrying: {name[:50]}...")

        try:
            if url:
                result = await enrich_from_url(name, url, token)
            else:
                result = await infer_from_name(name, token)

            if result and result.description:
                # Update cache
                cache[obj_id] = {
                    'description': result.description,
                    'topics': result.topics or [],
                    'languages': result.languages or [],
                    'technologies': result.technologies or [],
                }
                console.print(f"    [green]Got: {result.description[:60]}...[/green]")
                updated += 1
            else:
                console.print(f"    [yellow]No description extracted[/yellow]")
        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")

    # Save cache
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))
    console.print(f"\n[green]Updated {updated}/{len(missing)} CFPs[/green]")
    console.print("[cyan]Run 'cfp sync --enrich' to push to Algolia[/cyan]")


if __name__ == "__main__":
    asyncio.run(retry_missing())
