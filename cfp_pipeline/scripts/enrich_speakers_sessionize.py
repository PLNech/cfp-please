#!/usr/bin/env python3
"""Enrich Algolia speakers index with Sessionize profile data.

Looks up speakers on Sessionize and updates their records with:
- image_url, tagline, location, bio
- twitter, linkedin, github
- sessionize_slug (for linking)

Usage:
    poetry run python cfp_pipeline/scripts/enrich_speakers_sessionize.py --limit 50
    poetry run python cfp_pipeline/scripts/enrich_speakers_sessionize.py --all
"""

import argparse
import json
import os
import time
from pathlib import Path

import httpx
from algoliasearch.search.client import SearchClientSync
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

console = Console()

# Load env BEFORE importing lookup functions
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

# Import the lookup functions from the CLI
from sessionize_speaker_lookup import (
    HEADERS,
    lookup_speaker,
    fuzzy_name_match,
)


def get_speakers_to_enrich(client: SearchClientSync, limit: int | None = None) -> list[dict]:
    """Fetch speakers that don't have image_url yet."""
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    speakers = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID", "name", "image_url", "sessionize_slug"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            obj_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            name = getattr(hit, "name", None)
            image_url = getattr(hit, "image_url", None)
            sessionize_slug = getattr(hit, "sessionize_slug", None)

            # Skip if already has image from Sessionize
            if sessionize_slug and image_url:
                continue

            if obj_id and name:
                speakers.append({
                    "objectID": obj_id,
                    "name": name,
                    "has_image": bool(image_url),
                })

    client.browse_objects("cfps_speakers", aggregator, browse_params)

    console.print(f"[dim]Found {len(speakers)} speakers without Sessionize data[/dim]")

    if limit:
        speakers = speakers[:limit]

    return speakers


def enrich_speaker(http_client: httpx.Client, speaker: dict) -> dict | None:
    """Look up speaker on Sessionize and return enrichment data."""
    profile = lookup_speaker(http_client, speaker["name"], match_threshold=0.65)

    if not profile:
        return None

    # Map Sessionize fields to our Speaker model
    enrichment = {
        "objectID": speaker["objectID"],
    }

    # Only use absolute image URLs (filter out /Assets/no-avatar.png etc)
    photo_url = profile.get("photo_url", "")
    if photo_url and photo_url.startswith("https://"):
        enrichment["image_url"] = photo_url

    if profile.get("slug"):
        enrichment["sessionize_slug"] = profile["slug"]

    if profile.get("tagline"):
        enrichment["tagline"] = profile["tagline"]

    if profile.get("location"):
        enrichment["location"] = profile["location"]

    if profile.get("twitter"):
        enrichment["twitter"] = profile["twitter"]

    if profile.get("linkedin"):
        enrichment["linkedin"] = profile["linkedin"]

    if profile.get("github"):
        enrichment["github"] = profile["github"]

    # Don't overwrite profile_url if we already have one
    if profile.get("profile_url"):
        enrichment["sessionize_url"] = profile["profile_url"]

    return enrichment


def main():
    parser = argparse.ArgumentParser(description="Enrich speakers with Sessionize data")
    parser.add_argument("--limit", "-l", type=int, help="Max speakers to process")
    parser.add_argument("--all", "-a", action="store_true", help="Process all speakers")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Don't update Algolia")
    parser.add_argument("--output", "-o", help="Save results to JSON file")

    args = parser.parse_args()

    if not args.limit and not args.all:
        console.print("[yellow]Specify --limit N or --all[/yellow]")
        return

    limit = args.limit if args.limit else None

    # Initialize Algolia client
    algolia_client = SearchClientSync(
        os.environ["ALGOLIA_APP_ID"],
        os.environ["ALGOLIA_API_KEY"],
    )

    # Get speakers to enrich
    speakers = get_speakers_to_enrich(algolia_client, limit)
    console.print(f"[cyan]Processing {len(speakers)} speakers...[/cyan]")

    enriched = []
    not_found = []

    with httpx.Client(headers=HEADERS, follow_redirects=True) as http_client:
        with Progress() as progress:
            task = progress.add_task("Looking up speakers...", total=len(speakers))

            for speaker in speakers:
                result = enrich_speaker(http_client, speaker)

                if result:
                    enriched.append(result)
                    console.print(f"  [green]✓ {speaker['name']} -> {result.get('sessionize_slug')}[/green]")
                else:
                    not_found.append(speaker["name"])
                    console.print(f"  [dim]✗ {speaker['name']}[/dim]")

                progress.advance(task)

                # Rate limit
                time.sleep(0.5)

    console.print()
    console.print(f"[bold]Found: {len(enriched)}/{len(speakers)} ({100*len(enriched)//max(len(speakers),1)}%)[/bold]")

    # Update Algolia
    if enriched and not args.dry_run:
        console.print(f"[cyan]Updating {len(enriched)} speakers in Algolia...[/cyan]")
        algolia_client.partial_update_objects("cfps_speakers", enriched)
        console.print("[green]Done![/green]")
    elif args.dry_run:
        console.print("[yellow]Dry run - no updates made[/yellow]")

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "enriched": enriched,
                "not_found": not_found,
            }, f, indent=2)
        console.print(f"[dim]Saved to {args.output}[/dim]")


if __name__ == "__main__":
    main()
