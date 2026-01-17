"""YouTube talk search using yt-dlp (no API key needed).

Searches for conference talks on YouTube to help speakers understand
what kind of content gets presented at each conference.

Supports two modes:
1. ExampleTalk (simple) - for embedding in CFP records
2. Talk (full) - for separate talks index with conference FK
"""

import asyncio
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from rich.console import Console

from cfp_pipeline.enrichers.schema import ExampleTalk
from cfp_pipeline.models.talk import Talk

console = Console()

# Thread pool for yt-dlp (it's synchronous)
_executor = ThreadPoolExecutor(max_workers=4)


def _extract_speaker_from_title(title: str) -> tuple[str, Optional[str]]:
    """Try to extract speaker name from talk title.

    Common patterns:
    - "Talk Title - Speaker Name"
    - "Talk Title | Speaker Name"
    - "Speaker Name: Talk Title"
    - "Talk Title by Speaker Name"
    """
    # Pattern: "Title - Speaker" or "Title | Speaker"
    match = re.search(r'^(.+?)\s*[-|]\s*([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$', title)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Pattern: "Speaker: Title"
    match = re.search(r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s*(.+)$', title)
    if match:
        return match.group(2).strip(), match.group(1).strip()

    # Pattern: "Title by Speaker"
    match = re.search(r'^(.+?)\s+by\s+([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$', title, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return title, None


def _search_youtube_sync(query: str, max_results: int = 10) -> list[dict]:
    """Synchronous YouTube search using yt-dlp."""
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Don't download, just get metadata
        'skip_download': True,
        'ignoreerrors': True,
        'default_search': 'ytsearch',
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search YouTube
            search_query = f"ytsearch{max_results}:{query}"
            info = ydl.extract_info(search_query, download=False)

            if not info or 'entries' not in info:
                return []

            for entry in info['entries']:
                if not entry:
                    continue

                # Extract year from upload date
                year = None
                upload_date = entry.get('upload_date')  # YYYYMMDD format
                if upload_date and len(upload_date) >= 4:
                    try:
                        year = int(upload_date[:4])
                    except ValueError:
                        pass

                # Parse title for speaker
                title = entry.get('title', '')
                clean_title, speaker = _extract_speaker_from_title(title)

                results.append({
                    'title': clean_title,
                    'original_title': title,
                    'speaker': speaker,
                    'description': (entry.get('description') or '')[:500],
                    'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                    'thumbnail_url': entry.get('thumbnail'),
                    'year': year,
                    'duration_seconds': entry.get('duration'),
                    'view_count': entry.get('view_count'),
                    'channel': entry.get('channel') or entry.get('uploader'),
                })

    except Exception as e:
        console.print(f"[dim]YouTube search error: {e}[/dim]")
        return []

    return results


async def search_conference_talks(
    conference_name: str,
    max_results: int = 10,
    year: Optional[int] = None,
) -> list[ExampleTalk]:
    """Search YouTube for talks from a conference.

    Args:
        conference_name: Name of the conference (e.g., "PyCon US", "KubeCon")
        max_results: Maximum number of results to return
        year: Optional year to filter by (searches for "conference 2024" etc.)

    Returns:
        List of ExampleTalk objects sorted by view count
    """
    # Build search query
    query_parts = [conference_name, "conference talk"]
    if year:
        query_parts.insert(1, str(year))
    query = " ".join(query_parts)

    console.print(f"[dim]  Searching YouTube: '{query}'[/dim]")

    # Run sync search in thread pool
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, _search_youtube_sync, query, max_results + 5)

    if not results:
        # Try simpler query without "conference talk"
        query = f"{conference_name} talk"
        if year:
            query = f"{conference_name} {year} talk"
        results = await loop.run_in_executor(_executor, _search_youtube_sync, query, max_results + 5)

    # Filter out non-talk content (shorts, trailers, etc.)
    filtered = []
    for r in results:
        duration = r.get('duration_seconds') or 0
        title_lower = r.get('original_title', '').lower()

        # Skip very short videos (probably not full talks)
        if duration > 0 and duration < 300:  # Less than 5 minutes
            continue

        # Skip obvious non-talks
        skip_keywords = ['trailer', 'teaser', 'promo', 'highlight', 'aftermovie', 'recap']
        if any(kw in title_lower for kw in skip_keywords):
            continue

        filtered.append(r)

    # Sort by view count (most popular first)
    filtered.sort(key=lambda x: x.get('view_count') or 0, reverse=True)

    # Convert to ExampleTalk objects
    talks = []
    for r in filtered[:max_results]:
        talks.append(ExampleTalk(
            title=r['title'],
            speaker=r.get('speaker'),
            description=r.get('description'),
            url=r['url'],
            thumbnail_url=r.get('thumbnail_url'),
            year=r.get('year'),
            duration_seconds=r.get('duration_seconds'),
            view_count=r.get('view_count'),
            channel=r.get('channel'),
        ))

    console.print(f"[dim]  Found {len(talks)} talks[/dim]")
    return talks


async def search_talks_batch(
    conferences: list[tuple[str, Optional[int]]],  # (name, year) tuples
    max_results_per_conf: int = 10,
    max_concurrent: int = 3,
) -> dict[str, list[ExampleTalk]]:
    """Search for talks from multiple conferences in parallel.

    Args:
        conferences: List of (conference_name, year) tuples
        max_results_per_conf: Max talks per conference
        max_concurrent: Max concurrent searches

    Returns:
        Dict mapping conference name to list of talks
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, list[ExampleTalk]] = {}

    async def search_one(name: str, year: Optional[int]) -> tuple[str, list[ExampleTalk]]:
        async with semaphore:
            talks = await search_conference_talks(name, max_results_per_conf, year)
            return name, talks

    tasks = [search_one(name, year) for name, year in conferences]

    for coro in asyncio.as_completed(tasks):
        name, talks = await coro
        results[name] = talks

    return results


# ===== TALK INDEX FUNCTIONS (with conference FK) =====


def _slugify(name: str) -> str:
    """Convert conference name to URL-friendly slug."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def _youtube_result_to_talk(
    result: dict,
    conference_id: str,
    conference_name: str,
) -> Talk:
    """Convert raw YouTube result to Talk model with conference FK."""
    video_id = result.get('url', '').split('v=')[-1].split('&')[0]
    if not video_id or video_id == result.get('url'):
        # Extract from URL differently
        video_id = hashlib.sha256(result.get('url', '').encode()).hexdigest()[:12]

    # Parse speakers (could be multiple)
    speaker = result.get('speaker')
    speakers = [speaker] if speaker else []

    return Talk(
        objectID=f"yt_{video_id}",
        conference_id=conference_id,
        conference_name=conference_name,
        conference_slug=_slugify(conference_name),
        title=result['title'],
        speaker=speaker,
        speakers=speakers,
        description=result.get('description'),
        url=result['url'],
        thumbnail_url=result.get('thumbnail_url'),
        channel=result.get('channel'),
        duration_seconds=result.get('duration_seconds'),
        view_count=result.get('view_count'),
        year=result.get('year'),
        topics=[],  # TODO: infer from title/description
        languages=[],  # TODO: infer from title/description
    )


