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


def _get_best_thumbnail(entry: dict) -> Optional[str]:
    """Extract best thumbnail URL from yt-dlp entry.

    yt-dlp returns 'thumbnail' for full extracts but only 'thumbnails' array
    for flat/search extracts. This handles both cases.
    """
    # Try singular first (works in full extraction mode)
    if entry.get('thumbnail'):
        return entry['thumbnail']

    # Fall back to thumbnails array (search/flat mode)
    thumbnails = entry.get('thumbnails') or []
    if not thumbnails:
        return None

    # Prefer higher resolution thumbnails
    # Sort by height (descending) and pick the best one
    sorted_thumbs = sorted(
        [t for t in thumbnails if t.get('url')],
        key=lambda t: t.get('height', 0),
        reverse=True
    )
    return sorted_thumbs[0]['url'] if sorted_thumbs else None


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
    """Synchronous YouTube search using yt-dlp (flat mode for speed)."""
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Fast search
        'skip_download': True,
        'ignoreerrors': True,
        'default_search': 'ytsearch',
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch{max_results}:{query}"
            info = ydl.extract_info(search_query, download=False)

            if not info or 'entries' not in info:
                return []

            for entry in info['entries']:
                if not entry:
                    continue

                year = None
                upload_date = entry.get('upload_date')
                if upload_date and len(upload_date) >= 4:
                    try:
                        year = int(upload_date[:4])
                    except ValueError:
                        pass

                title = entry.get('title', '')
                clean_title, speaker = _extract_speaker_from_title(title)
                video_id = entry.get('id', '')
                video_url = entry.get('url') or entry.get('webpage_url')
                if not video_url and video_id:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

                results.append({
                    'id': video_id,
                    'title': clean_title,
                    'original_title': title,
                    'speaker': speaker,
                    'description': (entry.get('description') or '')[:500],
                    'url': video_url,
                    'thumbnail_url': _get_best_thumbnail(entry),
                    'year': year,
                    'duration_seconds': entry.get('duration'),
                    'view_count': entry.get('view_count'),
                    'channel': entry.get('channel') or entry.get('uploader'),
                    'channel_url': entry.get('channel_url'),
                    'tags': [],
                    'categories': [],
                    'like_count': None,
                    'comment_count': None,
                })

    except Exception as e:
        console.print(f"[dim]YouTube search error: {e}[/dim]")
        return []

    return results


