"""Algolia indexer for conference speakers."""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from algoliasearch.search.client import SearchClientSync
from rich.console import Console

from cfp_pipeline.models.speaker import Speaker, speaker_to_algolia, slugify_name

console = Console()


# ===== ALGOLIA SPEAKERS DATA =====
# Load known Algolia speakers for name resolution and flagging
_ALGOLIA_SPEAKERS_DATA: Optional[dict] = None
_NAME_ALIASES: dict[str, str] = {}
_ALGOLIA_SPEAKER_IDS: set[str] = set()


def _load_algolia_speakers() -> None:
    """Load Algolia speakers data from JSON file."""
    global _ALGOLIA_SPEAKERS_DATA, _NAME_ALIASES, _ALGOLIA_SPEAKER_IDS

    if _ALGOLIA_SPEAKERS_DATA is not None:
        return  # Already loaded

    data_path = Path(__file__).parent.parent.parent / "data" / "algolia_speakers.json"
    if not data_path.exists():
        console.print(f"[yellow]Warning: Algolia speakers data not found at {data_path}[/yellow]")
        _ALGOLIA_SPEAKERS_DATA = {"speakers": [], "name_aliases": {}}
        return

    with open(data_path) as f:
        _ALGOLIA_SPEAKERS_DATA = json.load(f)

    # Build name alias map: alias_slug -> canonical_slug
    _NAME_ALIASES = _ALGOLIA_SPEAKERS_DATA.get("name_aliases", {})

    # Also add aliases from speaker records
    for speaker in _ALGOLIA_SPEAKERS_DATA.get("speakers", []):
        canonical = slugify_name(speaker["name"])
        _ALGOLIA_SPEAKER_IDS.add(canonical)
        for alias in speaker.get("aliases", []):
            if alias != canonical:
                _NAME_ALIASES[alias] = canonical

    console.print(f"[dim]Loaded {len(_ALGOLIA_SPEAKER_IDS)} Algolia speakers, {len(_NAME_ALIASES)} aliases[/dim]")


def resolve_speaker_name(name: str) -> tuple[str, str]:
    """Resolve speaker name to canonical form.

    Returns:
        Tuple of (canonical_slug, display_name)
    """
    _load_algolia_speakers()

    slug = slugify_name(name)

    # Check if this slug is an alias
    if slug in _NAME_ALIASES:
        canonical_slug = _NAME_ALIASES[slug]
        # Find the canonical display name
        for speaker in _ALGOLIA_SPEAKERS_DATA.get("speakers", []):
            if slugify_name(speaker["name"]) == canonical_slug:
                return canonical_slug, speaker["name"]
        return canonical_slug, name  # Fallback to original name

    return slug, name


def is_algolia_speaker(slug: str) -> bool:
    """Check if a speaker slug belongs to an Algolia employee."""
    _load_algolia_speakers()
    return slug in _ALGOLIA_SPEAKER_IDS

# Names that are obviously not real speakers (exact match only - no substring matching
# to avoid blocking pseudonyms like "Mr Robot" or "Sarah Systems")
BLOCKED_SPEAKER_NAMES = {
    # Generic event types
    "all keynotes", "tech talk", "tech session", "virtual event",
    "dev room", "main stage", "workshop", "tutorial", "panel",
    "lightning talk", "demo", "keynote", "opening", "closing",
    "live stream", "full talk", "conference talk", "tech talks",
    # Technical terms mistakenly parsed as names
    "functional programming", "java programs interview", "rust dev room",
    "system design", "data structure", "world example", "spring history",
    "maximum efficiency", "the download", "react admin", "azure malayalam",
    "unlocking digital", "code play repeat", "memory safety", "interview java",
    "java interview", "python interview", "coding interview", "technical interview",
    "programming tutorial", "coding tutorial", "web development", "software engineering",
    "software development", "full stack", "front end", "back end", "api design",
    # Common false patterns (Title Case phrases)
    "applied psychology", "the carbon language", "platform engineering",
    "cloud native", "machine learning", "deep learning", "artificial intelligence",
    "open source", "best practices", "design patterns", "code review",
    "distributed systems", "microservices architecture", "event sourcing",
    "domain driven design", "test driven development", "behavior driven development",
    # Channel/playlist names
    "strange loop", "goto conference", "devoxx", "qcon", "infoq",
    "tech world", "developer advocate", "devrel", "community",
    # Common YouTube title fragments
    "part one", "part two", "part 1", "part 2", "episode 1", "episode 2",
    "day one", "day two", "day 1", "day 2", "session 1", "session 2",
    "complete guide", "crash course", "deep dive", "getting started",
    "introduction to", "beginner guide", "advanced guide", "ultimate guide",
}


