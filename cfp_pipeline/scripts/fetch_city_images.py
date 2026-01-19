#!/usr/bin/env python3
"""Fetch iconic city images from Unsplash for CFP/Talk backgrounds.

Creates a city_images.json mapping with 5 images per city.
Then enriches Algolia records with city_image_urls.

Usage:
    # First, set UNSPLASH_ACCESS_KEY in .env
    poetry run python -m cfp_pipeline.scripts.fetch_city_images --fetch   # Fetch from Unsplash
    poetry run python -m cfp_pipeline.scripts.fetch_city_images --enrich  # Update Algolia

API Key: Get free key at https://unsplash.com/developers
"""

import json
import os
import random
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from rich.console import Console
from rich.progress import track

console = Console()

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CITY_IMAGES_FILE = DATA_DIR / "city_images.json"

# Unsplash API
UNSPLASH_API = "https://api.unsplash.com"
IMAGES_PER_CITY = 5

# Fallback gradients for cities without images
FALLBACK_GRADIENTS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
    "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
]


def get_unsplash_client() -> Optional[httpx.Client]:
    """Get Unsplash API client if key is available."""
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None

    return httpx.Client(
        base_url=UNSPLASH_API,
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )


def fetch_city_images(city: str, client: httpx.Client) -> list[dict]:
    """Fetch iconic images for a city from Unsplash."""
    query = f"{city} iconic skyline cityscape"

    try:
        resp = client.get("/search/photos", params={
            "query": query,
            "per_page": IMAGES_PER_CITY,
            "orientation": "landscape",
            "content_filter": "high",  # Safe content only
        })
        resp.raise_for_status()
        data = resp.json()

        images = []
        for photo in data.get("results", []):
            images.append({
                "id": photo["id"],
                "url": photo["urls"]["regular"],  # 1080px wide
                "thumb": photo["urls"]["small"],  # 400px wide
                "blur_hash": photo.get("blur_hash"),
                "photographer": photo["user"]["name"],
                "photographer_url": photo["user"]["links"]["html"],
            })

        return images

    except httpx.HTTPError as e:
        console.print(f"[yellow]Failed to fetch {city}: {e}[/yellow]")
        return []


def load_city_images() -> dict:
    """Load existing city images mapping."""
    if CITY_IMAGES_FILE.exists():
        with open(CITY_IMAGES_FILE) as f:
            return json.load(f)
    return {}