def _fetch_video_details(video_ids: list[str]) -> dict[str, dict]:
    """Fetch full details for specific videos (slower but gets descriptions)."""
    import yt_dlp

    if not video_ids:
        return {}

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,
    }

    details = {}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for vid in video_ids[:20]:  # Limit to avoid slowdown
                try:
                    url = f"https://www.youtube.com/watch?v={vid}"
                    info = ydl.extract_info(url, download=False)
                    if info:
                        details[vid] = {
                            'description': (info.get('description') or '')[:2000],
                            'duration_seconds': info.get('duration'),
                            'view_count': info.get('view_count'),
                            'like_count': info.get('like_count'),
                            'comment_count': info.get('comment_count'),
                            'tags': (info.get('tags') or [])[:20],
                            'categories': info.get('categories') or [],
                            'channel': info.get('channel') or info.get('uploader'),
                            'channel_url': info.get('channel_url'),
                            'upload_date': info.get('upload_date'),
                        }
                except Exception:
                    continue
    except Exception as e:
        console.print(f"[dim]Video details fetch error: {e}[/dim]")

    return details


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
    # Add "conference" and tech keywords to avoid music B-sides results
    tech_keywords = "conference OR tech OR developer OR programming OR software"
    exclude_music = "-music -band -song -album -remix -live -concert -tour"

    if years:
        results_per_year = max(10, max_results // len(years))
        for year in years:
            # More specific query with conference context and music exclusion
            query = f'"{clean_name}" {year} ({tech_keywords}) {exclude_music}'
            console.print(f"[dim]  Searching: '{query}'[/dim]")
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                _executor, _search_youtube_sync, query, results_per_year + 5
            )
            all_results.extend(results)
    else:
        # Search without year filter
        query = f'"{clean_name}" ({tech_keywords}) {exclude_music}'
        console.print(f"[dim]  Searching: '{query}'[/dim]")
        loop = asyncio.get_event_loop()
        all_results = await loop.run_in_executor(
            _executor, _search_youtube_sync, query, max_results + 20
        )

    # Filter out non-talks
    filtered = []
    seen_urls = set()

    # Music/entertainment/spam keywords to filter out
    blocked_keywords = ['official video', 'music video', 'lyric video', 'audio only',
                        'full album', 'greatest hits', 'best of', 'remaster', 'unplugged',
                        'mtv', 'vevo', 'gun show', 'guns n roses', 'oasis', 'apex legends',
                        'beginner guide', 'gaming', 'chromebook', 'amazon shipment', 'vanlife',
                        'tawheed', 'allah', 'career advice', 'highest paying', 'get rich',
                        'how to beat', 'slasher', 'walkthrough', 'gameplay', 'playthrough',
                        'cnc design', 'ultimate guide', 'before 2025', 'before 2026',
                        'tutorial for beginners', 'course for beginners', 'easy business',
                        'make money', 'side hustle', 'passive income', 'dropshipping']

    # Tech keywords - title/channel should contain at least one of these
    # Note: "conference" alone is too broad (matches video games), require more specific terms
    tech_indicators = ['tech talk', 'presentation', 'keynote', 'session', 'meetup',
                       'developer', 'programming', 'software', 'api', 'cloud',
                       'kubernetes', 'docker', 'devops', 'infosec', 'cybersecurity',
                       'python', 'javascript', 'java', 'react', 'node', 'rust',
                       'golang', 'typescript', 'microservices', 'architecture',
                       'machine learning', 'deep learning', 'data science',
                       'database', 'sql', 'nosql', 'backend', 'frontend', 'fullstack',
                       'aws', 'azure', 'gcp', 'linux', 'open source', 'github',
                       'cncf', 'hashicorp', 'terraform', 'ansible', 'jenkins',
                       'pycon', 'kubecon', 'jsconf', 'rustconf', 'gophercon',
                       'devoxx', 'qcon', 'strangeloop', 'fosdem', 'defcon', 'bsides']

    for r in all_results:
        url = r.get('url', '')
        if url in seen_urls:
            continue
        seen_urls.add(url)

        duration = r.get('duration_seconds') or 0
        title_lower = r.get('original_title', '').lower()
        channel_lower = (r.get('channel') or '').lower()
        description_lower = (r.get('description') or '').lower()
        view_count = r.get('view_count') or 0

        # Skip short videos (conference talks are usually 15+ minutes)
        if duration > 0 and duration < 600:
            continue

        # Skip videos with suspiciously high view counts (500K is generous for tech talks)
        if view_count > 500_000:
            continue

        # Skip music/entertainment/spam content
        if any(kw in title_lower for kw in blocked_keywords):
            continue
        if any(kw in channel_lower for kw in ['vevo', 'music', 'records', 'entertainment', 'gaming']):
            continue

        # Skip non-talks
        skip_keywords = ['trailer', 'teaser', 'promo', 'highlight', 'aftermovie', 'recap', 'shorts']
        if any(kw in title_lower for kw in skip_keywords):
            continue

        # REQUIRE at least one tech indicator in title, description, or channel
        has_tech_indicator = (
            any(kw in title_lower for kw in tech_indicators) or
            any(kw in description_lower for kw in tech_indicators) or
            any(kw in channel_lower for kw in tech_indicators)
        )
        if not has_tech_indicator:
            continue

        filtered.append(r)

    # Sort by views
    filtered.sort(key=lambda x: x.get('view_count') or 0, reverse=True)

    # Limit results
    filtered = filtered[:max_results]

    # Fetch full details for top talks (to get descriptions)
    # Only fetch details for top 10 to avoid slowdown
    top_video_ids = [r.get('id') for r in filtered[:10] if r.get('id')]
    if top_video_ids:
        console.print(f"[dim]  Fetching details for top {len(top_video_ids)} talks...[/dim]")
        loop = asyncio.get_event_loop()
        details = await loop.run_in_executor(_executor, _fetch_video_details, top_video_ids)

        # Merge details back
        for r in filtered:
            vid = r.get('id')
            if vid and vid in details:
                d = details[vid]
                r['description'] = d.get('description') or r.get('description', '')
                r['duration_seconds'] = d.get('duration_seconds') or r.get('duration_seconds')
                r['view_count'] = d.get('view_count') or r.get('view_count')
                r['like_count'] = d.get('like_count')
                r['comment_count'] = d.get('comment_count')
                r['tags'] = d.get('tags', [])
                r['categories'] = d.get('categories', [])
                r['channel'] = d.get('channel') or r.get('channel')
                # Extract year from upload_date if available
                upload_date = d.get('upload_date')
                if upload_date and len(upload_date) >= 4:
                    try:
                        r['year'] = int(upload_date[:4])
                    except ValueError:
                        pass

    # Convert to Talk objects
    talks = [
        _youtube_result_to_talk(r, conference_id, conference_name)
        for r in filtered
    ]

    console.print(f"[dim]  Found {len(talks)} talks for {conference_name}[/dim]")
    return talks