def get_speakers_index_name() -> str:
    """Get speakers index name from env or default."""
    base = os.environ.get("ALGOLIA_INDEX_NAME", "cfps")
    return f"{base}_speakers"  # e.g., "cfps_speakers"


def configure_speakers_index(client: SearchClientSync, index_name: Optional[str] = None) -> None:
    """Configure speakers index settings for optimal search."""
    index_name = index_name or get_speakers_index_name()

    settings = {
        # Searchable attributes (priority order)
        "searchableAttributes": [
            "name",
            "aliases",
            "company",
            "topics",
            "conferences",
        ],

        # Facets for filtering
        "attributesForFaceting": [
            "searchable(company)",
            "searchable(topics)",
            "searchable(conferences)",
            "filterOnly(achievements)",
            "filterOnly(is_algolia_speaker)",
            "years_active",
        ],

        # Custom ranking - influence first, then views, then activity
        "customRanking": [
            "desc(influence_score)",
            "desc(total_views)",
            "desc(talk_count)",
            "desc(active_years)",
        ],

        # Highlighting
        "attributesToHighlight": [
            "name",
            "company",
            "topics",
        ],

        # Return these attributes
        "attributesToRetrieve": [
            "objectID",
            "name",
            "aliases",
            "company",
            "is_algolia_speaker",
            "talk_count",
            "total_views",
            "max_views",
            "avg_views",
            "years_active",
            "first_talk_year",
            "latest_talk_year",
            "active_years",
            "topics",
            "conferences",
            "conference_count",
            "top_talk_ids",
            "influence_score",
            "consistency_score",
            "achievements",
            "profile_url",
            "twitter",
            "github",
        ],
    }

    console.print(f"[cyan]Configuring speakers index: {index_name}[/cyan]")
    client.set_settings(index_name, settings)
    console.print("[green]Speakers index configured[/green]")


def index_speakers(
    client: SearchClientSync,
    speakers: list[Speaker],
    index_name: Optional[str] = None,
) -> int:
    """Index speakers to Algolia.

    Args:
        client: Algolia client
        speakers: List of Speaker objects
        index_name: Optional index name override

    Returns:
        Number of speakers indexed
    """
    index_name = index_name or get_speakers_index_name()

    if not speakers:
        console.print("[yellow]No speakers to index[/yellow]")
        return 0

    # Convert to Algolia records
    records = [speaker_to_algolia(speaker) for speaker in speakers]

    console.print(f"[cyan]Indexing {len(records)} speakers to {index_name}...[/cyan]")

    # Batch save
    client.save_objects(index_name, records)

    console.print(f"[green]Indexed {len(records)} speakers[/green]")
    return len(records)


