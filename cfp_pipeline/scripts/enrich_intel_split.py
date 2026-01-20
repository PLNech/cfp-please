#!/usr/bin/env python3
"""Intel Enrichment with Split Storage - Gentle rate-limited version.

Stores raw intel in separate indexes, compact summaries in main cfps index.
Respects API rate limits to avoid bans.

Usage:
    poetry run python -m cfp_pipeline.scripts.enrich_intel_split [--limit N] [--delay SECONDS]
"""

import argparse
import asyncio
import os
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

load_dotenv(override=True)

from cfp_pipeline.enrichers.popularity import (
    fetch_hn_intel,
    fetch_github_intel,
    fetch_reddit_intel,
    fetch_devto_intel,
)
from cfp_pipeline.indexers.intel import (
    get_client,
    configure_intel_indexes,
    index_hn_intel,
    index_github_intel,
    index_reddit_intel,
    index_devto_intel,
    INTEL_INDEX_HN,
    INTEL_INDEX_GITHUB,
    INTEL_INDEX_REDDIT,
    INTEL_INDEX_DEVTO,
)

console = Console()

# Gentle rate limits (requests per minute)
RATE_LIMITS = {
    "hn": 30,       # HN API is generous
    "github": 10,   # GitHub unauthenticated is strict
    "reddit": 20,   # Reddit public JSON
    "devto": 30,    # DEV.to is generous
}

# Delay between CFPs (seconds)
DEFAULT_DELAY = 2.0


