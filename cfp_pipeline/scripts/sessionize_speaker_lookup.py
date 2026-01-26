#!/usr/bin/env python3
"""Sessionize speaker profile lookup via directory search.

Uses httpx to search the speakers directory and extract profile data.

Usage:
    poetry run python cfp_pipeline/scripts/sessionize_speaker_lookup.py "Daniel Phiri"
    poetry run python cfp_pipeline/scripts/sessionize_speaker_lookup.py --batch speakers.txt
    poetry run python cfp_pipeline/scripts/sessionize_speaker_lookup.py --top 30
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def search_sessionize_speaker(client: httpx.Client, name: str) -> list[dict]:
    """Search Sessionize speakers directory for a name.

    Returns list of matching profiles with rich data from directory cards.
    """
    url = f"https://sessionize.com/speakers-directory?q={quote(name)}"

    try:
        resp = client.get(url, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error searching for {name}: {e}[/red]")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # Find all speaker cards
    cards = soup.select(".c-entry.c-entry--speaker")

    for card in cards[:10]:  # Limit to top 10 matches
        # Extract link and slug
        link_el = card.select_one(".c-entry__title a")
        if not link_el:
            continue

        href = link_el.get("href", "")
        slug = href.strip("/")
        if not slug or "/" in slug:
            continue

        # Extract photo
        photo_el = card.select_one(".c-entry__media img")
        photo_url = photo_el.get("src") if photo_el else None

        # Extract name
        display_name = link_el.get_text(strip=True)

        # Extract tagline
        tagline_el = card.select_one(".c-entry__tagline")
        tagline = tagline_el.get_text(strip=True) if tagline_el else None

        # Extract location
        location = None
        for item in card.select(".c-entry__meta-item"):
            label = item.select_one(".c-entry__meta-label")
            if label and "Location" in label.get_text():
                value = item.select_one(".c-entry__meta-value")
                if value:
                    location = value.get_text(strip=True)
                break

        # Extract sessions count
        sessions_count = None
        for item in card.select(".c-entry__meta-item"):
            label = item.select_one(".c-entry__meta-label")
            if label and "Sessions" in label.get_text():
                value = item.select_one(".c-entry__meta-value")
                if value:
                    text = value.get_text(strip=True)
                    match = re.search(r"(\d+)", text)
                    if match:
                        sessions_count = int(match.group(1))
                break

        # Extract bio/description
        bio = None
        desc_el = card.select_one(".c-entry__description p")
        if desc_el:
            bio = desc_el.get_text(strip=True)
            bio = bio.replace("Show more", "").strip()
            if len(bio) > 200:
                bio = bio[:200] + "..."

        # Extract topics
        topics = []
        for item in card.select(".c-entry__meta--tags .c-entry__meta-item"):
            label = item.select_one(".c-entry__meta-label")
            if label and "Topics" in label.get_text():
                topic_els = item.select(".c-entry__meta-value li")
                topics = [t.get_text(strip=True) for t in topic_els[:10]]
                break

        result = {
            "slug": slug,
            "name": display_name,
            "photo_url": photo_url,
            "profile_url": f"https://sessionize.com/{slug}/",
            "tagline": tagline,
            "location": location,
            "sessions_count": sessions_count,
            "bio": bio,
            "topics": topics if topics else None,
        }

        results.append(result)

    return results


def get_speaker_profile(client: httpx.Client, slug: str) -> dict | None:
    """Fetch full profile data for a Sessionize speaker.

    Returns rich profile with:
    - photo_url (high res from profile page)
    - tagline, location, bio
    - twitter, linkedin, github
    - areas (expertise areas)
    - topics (tags)
    - languages
    """
    url = f"https://sessionize.com/{slug}/"

    try:
        resp = client.get(url, timeout=15.0)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error fetching {slug}: {e}[/red]")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    profile = {
        "slug": slug,
        "profile_url": url,
    }

    # Photo (higher res from profile page)
    img = soup.select_one('img[src*="sessionize.com/image"]')
    if img:
        profile["photo_url"] = img.get("src")

    # Name
    name_el = soup.select_one("h1")
    if name_el:
        profile["name"] = name_el.get_text(strip=True)

    # Tagline
    tagline_el = soup.select_one('.c-s-speaker-info__tagline, [class*="tagline"]')
    if tagline_el:
        profile["tagline"] = tagline_el.get_text(strip=True)

    # Location
    loc_el = soup.select_one('.c-s-speaker-info__location, [class*="location"]')
    if loc_el:
        profile["location"] = loc_el.get_text(strip=True)

    # Bio from meta description
    meta_desc = soup.select_one('meta[name="description"]')
    if meta_desc:
        bio = meta_desc.get("content", "")
        if bio:
            profile["bio"] = bio[:500]  # Limit length

    # Social links
    for link in soup.select("a[href]"):
        href = link.get("href", "")
        if ("twitter.com" in href or "x.com" in href) and "twitter" not in profile:
            handle = href.rstrip("/").split("/")[-1].split("?")[0]
            if handle and handle != "intent":
                profile["twitter"] = handle
        elif "linkedin.com/in/" in href and "linkedin" not in profile:
            username = href.split("/in/")[-1].strip("/").split("?")[0]
            if username:
                profile["linkedin"] = username
        elif "github.com" in href and "github.com/sponsors" not in href and "github" not in profile:
            username = href.split("github.com/")[-1].strip("/").split("?")[0]
            # Filter out empty or generic paths
            if username and username not in ("", "orgs", "search", "explore"):
                profile["github"] = username

    # Tags - areas and topics
    tags = soup.select(".c-s-tags__item, .c-tag, [class*='tag'] li")
    all_tags = []
    for t in tags:
        text = t.get_text(strip=True)
        if text and len(text) < 50 and text not in ["All", "English", "French"]:
            all_tags.append(text)

    # First 2-3 are usually areas, rest are topics
    if all_tags:
        # Areas are broader categories
        areas = ["Humanities & Social Sciences", "Information & Communications Technology",
                 "Business & Management", "Health & Medical", "Arts", "Environment & Cleantech",
                 "Finance & Banking", "Government, Social Sector & Education"]
        profile["areas"] = [t for t in all_tags if t in areas]
        profile["topics"] = [t for t in all_tags if t not in areas][:15]

    # Languages
    lang_section = soup.select('a[href*="lang="], .c-s-speaker-sessions__item')
    languages = set()
    for el in soup.select("a"):
        text = el.get_text(strip=True)
        if text in ["English", "French", "Spanish", "German", "Portuguese", "Italian", "Japanese", "Chinese", "Korean"]:
            languages.add(text)
    if languages:
        profile["languages"] = list(languages)

    return profile


def normalize_name(name: str) -> str:
    """Normalize name: lowercase, strip diacritics (ą→a, ö→o)."""
    # NFKD decomposes characters, then we strip combining marks
    normalized = unicodedata.normalize("NFKD", name.lower().strip())
    # Remove combining diacritical marks (category 'Mn')
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def fuzzy_name_match(search_name: str, result_name: str) -> float:
    """Calculate fuzzy match score between two names (0.0-1.0).

    Uses:
    - Unicode normalization (ą→a, ö→o)
    - SequenceMatcher for Levenshtein-like ratio
    - Part-based matching for middle name handling
    - Surname must match well if first name matches (prevent "Andrew Black" → "Andrew Leong")
    """
    search_norm = normalize_name(search_name)
    result_norm = normalize_name(result_name)

    # Exact match after normalization
    if search_norm == result_norm:
        return 1.0

    search_parts = search_norm.split()
    result_parts = result_norm.split()

    if not search_parts or not result_parts:
        return 0.0

    # Part-based matching for middle names
    # "Daniel Phiri" vs "Daniel Madalitso Phiri"
    search_set = set(search_parts)
    result_set = set(result_parts)

    if search_set.issubset(result_set):
        return 0.95  # All search parts found in result
    if result_set.issubset(search_set):
        return 0.90

    # For 2-part names (first last), require both to match reasonably
    if len(search_parts) >= 2 and len(result_parts) >= 2:
        first_ratio = SequenceMatcher(None, search_parts[0], result_parts[0]).ratio()
        # Compare last parts (surname)
        last_ratio = SequenceMatcher(None, search_parts[-1], result_parts[-1]).ratio()

        # If first name matches but surname doesn't, it's likely wrong person
        if first_ratio > 0.9 and last_ratio < 0.7:
            return last_ratio * 0.5  # Penalize heavily

        # Both must match reasonably well
        combined = (first_ratio * 0.4 + last_ratio * 0.6)
        return combined

    # Single-part name or other cases: use full string ratio
    full_ratio = SequenceMatcher(None, search_norm, result_norm).ratio()
    return full_ratio


def lookup_speaker(client: httpx.Client, name: str, match_threshold: float = 0.6) -> dict | None:
    """Search for speaker and return best match with full profile."""
    results = search_sessionize_speaker(client, name)

    if not results:
        return None

    # Score all results
    scored_results = [(fuzzy_name_match(name, r.get("name", "")), r) for r in results]
    scored_results.sort(key=lambda x: x[0], reverse=True)

    best_score, best_match = scored_results[0]

    if best_score < match_threshold:
        console.print(f"  [dim]Best match '{best_match.get('name')}' scored {best_score:.2f} < {match_threshold}[/dim]")
        return None

    # Fetch full profile for social links
    full_profile = get_speaker_profile(client, best_match["slug"])

    if full_profile:
        # Merge search result data with profile data
        result = {**best_match, **full_profile}
        result["match_score"] = best_score
        return result

    best_match["match_score"] = best_score
    return best_match


def main():
    parser = argparse.ArgumentParser(description="Lookup Sessionize speaker profiles")
    parser.add_argument("name", nargs="?", help="Speaker name to search")
    parser.add_argument("--batch", "-b", help="File with speaker names (one per line)")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--skip-existing", "-s", help="Skip speakers already in this JSON file")
    parser.add_argument("--threshold", "-t", type=float, default=0.65, help="Match threshold (0.0-1.0, default 0.65)")

    args = parser.parse_args()

    # Determine speaker list
    speakers = []
    if args.name:
        speakers = [args.name]
    elif args.batch:
        with open(args.batch) as f:
            speakers = [line.strip() for line in f if line.strip()]
    else:
        parser.print_help()
        sys.exit(1)

    # Load existing results to skip
    existing_names = set()
    existing_results = []
    if args.skip_existing:
        try:
            with open(args.skip_existing) as f:
                existing_results = json.load(f)
                for r in existing_results:
                    if r.get("slug"):  # Only skip if we found a match
                        existing_names.add(r.get("search_name", "").lower())
            console.print(f"[dim]Loaded {len(existing_names)} existing results to skip[/dim]")
        except FileNotFoundError:
            pass

    # Filter speakers to lookup
    speakers_to_lookup = [s for s in speakers if s.lower() not in existing_names]
    console.print(f"[cyan]Looking up {len(speakers_to_lookup)} speakers on Sessionize (skipping {len(speakers) - len(speakers_to_lookup)})...[/cyan]")

    results = list(existing_results)

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for i, name in enumerate(speakers_to_lookup):
            console.print(f"[dim][{i+1}/{len(speakers_to_lookup)}] Searching: {name}[/dim]")

            profile = lookup_speaker(client, name, args.threshold)

            if profile:
                console.print(f"  [green]✓ Found: {profile.get('slug')} (score: {profile.get('match_score', 0):.2f})[/green]")
                profile["search_name"] = name
                results.append(profile)
            else:
                console.print(f"  [yellow]✗ Not found[/yellow]")
                results.append({"search_name": name, "found": False})

            # Rate limit - be nice to Sessionize
            time.sleep(0.5)

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"[green]Saved {len(results)} results to {args.output}[/green]")
    else:
        # Print table
        table = Table(title="Sessionize Speaker Lookup Results")
        table.add_column("Name", style="cyan")
        table.add_column("Slug", style="green")
        table.add_column("Photo", style="yellow")
        table.add_column("Twitter")
        table.add_column("LinkedIn")

        found = 0
        for r in results:
            if r.get("found") == False:
                table.add_row(r["search_name"], "❌", "", "", "")
            else:
                found += 1
                table.add_row(
                    r.get("search_name", r.get("name", "")),
                    r.get("slug", ""),
                    "✓" if r.get("photo_url") else "",
                    r.get("twitter", ""),
                    r.get("linkedin", ""),
                )

        console.print(table)
        console.print(f"\n[bold]Found: {found}/{len(results)} ({100*found//max(len(results),1)}%)[/bold]")


if __name__ == "__main__":
    main()
