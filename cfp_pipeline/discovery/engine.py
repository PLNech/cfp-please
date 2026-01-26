"""Discovery engine for speaker-aware talk discovery.

Implements graph-based discovery with BFS expansion:
- Start with seed speakers
- Find their talks → discover channels
- For each channel → find speakers who speak there
- For each new speaker → find their talks
- Continue until saturation or limits reached

The discovery list is stored locally for --explore deep dives.
"""

import asyncio
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console

from cfp_pipeline.enrichers.youtube import (
    search_talks_by_speaker,
    search_speakers_batch,
    _search_youtube_sync,
    _executor,
)
from cfp_pipeline.models.talk import Talk

console = Console()

DISCOVERY_DATA_DIR = Path(__file__).parent.parent / "data" / "discovery"
DISCOVERY_LIST_FILE = DISCOVERY_DATA_DIR / "discovered.json"

# Speakers that are definitely NOT real people (extracted from titles incorrectly)
_BLOCKED_SPEAKER_PATTERNS = [
    r'^build\s+stage$',
    r'^transform\s+stage$',
    r'^main\s+stage$',
    r'^lightning\s+talks?$',
    r'^conference\s+talk',
    r'^keynote\s+',
    r'^tech\s+talk',
    r'^workshop\s+',
    r'^talk\s+',
    r'^session\s+',
    r'^panel\s+',
    r'^intro(dduction)?\s+to\s+',
    r'^how\s+to\s+',
    r'^what\s+is\s+',
    r'^why\s+',
    r'^building\s+',
    r'^running\s+',
    r'^getting\s+started',
    r'^deep\s+dive',
    r'^beginner',
    r'^advanced',
    r'^crash\s+course',
    r'^complete\s+guide',
    r'^ultimate\s+guide',
    r'^practical\s+',
    r'^real-world\s+',
    r'^scale?\s+',
    r'^grade\s+',
    r'^exceptional\s+',
    r'^english\s+speaking',
    r'^compiling\s+your\s+',
    r'^data\s+mesh',
    r'^data\s+engineering',
    r'^machine\s+learning',
    r'^cloud\s+native',
    r'^serverless',
    r'^microservices',
    r'^devops',
    r'^ci/cd',
    r'^agile',
    r'^scrum',
    r'^kanban',
    r'^productivity',
    r'^time\s+management',
    r'^coding\s+',
    r'^programming\s+',
    r'^software\s+',
    r'^system\s+design',
    r'^api\s+',
    r'^frontend\s+',
    r'^backend\s+',
    r'^fullstack',
    r'^database\s+',
    r'^sql\s+',
    r'^nosql',
    r'^aws\s+',
    r'^azure\s+',
    r'^gcp\s+',
    r'^kubernetes',
    r'^docker',
    r'^terraform',
    r'^ansible',
    r'^jenkins',
    r'^github',
    r'^git',
    r'^linux',
    r'^unix',
    r'^python',
    r'^javascript',
    r'^typescript',
    r'^rust',
    r'^go\s+',
    r'^golang',
    r'^java',
    r'^c\+\+',
    r'^c#',
    r'^ruby',
    r'^php',
    r'^swift',
    r'^kotlin',
    r'^scala',
    r'^clojure',
    r'^haskell',
    r'^elm',
    r'^reasonml',
    r'^react',
    r'^vue',
    r'^angular',
    r'^svelte',
    r'^node',
    r'^nodejs',
    r'^deno',
]

_BLOCKED_SPEAKER_REGEX = re.compile('|'.join(_BLOCKED_SPEAKER_PATTERNS), re.IGNORECASE)


def _is_valid_speaker_name(name: str) -> bool:
    """Check if extracted name is likely a real person."""
    if not name or len(name) < 3:
        return False

    name_lower = name.lower().strip()

    # Check blocked patterns
    if _BLOCKED_SPEAKER_REGEX.search(name_lower):
        return False

    # Must have at least one space (First Last) or be a short single name
    # But "Build Stage" has a space but is blocked above
    if ' ' not in name and len(name) < 10:
        # Single word names like "Alice" are OK, but long single words aren't
        if len(name) > 15:
            return False

    # Check for obvious non-name patterns
    if re.match(r'^(how|what|why|when|where|which|who|whose)\s', name_lower):
        return False

    # Check for conference/event words in the name
    conf_words = ['conference', 'summit', 'symposium', 'forum', 'meetup', 'workshop', 'training']
    if any(w in name_lower for w in conf_words):
        return False

    return True