async def fetch_intel_gentle(name: str, delay: float = 1.0) -> dict:
    """Fetch intel from all sources with delays between requests."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = {
            "hn": {},
            "github": {},
            "reddit": {},
            "devto": {},
        }

        # HN
        try:
            results["hn"] = await fetch_hn_intel(client, name)
            await asyncio.sleep(delay)
        except Exception as e:
            console.print(f"[dim]HN error for {name}: {e}[/dim]")

        # GitHub (slower, more strict)
        try:
            results["github"] = await fetch_github_intel(client, name)
            await asyncio.sleep(delay * 2)  # Extra gentle with GitHub
        except Exception as e:
            console.print(f"[dim]GitHub error for {name}: {e}[/dim]")

        # Reddit
        try:
            results["reddit"] = await fetch_reddit_intel(client, name)
            await asyncio.sleep(delay)
        except Exception as e:
            console.print(f"[dim]Reddit error for {name}: {e}[/dim]")

        # DEV.to
        try:
            results["devto"] = await fetch_devto_intel(client, name)
            await asyncio.sleep(delay)
        except Exception as e:
            console.print(f"[dim]DEV.to error for {name}: {e}[/dim]")

        return results


def build_compact_cfp_intel(intel: dict) -> dict:
    """Build compact intel summary for main CFP record (<10KB)."""
    hn = intel.get("hn", {})
    github = intel.get("github", {})
    reddit = intel.get("reddit", {})
    devto = intel.get("devto", {})

    # Calculate scores
    hn_score = (hn.get("total_points", 0) or 0) + (hn.get("total_stories", 0) or 0) * 10
    github_score = (github.get("total_stars", 0) or 0) + (github.get("total_repos", 0) or 0) * 5
    reddit_score = (reddit.get("total_posts", 0) or 0) * 3
    devto_score = (devto.get("total_articles", 0) or 0) * 5

    # Popularity score (0-100)
    import math
    raw_score = hn_score * 0.4 + github_score * 0.3 + reddit_score * 0.2 + devto_score * 0.1
    popularity = min(100, math.log1p(raw_score) * 8)

    return {
        # HN compact
        "hnStories": hn.get("total_stories", 0) or 0,
        "hnPoints": hn.get("total_points", 0) or 0,
        "hnScore": hn_score,
        "hnStoryTitles": (hn.get("story_titles") or [])[:5],  # Just top 5

        # GitHub compact
        "githubRepos": github.get("total_repos", 0) or 0,
        "githubStars": github.get("total_stars", 0) or 0,
        "githubScore": github_score,
        "githubLanguages": (github.get("languages") or [])[:5],

        # Reddit compact
        "redditPosts": reddit.get("total_posts", 0) or 0,
        "redditSubreddits": (reddit.get("subreddits") or [])[:5],
        "redditScore": reddit_score,

        # DEV.to compact
        "devtoArticles": devto.get("total_articles", 0) or 0,
        "devtoTags": (devto.get("tags") or [])[:5],
        "devtoScore": devto_score,

        # Overall
        "popularityScore": round(popularity, 1),
        "intelEnriched": True,
        "intelFetchedAt": datetime.utcnow().isoformat(),
    }


async def enrich_cfp(
    search_client,
    cfp: dict,
    delay: float,
    progress=None,
    task_id=None,
) -> dict:
    """Enrich a single CFP with intel data."""
    cfp_id = cfp.get("objectID")
    cfp_name = cfp.get("name", "Unknown")

    if progress and task_id:
        progress.update(task_id, description=f"[cyan]{cfp_name[:40]}...")

    # Fetch intel from all sources
    intel = await fetch_intel_gentle(cfp_name, delay=delay / 4)

    # Index raw data to separate indexes
    hn_indexed = index_hn_intel(search_client, cfp_id, cfp_name, intel.get("hn", {}))
    github_indexed = index_github_intel(search_client, cfp_id, cfp_name, intel.get("github", {}))
    reddit_indexed = index_reddit_intel(search_client, cfp_id, cfp_name, intel.get("reddit", {}))
    devto_indexed = index_devto_intel(search_client, cfp_id, cfp_name, intel.get("devto", {}))

    # Build compact summary for main index
    compact = build_compact_cfp_intel(intel)

    # Log progress
    indexed_count = sum([hn_indexed, github_indexed, reddit_indexed, devto_indexed])
    if compact["popularityScore"] > 0:
        console.print(
            f"  [green]{cfp_name[:40]}[/green]: "
            f"score={compact['popularityScore']:.1f}, "
            f"hn={compact['hnStories']}, gh={compact['githubRepos']}, "
            f"reddit={compact['redditPosts']}, devto={compact['devtoArticles']} "
            f"[dim]({indexed_count} indexes)[/dim]"
        )

    return {**cfp, **compact}


async def main(limit: int = 0, delay: float = DEFAULT_DELAY, skip_existing: bool = True):
    """Main enrichment loop."""
    console.print("[bold]Intel Enrichment (Split Storage)[/bold]")
    console.print(f"Delay: {delay}s between CFPs, gentle rate limits\n")

    # Get Algolia client
    search_client = get_client()

    # Configure intel indexes
    console.print("[cyan]Configuring intel indexes...[/cyan]")
    try:
        configure_intel_indexes(search_client)
    except Exception as e:
        console.print(f"[yellow]Index config warning: {e}[/yellow]")

    # Fetch all CFPs from main index
    console.print("[cyan]Fetching CFPs from index...[/cyan]")
    cfps = []
    page = 0

    while True:
        result = search_client.search_single_index(
            os.environ.get("ALGOLIA_INDEX_NAME", "cfps"),
            {
                "query": "",
                "hitsPerPage": 100,
                "page": page,
                "attributesToRetrieve": ["objectID", "name", "intelEnriched", "popularityScore"],
            }
        )

        for hit in result.hits:
            cfp = {
                "objectID": getattr(hit, "object_id", None),
                "name": getattr(hit, "name", None) or hit.model_extra.get("name"),
                "intelEnriched": hit.model_extra.get("intelEnriched", False),
            }

            # Skip if already enriched (unless forced)
            if skip_existing and cfp.get("intelEnriched"):
                continue

            if cfp["objectID"] and cfp["name"]:
                cfps.append(cfp)

        if page >= (result.nb_pages or 1) - 1:
            break
        page += 1

    console.print(f"Found {len(cfps)} CFPs to enrich\n")

    if limit > 0:
        cfps = cfps[:limit]
        console.print(f"[yellow]Limited to {limit} CFPs[/yellow]\n")

    if not cfps:
        console.print("[green]All CFPs already enriched![/green]")
        return

    # Enrich CFPs with progress bar
    enriched_cfps = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Enriching...", total=len(cfps))

        for i, cfp in enumerate(cfps):
            try:
                enriched = await enrich_cfp(
                    search_client, cfp, delay,
                    progress=progress, task_id=task,
                )
                enriched_cfps.append(enriched)
            except Exception as e:
                console.print(f"[red]Error enriching {cfp.get('name')}: {e}[/red]")

            progress.update(task, advance=1)

            # Delay between CFPs
            if i < len(cfps) - 1:
                await asyncio.sleep(delay)

    # Update main index with compact summaries
    console.print(f"\n[cyan]Updating main index with {len(enriched_cfps)} compact summaries...[/cyan]")

    index_name = os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Batch update (only the intel fields)
    updates = []
    for cfp in enriched_cfps:
        update = {"objectID": cfp["objectID"]}
        for key in [
            "hnStories", "hnPoints", "hnScore", "hnStoryTitles",
            "githubRepos", "githubStars", "githubScore", "githubLanguages",
            "redditPosts", "redditSubreddits", "redditScore",
            "devtoArticles", "devtoTags", "devtoScore",
            "popularityScore", "intelEnriched", "intelFetchedAt",
        ]:
            if key in cfp:
                update[key] = cfp[key]
        updates.append(update)

    if updates:
        search_client.partial_update_objects(index_name, updates)
        console.print(f"[green]Updated {len(updates)} CFPs in main index[/green]")

    # Summary
    with_intel = sum(1 for c in enriched_cfps if c.get("popularityScore", 0) > 0)
    console.print(f"\n[bold green]Done![/bold green]")
    console.print(f"  Enriched: {len(enriched_cfps)} CFPs")
    console.print(f"  With intel data: {with_intel}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich CFPs with intel (split storage)")
    parser.add_argument("--limit", "-l", type=int, default=0, help="Limit CFPs to process (0=all)")
    parser.add_argument("--delay", "-d", type=float, default=DEFAULT_DELAY, help="Delay between CFPs (seconds)")
    parser.add_argument("--force", "-f", action="store_true", help="Re-enrich already enriched CFPs")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, delay=args.delay, skip_existing=not args.force))
