#!/usr/bin/env python3
"""Index verified DevCon talks from YouTube research.

This script:
1. Loads research results from devcon_youtube_research.json
2. Filters to official Algolia channel videos
3. Extracts proper speaker names
4. Checks for duplicates in existing index
5. Indexes new talks
"""
import json
import os
import re
from pathlib import Path

# Load env
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

from algoliasearch.search.client import SearchClientSync

APP_ID = os.environ['ALGOLIA_APP_ID']
API_KEY = os.environ['ALGOLIA_API_KEY']

client = SearchClientSync(APP_ID, API_KEY)

# Load Algolia speakers data for name resolution
ALGOLIA_SPEAKERS = {}
speakers_path = Path(__file__).parent.parent.parent / "data" / "algolia_speakers.json"
if speakers_path.exists():
    with open(speakers_path) as f:
        data = json.load(f)
        for speaker in data.get("speakers", []):
            ALGOLIA_SPEAKERS[speaker["name"].lower()] = speaker["name"]
            for alias in speaker.get("aliases", []):
                ALGOLIA_SPEAKERS[alias.lower().replace("-", " ")] = speaker["name"]


def extract_speaker_from_title(title: str) -> tuple[str | None, str]:
    """Extract speaker name from video title.

    Returns:
        Tuple of (speaker_name, clean_title)
    """
    # Common patterns:
    # "Talk Title - Speaker Name, Company"
    # "Talk Title - Speaker Name"

    # Pattern: "Title - Name, Company"
    match = re.search(r'^(.+?)\s*-\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)(?:,\s*\w+)?$', title)
    if match:
        clean_title = match.group(1).strip()
        speaker_raw = match.group(2).strip()

        # Remove ", Algolia" or ", Company" suffix
        speaker = re.sub(r',\s*\w+.*$', '', speaker_raw).strip()

        # Try to resolve to canonical name
        speaker_lower = speaker.lower()
        if speaker_lower in ALGOLIA_SPEAKERS:
            speaker = ALGOLIA_SPEAKERS[speaker_lower]

        return speaker, clean_title

    return None, title


def get_existing_talk_ids(talks_index: str) -> set[str]:
    """Get all existing talk objectIDs from index."""
    existing = set()

    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            obj_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            if obj_id:
                existing.add(obj_id)

    client.browse_objects(talks_index, aggregator, browse_params)
    return existing


def main():
    print("=" * 70)
    print("INDEXING VERIFIED DEVCON TALKS")
    print("=" * 70)

    # Load research results
    research_path = Path(__file__).parent.parent.parent / "data" / "devcon_youtube_research.json"
    with open(research_path) as f:
        research = json.load(f)

    videos = research.get("videos", [])
    print(f"\nLoaded {len(videos)} videos from research")

    # Get existing talk IDs
    print("\nChecking existing talks index...")
    existing_ids = get_existing_talk_ids("cfps_talks")
    print(f"Found {len(existing_ids)} existing talks")

    # Filter and process videos
    talks_to_add = []

    for video in videos:
        video_id = video.get("video_id")
        if not video_id:
            continue

        object_id = f"yt_{video_id}"

        # Skip if already exists
        if object_id in existing_ids:
            continue

        # Only process Algolia channel videos (official DevCon)
        channel = video.get("channel", "")
        if channel.lower() != "algolia":
            continue

        # Only process playlist videos (verified DevCon)
        source = video.get("source", "")
        if not source.startswith("playlist:"):
            continue

        title = video.get("title", "")
        year = video.get("year")

        # Extract speaker from title
        speaker, clean_title = extract_speaker_from_title(title)

        # Skip keynotes and non-talk content
        skip_patterns = ["keynote", "dev build", "welcome to"]
        if any(p in title.lower() for p in skip_patterns):
            continue

        talk = {
            "objectID": object_id,
            "title": clean_title or title,
            "speaker": speaker,
            "speakers": [speaker] if speaker else [],
            "conference_name": f"Algolia DevCon {year}" if year else "Algolia DevCon",
            "conference_id": f"algolia-devcon-{year}" if year else "algolia-devcon",
            "year": year,
            "url": video.get("url"),
            "view_count": video.get("view_count", 0),
            "duration": video.get("duration", 0),
            "topics": ["Search", "Algolia"],
            "is_devcon": True,
        }

        talks_to_add.append(talk)

    print(f"\nFound {len(talks_to_add)} new DevCon talks to add")

    if not talks_to_add:
        print("No new talks to add!")
        return

    # Show what we're adding
    print("\nTalks to add:")
    for talk in talks_to_add:
        print(f"  [{talk['objectID']}] {talk['title'][:50]}...")
        print(f"     Speaker: {talk['speaker'] or 'Unknown'}")
        print(f"     Year: {talk['year']}")

    # Confirm
    response = input(f"\nAdd {len(talks_to_add)} talks to index? [y/N]: ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return

    # Index talks
    print("\nIndexing talks...")
    client.save_objects("cfps_talks", talks_to_add)
    print(f"[OK] Added {len(talks_to_add)} DevCon talks!")


if __name__ == "__main__":
    main()