@dataclass
class DiscoveryChannel:
    """A YouTube channel discovered during graph exploration."""
    name: str
    url: Optional[str] = None
    source: str = "speaker_search"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    talk_count: int = 0
    speakers: list[str] = field(default_factory=list)
    total_views: int = 0
    years: set = field(default_factory=set)
    is_conference: bool = False  # Likely a conference/major channel
    is_company: bool = False  # Likely a company channel

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "talk_count": self.talk_count,
            "speakers": self.speakers,
            "total_views": self.total_views,
            "years": sorted([y for y in self.years if y is not None]),
            "is_conference": self.is_conference,
            "is_company": self.is_company,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryChannel":
        return cls(
            name=data["name"],
            url=data.get("url"),
            source=data.get("source", "speaker_search"),
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            talk_count=data.get("talk_count", 0),
            speakers=data.get("speakers", []),
            total_views=data.get("total_views", 0),
            years=set(data.get("years", [])),
            is_conference=data.get("is_conference", False),
            is_company=data.get("is_company", False),
        )


@dataclass
class DiscoverySpeaker:
    """A speaker discovered during graph exploration."""
    name: str
    slug: str = field(default="")
    source: str = "speaker_search"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    talk_count: int = 0
    total_views: int = 0
    channels: list[str] = field(default_factory=list)
    conferences: list[str] = field(default_factory=list)
    youtube_urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.slug:
            self.slug = self._slugify(self.name)

    def _slugify(self, name: str) -> str:
        if not name:
            return ""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        return slug.strip('-')

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "talk_count": self.talk_count,
            "total_views": self.total_views,
            "channels": self.channels,
            "conferences": self.conferences,
            "youtube_urls": self.youtube_urls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoverySpeaker":
        return cls(
            name=data["name"],
            slug=data.get("slug", ""),
            source=data.get("source", "speaker_search"),
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            talk_count=data.get("talk_count", 0),
            total_views=data.get("total_views", 0),
            channels=data.get("channels", []),
            conferences=data.get("conferences", []),
            youtube_urls=data.get("youtube_urls", []),
        )