def save_city_images(data: dict):
    """Save city images mapping."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CITY_IMAGES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    console.print(f"[green]Saved to {CITY_IMAGES_FILE}[/green]")


def get_unique_cities(prioritize: bool = True) -> list[str]:
    """Get all unique cities from Algolia CFPs, optionally sorted by frequency."""
    from algoliasearch.search.client import SearchClientSync
    from collections import Counter

    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")

    if not app_id or not api_key:
        raise ValueError("ALGOLIA_APP_ID and ALGOLIA_API_KEY required")

    client = SearchClientSync(app_id, api_key)
    city_counts = Counter()

    # Fetch from CFPs
    page = 0
    while True:
        resp = client.search_single_index('cfps', {
            'query': '',
            'hitsPerPage': 1000,
            'page': page,
            'attributesToRetrieve': ['location']
        })
        for hit in resp.hits:
            h = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
            loc = h.get('location')
            if loc and isinstance(loc, dict):
                city = loc.get('city')
                if city and city.lower() != 'online':
                    city_counts[city] += 1
        if page >= (resp.nb_pages or 1) - 1:
            break
        page += 1

    if prioritize:
        # Return cities sorted by CFP count (most first)
        return [city for city, _ in city_counts.most_common()]
    return list(city_counts.keys())


def fetch_all_cities(limit: int = 45):
    """Fetch images for all unique cities, prioritized by CFP count.

    Args:
        limit: Max cities to fetch (default 45 to stay under 50/hour rate limit)
    """
    client = get_unsplash_client()
    if not client:
        console.print("[red]UNSPLASH_ACCESS_KEY not set![/red]")
        console.print("Get a free key at: https://unsplash.com/developers")
        return

    # Load existing data
    city_images = load_city_images()

    # Get cities that need images (sorted by CFP count - top cities first)
    all_cities = get_unique_cities(prioritize=True)
    cities_to_fetch = [c for c in all_cities if c not in city_images]

    console.print(f"[cyan]Total cities: {len(all_cities)}[/cyan]")
    console.print(f"[cyan]Already have: {len(city_images)}[/cyan]")
    console.print(f"[cyan]To fetch: {len(cities_to_fetch)} (limit: {limit})[/cyan]")

    if not cities_to_fetch:
        console.print("[green]All cities already have images![/green]")
        return

    # Limit to stay under rate limit
    cities_batch = cities_to_fetch[:limit]
    console.print(f"[cyan]Fetching top {len(cities_batch)} cities this batch[/cyan]")

    fetched = 0
    rate_limited = False

    for city in track(cities_batch, description="Fetching city images"):
        images = fetch_city_images(city, client)

        # Check for rate limit (403 means we hit the limit)
        if images is None:
            # fetch_city_images returns [] on error, but let's check
            pass

        if images:
            city_images[city] = images
            console.print(f"  [dim]{city}: {len(images)} images[/dim]")
            fetched += 1
        else:
            console.print(f"  [yellow]{city}: no images found[/yellow]")

        # Rate limiting: 50 req/hour = ~1.2 req/min
        # Wait 1.5s between requests to be safe
        time.sleep(1.5)

        # Save periodically in case of interruption
        if fetched % 10 == 0 and fetched > 0:
            save_city_images(city_images)

    save_city_images(city_images)
    remaining = len(cities_to_fetch) - limit
    console.print(f"\n[bold green]Done! {len(city_images)} cities with images[/bold green]")
    if remaining > 0:
        console.print(f"[yellow]Run again in 1 hour to fetch {remaining} more cities[/yellow]")


def enrich_algolia_records():
    """Add city_image_urls to Algolia CFP records."""
    from algoliasearch.search.client import SearchClientSync

    city_images = load_city_images()
    if not city_images:
        console.print("[red]No city_images.json found! Run --fetch first[/red]")
        return

    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")
    client = SearchClientSync(app_id, api_key)

    # Process CFPs
    console.print("[bold]Enriching CFPs...[/bold]")
    updates = []
    page = 0

    while True:
        resp = client.search_single_index('cfps', {
            'query': '',
            'hitsPerPage': 1000,
            'page': page,
            'attributesToRetrieve': ['objectID', 'location', 'city_image_urls']
        })

        for hit in resp.hits:
            h = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
            obj_id = h.get('objectID')
            loc = h.get('location')

            if not loc or not isinstance(loc, dict):
                continue

            city = loc.get('city')
            if not city or city.lower() == 'online':
                continue

            # Skip if already has images
            if h.get('city_image_urls'):
                continue

            city_data = city_images.get(city)
            if city_data:
                urls = [img['url'] for img in city_data]
                updates.append({
                    'objectID': obj_id,
                    'city_image_urls': urls,
                    'city_image_thumbs': [img['thumb'] for img in city_data],
                })

        if page >= (resp.nb_pages or 1) - 1:
            break
        page += 1

    console.print(f"[cyan]CFPs to update: {len(updates)}[/cyan]")

    if updates:
        # Batch update
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            client.partial_update_objects('cfps', batch)
            console.print(f"  Updated batch {i//batch_size + 1}/{(len(updates)-1)//batch_size + 1}")

        console.print(f"[green]✓ Enriched {len(updates)} CFPs with city images[/green]")
    else:
        console.print("[green]All CFPs already have city images![/green]")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch city images from Unsplash")
    parser.add_argument("--fetch", action="store_true", help="Fetch images from Unsplash")
    parser.add_argument("--enrich", action="store_true", help="Enrich Algolia records")
    parser.add_argument("--stats", action="store_true", help="Show current stats")
    parser.add_argument("--limit", type=int, default=45, help="Max cities per batch (default: 45)")
    parser.add_argument("--missing", action="store_true", help="Show missing top cities")

    args = parser.parse_args()

    if args.missing:
        city_images = load_city_images()
        all_cities = get_unique_cities(prioritize=True)
        missing = [c for c in all_cities if c not in city_images]
        console.print(f"[bold]Missing cities (top 50):[/bold]")
        for city in missing[:50]:
            console.print(f"  {city}")
        console.print(f"\nTotal missing: {len(missing)}")
        return

    if args.stats or not (args.fetch or args.enrich):
        city_images = load_city_images()
        console.print(f"[bold]City Images Stats[/bold]")
        console.print(f"  Cities with images: {len(city_images)}")
        console.print(f"  Total images: {sum(len(imgs) for imgs in city_images.values())}")
        if city_images:
            console.print(f"\nSample cities:")
            for city in list(city_images.keys())[:5]:
                console.print(f"  {city}: {len(city_images[city])} images")
        return

    if args.fetch:
        fetch_all_cities(limit=args.limit)

    if args.enrich:
        enrich_algolia_records()


if __name__ == "__main__":
    main()