def fetch_video_by_url(url: str) -> Optional[dict]:
    """Fetch full video details for a specific YouTube URL.

    Args:
        url: YouTube video URL (e.g., https://youtube.com/watch?v=xxx)

    Returns:
        Dict with video details or None if failed
    """
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            # Extract year from upload_date
            year = None
            upload_date = info.get('upload_date')
            if upload_date and len(upload_date) >= 4:
                try:
                    year = int(upload_date[:4])
                except ValueError:
                    pass

            title = info.get('title', '')
            clean_title, speaker = _extract_speaker_from_title(title)

            return {
                'id': info.get('id', ''),
                'title': clean_title,
                'original_title': title,
                'speaker': speaker,
                'description': (info.get('description') or '')[:2000],
                'url': info.get('webpage_url') or url,
                'thumbnail_url': _get_best_thumbnail(info),
                'year': year,
                'duration_seconds': info.get('duration'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'comment_count': info.get('comment_count'),
                'channel': info.get('channel') or info.get('uploader'),
                'channel_url': info.get('channel_url'),
                'tags': (info.get('tags') or [])[:20],
                'categories': info.get('categories') or [],
            }
    except Exception as e:
        console.print(f"[dim]Error fetching {url}: {e}[/dim]")
        return None


async def fetch_talks_by_urls(
    urls: list[dict],  # List of {"url": str, "conference_id": str, "conference_name": str, "speaker"?: str}
    max_concurrent: int = 3,
) -> list[Talk]:
    """Fetch talks from specific YouTube URLs.

    Args:
        urls: List of dicts with url, conference_id, conference_name, optional speaker override
        max_concurrent: Max concurrent fetches

    Returns:
        List of Talk objects
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    loop = asyncio.get_event_loop()
    talks = []

    async def fetch_one(item: dict) -> Optional[Talk]:
        async with semaphore:
            url = item['url']
            result = await loop.run_in_executor(_executor, fetch_video_by_url, url)
            if not result:
                return None

            # Override speaker if provided
            if item.get('speaker'):
                result['speaker'] = item['speaker']

            return _youtube_result_to_talk(
                result,
                item['conference_id'],
                item['conference_name'],
            )

    tasks = [fetch_one(item) for item in urls]

    for coro in asyncio.as_completed(tasks):
        talk = await coro
        if talk:
            talks.append(talk)
            console.print(f"[green]  ✓ {talk.title[:50]}...[/green]")
        else:
            console.print(f"[yellow]  ✗ Failed to fetch a URL[/yellow]")

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