@dataclass
class DiscoveryTalk:
    """A talk discovered during graph exploration."""
    youtube_id: str
    title: str
    speaker: Optional[str] = None
    url: Optional[str] = None
    channel: Optional[str] = None
    year: Optional[int] = None
    view_count: int = 0
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    source: str = "speaker_search"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ingested: bool = False

    def to_dict(self) -> dict:
        return {
            "youtube_id": self.youtube_id,
            "title": self.title,
            "speaker": self.speaker,
            "url": self.url,
            "channel": self.channel,
            "year": self.year,
            "view_count": self.view_count,
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "ingested": self.ingested,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryTalk":
        return cls(
            youtube_id=data["youtube_id"],
            title=data["title"],
            speaker=data.get("speaker"),
            url=data.get("url"),
            channel=data.get("channel"),
            year=data.get("year"),
            view_count=data.get("view_count", 0),
            duration_seconds=data.get("duration_seconds"),
            thumbnail_url=data.get("thumbnail_url"),
            source=data.get("source", "speaker_search"),
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            ingested=data.get("ingested", False),
        )


def _is_conference_channel(channel_name: str) -> bool:
    """Heuristic: is this likely a conference/event channel?

    Signals:
    - Contains conference keywords
    - Channel name is a known tech conference
    - Company channels are NOT conferences (Vercel, Netflix, etc.)
    """
    if not channel_name:
        return False

    name_lower = channel_name.lower()

    # Definitely conference indicators
    conf_keywords = [
        'conference', 'conf', 'summit', 'symposium', 'forum',
        'fosdem', 'defcon', 'bsides', 'kcc', 'jsconf', 'pycon',
        'kubecon', 'reactconf', 'vueconf', 'rustconf', 'gophercon',
        'dotai', 'dotscale', 'ndc', 'qcon', 'devoxx', 'goto',
        'strangeloop', 'infoq', 'velocity', 'rubyconf', 'elixirconf',
        'clojureconf', 'haskellconf', 'scalaconf', 'deno',
    ]

    # NOT conferences - company/tech blogs (these are still valuable but different)
    company_keywords = [
        'vercel', 'netlify', 'cloudflare', 'aws', 'azure', 'gcp',
        'google', 'microsoft', 'apple', 'meta', 'netflix', 'spotify',
        'stripe', 'square', 'uber', 'lyft', 'doordash',
        'twitch', 'discord', 'slack', 'zoom',
        'github', 'gitlab', 'bitbucket',
        'docker', 'kubernetes', 'hashicorp', 'terraform',
        'prisma', 'mongodb', 'postgresql', 'redis', 'elastic',
    ]

    # Check if company
    for kw in company_keywords:
        if kw in name_lower:
            return False

    # Check if conference
    for kw in conf_keywords:
        if kw in name_lower:
            return True

    # Check pattern: "NameConf" or "Name Conference"
    if re.search(r'\w+conf\b', name_lower):
        return True

    return False


def _is_company_channel(channel_name: str) -> bool:
    """Heuristic: is this likely a company tech channel?"""
    if not channel_name:
        return False

    name_lower = channel_name.lower()

    company_keywords = [
        'vercel', 'netlify', 'cloudflare', 'aws', 'amazon', 'azure',
        'google', 'microsoft', 'apple', 'meta', 'netflix', 'spotify',
        'stripe', 'square', 'shopify', 'uber', 'lyft', 'doordash',
        'twitch', 'discord', 'slack', 'zoom', 'figma', 'notion',
        'github', 'gitlab', 'bitbucket', 'snyk', 'sonatype',
        'docker', 'kubernetes', 'hashicorp', 'terraform', 'ansible',
        'prisma', 'mongodb', 'postgresql', 'redis', 'elastic',
        'mongo', 'redis', 'mysql', 'cassandra',
        'intel', 'amd', 'nvidia', 'qualcomm',
    ]

    for kw in company_keywords:
        if kw in name_lower:
            return True

    return False


class DiscoveryEngine:
    """Engine for graph-based speaker discovery."""

    def __init__(self):
        self.channels: dict[str, DiscoveryChannel] = {}
        self.speakers: dict[str, DiscoverySpeaker] = {}
        self.talks: dict[str, DiscoveryTalk] = {}

        # Queue for BFS expansion
        self.speaker_queue: list[str] = []
        self.channel_queue: list[str] = []

        # Stats
        self.stats = {
            "speakers_discovered": 0,
            "channels_discovered": 0,
            "talks_discovered": 0,
            "new_speakers_last_run": 0,
            "new_channels_last_run": 0,
            "new_talks_last_run": 0,
        }

    def add_seed_speakers(self, speaker_names: list[str]) -> int:
        """Add seed speakers to start discovery.

        Returns number of new speakers added.
        """
        added = 0
        for name in speaker_names:
            if not name or name.strip() == "":
                continue
            name = name.strip()
            slug = self._slugify(name)
            if slug not in self.speakers:
                self.speakers[slug] = DiscoverySpeaker(
                    name=name,
                    slug=slug,
                    source="seed",
                )
                self.speaker_queue.append(slug)
                added += 1
        return added

    def _slugify(self, name: str) -> str:
        if not name:
            return ""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        return slug.strip('-')

    async def discover_from_speakers(
        self,
        max_speakers: int = 50,
        max_talks_per_speaker: int = 30,
        max_concurrent: int = 3,
    ) -> dict:
        """BFS discovery starting from seed speakers.

        Process:
        1. Take speakers from queue
        2. Search for their talks
        3. Extract channels and new speakers
        4. Add new speakers to queue
        5. Repeat until max reached

        Returns discovery stats.
        """
        processed = set()
        loop = asyncio.get_event_loop()

        async def process_speaker(speaker_slug: str) -> tuple[str, list[dict]]:
            speaker = self.speakers.get(speaker_slug)
            if not speaker:
                return "", []

            console.print(f"[dim]  Searching talks for: {speaker.name}[/dim]")

            try:
                talks = await search_talks_by_speaker(
                    speaker.name,
                    max_results=max_talks_per_speaker,
                )
                return speaker.name, talks
            except Exception as e:
                console.print(f"[yellow]  Error searching {speaker.name}: {e}[/yellow]")
                return speaker.name, []

        console.print(f"[cyan]Starting BFS discovery from {len(self.speaker_queue)} seed speakers...[/cyan]")

        while self.speaker_queue and len(processed) < max_speakers:
            # Get batch of speakers
            batch_size = min(max_concurrent, len(self.speaker_queue))
            batch = self.speaker_queue[:batch_size]
            self.speaker_queue = self.speaker_queue[batch_size:]

            # Process in parallel
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_one(slug: str) -> tuple[str, list[dict]]:
                async with semaphore:
                    return await process_speaker(slug)

            tasks = [process_one(slug) for slug in batch if slug not in processed]

            for coro in asyncio.as_completed(tasks):
                speaker_name, talks = await coro
                if not speaker_name:
                    continue

                processed.add(self._slugify(speaker_name))
                self.stats["speakers_discovered"] += 1

                # Process talks
                for talk in talks:
                    talk_id = talk.get('id', '')
                    if not talk_id or talk_id in self.talks:
                        continue

                    # Create talk record
                    self.talks[talk_id] = DiscoveryTalk(
                        youtube_id=talk_id,
                        title=talk.get('title', ''),
                        speaker=speaker_name,
                        url=talk.get('url'),
                        channel=talk.get('channel'),
                        year=talk.get('year'),
                        view_count=talk.get('view_count', 0),
                        duration_seconds=talk.get('duration_seconds'),
                        thumbnail_url=talk.get('thumbnail_url'),
                        source="speaker_search",
                    )

                    # Update speaker stats
                    slug = self._slugify(speaker_name)
                    sp = self.speakers.get(slug)
                    if sp:
                        sp.talk_count += 1
                        sp.total_views += (talk.get('view_count') or 0)
                        if talk.get('url'):
                            sp.youtube_urls.append(talk.get('url'))

                    # Process channel
                    channel_name = talk.get('channel') or 'Unknown'
                    if channel_name and channel_name != 'Unknown':
                        if channel_name not in self.channels:
                            ch = DiscoveryChannel(
                                name=channel_name,
                                url=talk.get('channel_url'),
                                source="speaker_discovery",
                                is_conference=_is_conference_channel(channel_name),
                                is_company=_is_company_channel(channel_name),
                            )
                            self.channels[channel_name] = ch
                            self.channel_queue.append(channel_name)

                        ch = self.channels[channel_name]
                        ch.talk_count += 1
                        ch.total_views += (talk.get('view_count') or 0)
                        ch.years.add(talk.get('year'))
                        if speaker_name not in ch.speakers:
                            ch.speakers.append(speaker_name)

                        # Update speaker's channel list
                        if sp and channel_name not in sp.channels:
                            sp.channels.append(channel_name)

                        # Track new speaker from talk's speaker field
                        extracted_speaker = talk.get('speaker')
                        if extracted_speaker and extracted_speaker != speaker_name:
                            extracted_slug = self._slugify(extracted_speaker)
                            if extracted_slug not in self.speakers:
                                # Validate it's a real speaker name
                                if _is_valid_speaker_name(extracted_speaker):
                                    self.speakers[extracted_slug] = DiscoverySpeaker(
                                        name=extracted_speaker,
                                        slug=extracted_slug,
                                        source="talk_extraction",
                                    )
                                    self.speaker_queue.append(extracted_slug)

        self.stats["new_speakers_last_run"] = len(processed)
        self.stats["new_channels_last_run"] = len(self.channels)
        self.stats["new_talks_last_run"] = len(self.talks)

        return self.stats

    async def discover_speakers_from_channels(
        self,
        max_new_speakers: int = 100,
        max_talks_per_channel: int = 20,
    ) -> dict:
        """Discover new speakers from discovered channels.

        For each channel, search for other speakers who have talks there.

        Args:
            max_new_speakers: Maximum new speakers to discover
            max_talks_per_channel: Talks to check per channel

        Returns discovery stats.
        """
        found_speakers: dict[str, dict] = {}

        for channel_name in self.channel_queue:
            if len(found_speakers) >= max_new_speakers:
                break

            channel = self.channels.get(channel_name)
            if not channel:
                continue

            # For a channel, search for "channel name conference talk"
            # to find other speakers
            queries = [
                f'"{channel_name}" conference talk',
                f'"{channel_name}" keynote',
            ]

            for query in queries:
                if len(found_speakers) >= max_new_speakers:
                    break

                console.print(f"[dim]  Searching channel: {query}[/dim]")

                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    _executor, _search_youtube_sync, query, max_talks_per_channel
                )

                for result in results:
                    # Extract speaker from result
                    speaker = result.get('speaker')
                    if not speaker:
                        # Try to extract from title
                        title = result.get('original_title', '')
                        clean_title, extracted = self._extract_speaker_from_title(title)
                        speaker = extracted

                    if speaker:
                        slug = self._slugify(speaker)
                        if slug not in self.speakers and slug not in found_speakers:
                            found_speakers[slug] = {
                                'name': speaker,
                                'slug': slug,
                                'channel': channel_name,
                                'source': 'channel_discovery',
                                'talks': [result],
                            }
                        elif slug in found_speakers:
                            found_speakers[slug]['talks'].append(result)

        # Add found speakers to queue
        for slug, data in found_speakers.items():
            talk_count = len(data['talks'])
            self.speakers[slug] = DiscoverySpeaker(
                name=data['name'],
                slug=slug,
                source=data['source'],
                talk_count=talk_count,
                channels=[data['channel']],
            )
            self.speaker_queue.append(slug)

        self.stats["new_speakers_last_run"] = len(found_speakers)

        return self.stats

    def _extract_speaker_from_title(self, title: str) -> tuple[str, Optional[str]]:
        """Extract speaker name from title using existing patterns."""
        # Import from youtube.py for consistent extraction
        from cfp_pipeline.enrichers.youtube import _extract_speaker_from_title
        clean_title, speaker = _extract_speaker_from_title(title)
        return clean_title, speaker

    def get_top_channels(self, limit: int = 20, conference_only: bool = False) -> list[DiscoveryChannel]:
        """Get top channels by talk count."""
        channels = list(self.channels.values())
        if conference_only:
            channels = [c for c in channels if c.is_conference]
        channels.sort(key=lambda c: c.talk_count, reverse=True)
        return channels[:limit]

    def get_top_speakers(self, limit: int = 20) -> list[DiscoverySpeaker]:
        """Get top speakers by talk count."""
        speakers = list(self.speakers.values())
        speakers.sort(key=lambda s: s.talk_count, reverse=True)
        return speakers[:limit]

    def get_channels_for_explore(self, limit: int = 50) -> list[dict]:
        """Get channels formatted for --explore."""
        channels = self.get_top_channels(limit=limit)
        return [
            {
                "name": ch.name,
                "url": ch.url,
                "talk_count": ch.talk_count,
                "speaker_count": len(ch.speakers),
                "is_conference": ch.is_conference,
                "is_company": ch.is_company,
                "sample_speakers": ch.speakers[:5],
                "years": sorted(ch.years),
            }
            for ch in channels
        ]

    def get_speakers_for_explore(self, limit: int = 50) -> list[dict]:
        """Get speakers formatted for --explore."""
        speakers = self.get_top_speakers(limit=limit)
        return [
            {
                "name": sp.name,
                "slug": sp.slug,
                "talk_count": sp.talk_count,
                "total_views": sp.total_views,
                "channel_count": len(sp.channels),
                "channels": sp.channels[:5],
            }
            for sp in speakers
        ]

    def save(self) -> None:
        """Save discovery state to disk."""
        DISCOVERY_DATA_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "stats": self.stats,
            "channels": {k: v.to_dict() for k, v in self.channels.items()},
            "speakers": {k: v.to_dict() for k, v in self.speakers.items()},
            "talks": {k: v.to_dict() for k, v in self.talks.items()},
        }

        with open(DISCOVERY_LIST_FILE, "w") as f:
            json.dump(data, f, indent=2)

        console.print(f"[green]Saved discovery data:[/green]")
        console.print(f"  Channels: {len(self.channels)}")
        console.print(f"  Speakers: {len(self.speakers)}")
        console.print(f"  Talks: {len(self.talks)}")

    def load(self) -> bool:
        """Load discovery state from disk. Returns True if successful."""
        if not DISCOVERY_LIST_FILE.exists():
            return False

        try:
            with open(DISCOVERY_LIST_FILE) as f:
                data = json.load(f)

            for k, v in data.get("channels", {}).items():
                self.channels[k] = DiscoveryChannel.from_dict(v)

            for k, v in data.get("speakers", {}).items():
                self.speakers[k] = DiscoverySpeaker.from_dict(v)
                if v.get("source") == "seed":
                    self.speaker_queue.append(k)

            for k, v in data.get("talks", {}).items():
                self.talks[k] = DiscoveryTalk.from_dict(v)

            self.stats = data.get("stats", self.stats)

            console.print(f"[cyan]Loaded discovery data:[/cyan]")
            console.print(f"  Channels: {len(self.channels)}")
            console.print(f"  Speakers: {len(self.speakers)}")
            console.print(f"  Talks: {len(self.talks)}")

            return True

        except Exception as e:
            console.print(f"[yellow]Warning: Could not load discovery data: {e}[/yellow]")
            return False

    def clear(self) -> None:
        """Clear all discovery data."""
        self.channels = {}
        self.speakers = {}
        self.talks = {}
        self.speaker_queue = []
        self.channel_queue = []
        self.stats = {
            "speakers_discovered": 0,
            "channels_discovered": 0,
            "talks_discovered": 0,
            "new_speakers_last_run": 0,
            "new_channels_last_run": 0,
            "new_talks_last_run": 0,
        }

        if DISCOVERY_LIST_FILE.exists():
            DISCOVERY_LIST_FILE.unlink()

        console.print("[green]Discovery data cleared[/green]")

    def print_summary(self) -> None:
        """Print discovery summary."""
        conf_channels = [c for c in self.channels.values() if c.is_conference]
        comp_channels = [c for c in self.channels.values() if c.is_company]

        console.print("\n[bold]Discovery Summary[/bold]")
        console.print(f"  Total Speakers: {len(self.speakers)}")
        console.print(f"  Total Channels: {len(self.channels)}")
        console.print(f"    - Conference channels: {len(conf_channels)}")
        console.print(f"    - Company channels: {len(comp_channels)}")
        console.print(f"  Total Talks: {len(self.talks)}")

        top_speakers = self.get_top_speakers(limit=5)
        if top_speakers:
            console.print(f"\n[bold]Top 5 Speakers:[/bold]")
            for sp in top_speakers:
                console.print(f"  - {sp.name}: {sp.talk_count} talks, {sp.total_views:,} views")

        top_channels = self.get_top_channels(limit=5, conference_only=False)
        if top_channels:
            console.print(f"\n[bold]Top 5 Channels:[/bold]")
            for ch in top_channels:
                conf_tag = "[CONF]" if ch.is_conference else "[COMP]" if ch.is_company else ""
                console.print(f"  - {ch.name} {conf_tag}: {ch.talk_count} talks, {len(ch.speakers)} speakers")


def load_discovery_list() -> dict:
    """Load the discovery list (for --explore)."""
    if not DISCOVERY_LIST_FILE.exists():
        return {"version": "1.0", "channels": [], "speakers": [], "talks": [], "saved_at": None}

    try:
        with open(DISCOVERY_LIST_FILE) as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load discovery list: {e}[/yellow]")
        return {"version": "1.0", "channels": [], "speakers": [], "talks": [], "saved_at": None}