async def fetch_talks_for_conference(
    conference_id: str,
    conference_name: str,
    max_results: int = 100,
    years: Optional[list[int]] = None,
) -> list[Talk]:
    """Fetch talks for a conference and return Talk objects for indexing.

    Args:
        conference_id: Conference objectID (FK)
        conference_name: Conference name for search
        max_results: Total max talks to return
        years: Optional list of years to search (e.g., [2023, 2024, 2025])

    Returns:
        List of Talk objects ready for Algolia indexing
    """
    all_results = []

    # Clean conference name - remove year if present (e.g., "KubeCon 2026" -> "KubeCon")
    clean_name = re.sub(r'\s*20\d{2}\s*', ' ', conference_name).strip()

    # Search across multiple years if provided
    if years:
        results_per_year = max(10, max_results // len(years))
        for year in years:
            # More specific query: "conference name" in quotes + year + presentation/talk
            query = f'"{clean_name}" {year} presentation OR talk OR keynote'
            console.print(f"[dim]  Searching: '{query}'[/dim]")
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                _executor, _search_youtube_sync, query, results_per_year + 5
            )
            all_results.extend(results)
    else:
        # Search without year filter
        query = f'"{clean_name}" conference presentation OR talk'
        console.print(f"[dim]  Searching: '{query}'[/dim]")
        loop = asyncio.get_event_loop()
        all_results = await loop.run_in_executor(
            _executor, _search_youtube_sync, query, max_results + 20
        )

    # Filter out non-talks
    filtered = []
    seen_urls = set()

    for r in all_results:
        url = r.get('url', '')
        if url in seen_urls:
            continue
        seen_urls.add(url)

        duration = r.get('duration_seconds') or 0
        title_lower = r.get('original_title', '').lower()

        # Skip short videos
        if duration > 0 and duration < 300:
            continue

        # Skip non-talks
        skip_keywords = ['trailer', 'teaser', 'promo', 'highlight', 'aftermovie', 'recap', 'shorts']
        if any(kw in title_lower for kw in skip_keywords):
            continue

        filtered.append(r)

    # Sort by views
    filtered.sort(key=lambda x: x.get('view_count') or 0, reverse=True)

    # Convert to Talk objects
    talks = [
        _youtube_result_to_talk(r, conference_id, conference_name)
        for r in filtered[:max_results]
    ]

    console.print(f"[dim]  Found {len(talks)} talks for {conference_name}[/dim]")
    return talks


async def fetch_talks_for_conferences(
    conferences: list[dict],  # List of {"id": str, "name": str}
    max_results_per_conf: int = 100,
    years: Optional[list[int]] = None,
    max_concurrent: int = 2,
) -> list[Talk]:
    """Fetch talks for multiple conferences in parallel.

    Args:
        conferences: List of dicts with 'id' and 'name' keys
        max_results_per_conf: Max talks per conference
        years: Years to search across
        max_concurrent: Max concurrent YouTube searches

    Returns:
        List of all Talk objects
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    all_talks: list[Talk] = []

    async def fetch_one(conf: dict) -> list[Talk]:
        async with semaphore:
            return await fetch_talks_for_conference(
                conference_id=conf['id'],
                conference_name=conf['name'],
                max_results=max_results_per_conf,
                years=years,
            )

    tasks = [fetch_one(conf) for conf in conferences]

    for coro in asyncio.as_completed(tasks):
        talks = await coro
        all_talks.extend(talks)
        console.print(f"[green]  +{len(talks)} talks[/green]")

    return all_talks