def build_speakers_from_talks(
    client: SearchClientSync,
    talks_index: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Speaker]:
    """Build Speaker objects by aggregating talks from the talks index.

    Args:
        client: Algolia client
        talks_index: Talks index name (default: cfps_talks)
        limit: Max speakers to return (None = all)

    Returns:
        List of Speaker objects with aggregated stats
    """
    from cfp_pipeline.indexers.talks import get_talks_index_name

    talks_index = talks_index or get_talks_index_name()

    console.print(f"[cyan]Building speakers from {talks_index}...[/cyan]")

    # Fetch ALL talks using browse (no 1000 limit like search)
    all_talks: list[dict] = []

    # Use browse_objects with aggregator callback to iterate entire index
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=[
            "objectID",
            "speaker",
            "speakers",
            "conference_name",
            "view_count",
            "year",
            "topics",
            "title",
        ],
        hits_per_page=1000,
    )

    def aggregator(response):
        """Callback to collect hits from each browse page."""
        for hit in response.hits:
            talk_dict = {
                "objectID": getattr(hit, "object_id", None) or getattr(hit, "objectID", None),
                "speaker": getattr(hit, "speaker", None),
                "speakers": getattr(hit, "speakers", []) or [],
                "conference_name": getattr(hit, "conference_name", None),
                "view_count": getattr(hit, "view_count", 0),
                "year": getattr(hit, "year", None),
                "topics": getattr(hit, "topics", []) or [],
                "title": getattr(hit, "title", None),
            }
            all_talks.append(talk_dict)

    # Browse entire index
    client.browse_objects(talks_index, aggregator, browse_params)

    console.print(f"[dim]Fetched {len(all_talks)} talks[/dim]")

    # Group by speaker
    speaker_data: dict[str, dict] = defaultdict(lambda: {
        "names": set(),
        "talks": [],
        "views": 0,
        "max_views": 0,
        "years": set(),
        "topics": defaultdict(int),
        "conferences": defaultdict(int),
    })

    for talk in all_talks:
        # Get speaker(s) from talk
        speaker_name = talk.get("speaker")
        speakers_list = talk.get("speakers", [])

        # Collect all speaker names for this talk
        names_to_process = []
        if speaker_name:
            names_to_process.append(speaker_name)
        names_to_process.extend(speakers_list)

        # Dedupe
        names_to_process = list(set(names_to_process))

        for name in names_to_process:
            if not name or len(name) < 2:
                continue

            # Filter out obvious non-speaker names (exact match only to avoid blocking pseudonyms)
            name_lower = name.lower().strip()
            if name_lower in BLOCKED_SPEAKER_NAMES:
                continue

            # Resolve name to canonical form (handles aliases like "Louis Nech" -> "Paul-Louis Nech")
            key, resolved_name = resolve_speaker_name(name)
            if not key:
                continue

            data = speaker_data[key]
            # Add both original and resolved names for alias tracking
            data["names"].add(name)
            if resolved_name != name:
                data["names"].add(resolved_name)
            data["talks"].append(talk)

            views = talk.get("view_count") or 0
            data["views"] += views
            data["max_views"] = max(data["max_views"], views)

            year = talk.get("year")
            if year:
                data["years"].add(year)

            conf = talk.get("conference_name")
            if conf:
                data["conferences"][conf] += 1

            for topic in talk.get("topics", []):
                data["topics"][topic] += 1

    console.print(f"[dim]Found {len(speaker_data)} unique speakers[/dim]")

    # Build Speaker objects
    speakers = []
    for key, data in speaker_data.items():
        # Pick the most common name variant
        names = list(data["names"])
        name = max(names, key=len) if names else key

        # Sort topics by count
        sorted_topics = sorted(data["topics"].items(), key=lambda x: -x[1])
        top_topics = [t[0] for t in sorted_topics[:10]]

        # Sort conferences by count
        sorted_confs = sorted(data["conferences"].items(), key=lambda x: -x[1])
        conferences = [c[0] for c in sorted_confs]

        # Get top talks by views
        talks_sorted = sorted(data["talks"], key=lambda t: t.get("view_count") or 0, reverse=True)
        top_talk_ids = [t["objectID"] for t in talks_sorted[:5]]
        all_talk_ids = [t["objectID"] for t in talks_sorted]

        years = sorted(data["years"]) if data["years"] else []

        # Check if this is an Algolia speaker
        algolia_speaker = is_algolia_speaker(key)

        speaker = Speaker(
            objectID=key,
            name=name,
            aliases=[n for n in names if n != name],
            is_algolia_speaker=algolia_speaker,
            talk_count=len(data["talks"]),
            total_views=data["views"],
            max_views=data["max_views"],
            years_active=years,
            first_talk_year=years[0] if years else None,
            latest_talk_year=years[-1] if years else None,
            topics=top_topics,
            topic_counts=dict(sorted_topics),
            conferences=conferences,
            conference_counts=dict(sorted_confs),
            top_talk_ids=top_talk_ids,
            all_talk_ids=all_talk_ids,
        )

        # Recompute achievements after stats are set
        speaker.achievements = speaker.compute_achievements()

        speakers.append(speaker)

    # Sort by influence score
    speakers.sort(key=lambda s: s.influence_score, reverse=True)

    if limit:
        speakers = speakers[:limit]

    console.print(f"[green]Built {len(speakers)} speaker profiles[/green]")
    return speakers


def get_speakers_stats(
    client: SearchClientSync,
    index_name: Optional[str] = None,
) -> dict:
    """Get speakers index statistics."""
    index_name = index_name or get_speakers_index_name()

    try:
        # Search for count
        results = client.search_single_index(
            index_name,
            {"query": "", "hitsPerPage": 0}
        )

        return {
            "index_name": index_name,
            "num_speakers": results.nb_hits,
        }
    except Exception as e:
        return {"error": str(e)}


def get_top_speakers(
    client: SearchClientSync,
    limit: int = 10,
    index_name: Optional[str] = None,
    topic: Optional[str] = None,
) -> list[dict]:
    """Get top speakers by influence score.

    Args:
        client: Algolia client
        limit: Max speakers to return
        index_name: Optional index name override
        topic: Optional topic filter

    Returns:
        List of speaker records
    """
    index_name = index_name or get_speakers_index_name()

    params = {
        "query": "",
        "hitsPerPage": limit,
    }

    if topic:
        params["filters"] = f"topics:{topic}"

    results = client.search_single_index(index_name, params)
    return results.hits


def clear_speakers_index(
    client: SearchClientSync,
    index_name: Optional[str] = None,
) -> None:
    """Clear all speakers from index."""
    index_name = index_name or get_speakers_index_name()
    console.print(f"[yellow]Clearing speakers index: {index_name}[/yellow]")
    client.clear_objects(index_name)
    console.print("[green]Speakers index cleared[/green]")
