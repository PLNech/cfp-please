#!/usr/bin/env python3
"""Enrich Algolia speakers index with GitHub profile data.

Two-stage discovery:
1. Direct: Parse GitHub link from Sessionize profile
2. Crawl: If no direct link, crawl speaker's personal website for GitHub links

Then fetches from GitHub API:
- avatar_url (profile photo)
- bio, company, location, blog, twitter_username

GitHub API: 60/hour unauthenticated, 5000/hour with GITHUB_TOKEN.

Usage:
    poetry run python cfp_pipeline/scripts/enrich_speakers_github.py --limit 50
    poetry run python cfp_pipeline/scripts/enrich_speakers_github.py --all
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import httpx
from algoliasearch.search.client import SearchClientSync
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

console = Console()

# Load env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}
GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "CFP-Pipeline/1.0",
}

# Add auth if available
if os.environ.get("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"


def extract_github_username(url: str) -> str | None:
    """Extract GitHub username from URL, filtering out repos/orgs/pages."""
    if not url or "github" not in url.lower():
        return None

    # Skip non-profile URLs
    skip_patterns = ["github.io", "/sponsors/", "/orgs/", "/marketplace",
                     "/features", "/pricing", "/enterprise", "/topics"]
    if any(p in url.lower() for p in skip_patterns):
        return None

    # Extract username from github.com/username or github.com/username/repo
    match = re.search(r"github\.com/([a-zA-Z0-9_-]+)", url)
    if match:
        username = match.group(1)
        # Filter generic paths
        if username.lower() not in ("search", "explore", "trending", "collections", "apps"):
            return username
    return None


def validate_github_user(client: httpx.Client, username: str) -> dict | None:
    """Validate GitHub user exists and fetch profile data."""
    try:
        resp = client.get(f"{GITHUB_API}/users/{username}", headers=GH_HEADERS, timeout=8.0)

        if resp.status_code == 404:
            return None

        if resp.status_code == 403:
            console.print("[red]Rate limited![/red]")
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()

        # Only accept User type (not Organization)
        if data.get("type") != "User":
            return None

        return {
            "username": username,
            "avatar_url": data.get("avatar_url"),
            "bio": data.get("bio"),
            "company": data.get("company"),
            "location": data.get("location"),
            "blog": data.get("blog"),
            "name": data.get("name"),
            "twitter_username": data.get("twitter_username"),
        }
    except Exception as e:
        console.print(f"[dim]Error validating {username}: {e}[/dim]")
        return None


def crawl_website_for_github(client: httpx.Client, website_url: str) -> str | None:
    """Crawl a website looking for GitHub profile links."""
    try:
        resp = client.get(website_url, timeout=8.0, follow_redirects=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.select("a[href]"):
            username = extract_github_username(link.get("href", ""))
            if username:
                return username

        return None
    except Exception:
        return None


def find_github_from_sessionize(client: httpx.Client, slug: str) -> tuple[str | None, str | None]:
    """Find GitHub username from Sessionize profile.

    Returns: (username, source) where source is 'direct' or 'via {website}'
    """
    try:
        resp = client.get(f"https://sessionize.com/{slug}/", timeout=10.0)
        if resp.status_code != 200:
            return None, None
    except Exception:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    github_direct = None
    website = None

    # Domains to skip when looking for personal websites
    skip_domains = ["twitter", "linkedin", "github", "sessionize", "youtube",
                    "facebook", "instagram", "twitch", "x.com", "medium.com",
                    "dev.to", "hashnode", "substack", "speakerdeck"]

    for link in soup.select("a[href]"):
        href = link.get("href", "")

        # Check for direct GitHub link
        gh = extract_github_username(href)
        if gh and not github_direct:
            github_direct = gh

        # Find personal website
        if href.startswith("http") and not any(x in href.lower() for x in skip_domains):
            if not website:
                website = href

    if github_direct:
        return github_direct, "direct"

    # Crawl personal website for GitHub link
    if website:
        gh = crawl_website_for_github(client, website)
        if gh:
            return gh, f"via {website[:40]}"

    return None, None


def get_speakers_with_sessionize(client: SearchClientSync, limit: int | None = None) -> list[dict]:
    """Fetch speakers that have sessionize_slug (for GitHub discovery)."""
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    speakers = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID", "name", "sessionize_slug", "github", "image_url", "location", "company", "twitter"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            slug = getattr(hit, "sessionize_slug", None)
            if slug:
                speakers.append({
                    "objectID": getattr(hit, "object_id", None) or getattr(hit, "objectID", None),
                    "name": getattr(hit, "name", ""),
                    "sessionize_slug": slug,
                    "github": getattr(hit, "github", None),
                    "has_image": bool(getattr(hit, "image_url", None)),
                    "has_location": bool(getattr(hit, "location", None)),
                    "has_company": bool(getattr(hit, "company", None)),
                    "has_twitter": bool(getattr(hit, "twitter", None)),
                })

    client.browse_objects("cfps_speakers", aggregator, browse_params)

    console.print(f"[dim]Found {len(speakers)} speakers with Sessionize profiles[/dim]")

    if limit:
        speakers = speakers[:limit]

    return speakers


def enrich_from_github(speaker: dict, gh_profile: dict) -> dict | None:
    """Build enrichment data from GitHub profile."""
    enrichment = {"objectID": speaker["objectID"]}
    has_data = False

    # Avatar (use if speaker has no image)
    if gh_profile.get("avatar_url") and not speaker.get("has_image"):
        enrichment["image_url"] = gh_profile["avatar_url"]
        enrichment["image_source"] = "github"
        has_data = True

    # GitHub username
    if gh_profile.get("username"):
        enrichment["github"] = gh_profile["username"]
        has_data = True

    # Location (only if speaker doesn't have one)
    if gh_profile.get("location") and not speaker.get("has_location"):
        enrichment["location"] = gh_profile["location"]
        has_data = True

    # Company (only if speaker doesn't have one)
    if gh_profile.get("company") and not speaker.get("has_company"):
        company = gh_profile["company"].lstrip("@").strip()
        if company:
            enrichment["company"] = company
            has_data = True

    # Twitter from GitHub (if we don't have it)
    if gh_profile.get("twitter_username") and not speaker.get("has_twitter"):
        enrichment["twitter"] = gh_profile["twitter_username"]
        has_data = True

    # Website/blog
    blog = gh_profile.get("blog", "").strip()
    if blog and not blog.startswith("https://github.com"):
        enrichment["website"] = blog
        has_data = True

    return enrichment if has_data else None


def main():
    parser = argparse.ArgumentParser(description="Enrich speakers with GitHub data")
    parser.add_argument("--limit", "-l", type=int, help="Max speakers to process")
    parser.add_argument("--all", "-a", action="store_true", help="Process all speakers")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Don't update Algolia")
    parser.add_argument("--output", "-o", help="Save results to JSON file")

    args = parser.parse_args()

    if not args.limit and not args.all:
        console.print("[yellow]Specify --limit N or --all[/yellow]")
        return

    limit = args.limit if args.limit else None

    # Check rate limit
    with httpx.Client() as client:
        resp = client.get(f"{GITHUB_API}/rate_limit", headers=GH_HEADERS)
        if resp.status_code == 200:
            limits = resp.json()
            remaining = limits["resources"]["core"]["remaining"]
            console.print(f"[dim]GitHub API rate limit: {remaining} requests remaining[/dim]")
            if remaining < 20:
                console.print("[red]Rate limit too low, aborting[/red]")
                return

    # Initialize Algolia client
    algolia_client = SearchClientSync(
        os.environ["ALGOLIA_APP_ID"],
        os.environ["ALGOLIA_API_KEY"],
    )

    # Get speakers with Sessionize profiles
    speakers = get_speakers_with_sessionize(algolia_client, limit)
    console.print(f"[cyan]Processing {len(speakers)} speakers...[/cyan]")

    enriched = []
    github_found = []
    not_found = []

    with httpx.Client(headers=HEADERS, follow_redirects=True) as http_client:
        with Progress() as progress:
            task = progress.add_task("Discovering GitHub profiles...", total=len(speakers))

            for speaker in speakers:
                # Stage 1: Find GitHub username
                username, source = find_github_from_sessionize(http_client, speaker["sessionize_slug"])

                if username:
                    # Stage 2: Validate and fetch profile
                    gh_profile = validate_github_user(http_client, username)

                    if gh_profile:
                        github_found.append({"name": speaker["name"], "github": username, "source": source})

                        # Stage 3: Build enrichment
                        result = enrich_from_github(speaker, gh_profile)
                        if result:
                            enriched.append(result)
                            console.print(f"  [green]✓ {speaker['name']}: @{username} ({source})[/green]")
                        else:
                            console.print(f"  [dim]= {speaker['name']}: @{username} (no new data)[/dim]")
                    else:
                        console.print(f"  [yellow]✗ {speaker['name']}: @{username} (invalid/org)[/yellow]")
                else:
                    not_found.append(speaker["name"])

                progress.advance(task)

                # Rate limit
                time.sleep(0.8)

    console.print()
    console.print(f"[bold]GitHub found: {len(github_found)}/{len(speakers)}[/bold]")
    console.print(f"[bold]Enriched: {len(enriched)}[/bold]")

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
                "github_found": github_found,
                "enriched": enriched,
                "not_found": not_found,
            }, f, indent=2)
        console.print(f"[dim]Saved to {args.output}[/dim]")


if __name__ == "__main__":
    main()
