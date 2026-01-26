"""Discovery graph for speaker-aware talk discovery.

Implements a graph-based discovery system that:
- Discovers conferences from talks (via video metadata/channels)
- Discovers speakers from talks (via title parsing)
- Discovers talks from speakers (speaker-aware YouTube search)
- Builds a local "discovered" list for --explore deep dives
- Tracks discovery provenance (how we found each entity)

The graph structure:
    Speaker --(speaks at)--> Conference --(has)--> Talk --(by)--> Speaker
       |                         |
       +--(discovered from)------+

This creates a cycle that allows iterative deepening:
1. Start with seed speakers
2. Find their talks → discover new conferences
3. For each new conference → find more talks → discover more speakers
4. For each new speaker → find more talks → ...
5. Continue until saturation or limits reached
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

console = Console()

_executor = ThreadPoolExecutor(max_workers=4)

DISCOVERY_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "discovery"
DISCOVERY_LIST_FILE = DISCOVERY_DATA_DIR / "discovered.json"
DISCOVERY_GRAPH_FILE = DISCOVERY_DATA_DIR / "graph.json"


@dataclass
class DiscoveredConference:
    """A conference discovered during graph exploration."""
    name: str
    conference_id: str  # sha256 hash of lowercase name (matching pipeline convention)
    source: str  # "talk", "speaker", "search", "manual"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    talk_count: int = 0
    year: Optional[int] = None
    channel_url: Optional[str] = None
    channel_name: Optional[str] = None
    url: Optional[str] = None
    topics: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0-1, how confident we are this is a real conference

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "conference_id": self.conference_id,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "talk_count": self.talk_count,
            "year": self.year,
            "channel_url": self.channel_url,
            "channel_name": self.channel_name,
            "url": self.url,
            "topics": self.topics,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveredConference":
        return cls(
            name=data["name"],
            conference_id=data["conference_id"],
            source=data["source"],
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            talk_count=data.get("talk_count", 0),
            year=data.get("year"),
            channel_url=data.get("channel_url"),
            channel_name=data.get("channel_name"),
            url=data.get("url"),
            topics=data.get("topics", []),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class DiscoveredSpeaker:
    """A speaker discovered during graph exploration."""
    name: str
    slug: str  # slugified name for uniqueness
    source: str  # "talk", "conference", "channel", "manual"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    talk_count: int = 0
    total_views: int = 0
    channel_url: Optional[str] = None
    channel_name: Optional[str] = None
    conferences: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "talk_count": self.talk_count,
            "total_views": self.total_views,
            "channel_url": self.channel_url,
            "channel_name": self.channel_name,
            "conferences": self.conferences,
            "topics": self.topics,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveredSpeaker":
        return cls(
            name=data["name"],
            slug=data["slug"],
            source=data["source"],
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            talk_count=data.get("talk_count", 0),
            total_views=data.get("total_views", 0),
            channel_url=data.get("channel_url"),
            channel_name=data.get("channel_name"),
            conferences=data.get("conferences", []),
            topics=data.get("topics", []),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class DiscoveredTalk:
    """A talk discovered during graph exploration."""
    youtube_id: str
    title: str
    speaker: Optional[str] = None
    source: str = "search"  # "search", "channel", "conference", "speaker"
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    url: Optional[str] = None
    conference_name: Optional[str] = None
    conference_id: Optional[str] = None
    year: Optional[int] = None
    view_count: int = 0
    channel: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    topics: list[str] = field(default_factory=list)
    ingested: bool = False  # True if already added to talks index

    def to_dict(self) -> dict:
        return {
            "youtube_id": self.youtube_id,
            "title": self.title,
            "speaker": self.speaker,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "url": self.url,
            "conference_name": self.conference_name,
            "conference_id": self.conference_id,
            "year": self.year,
            "view_count": self.view_count,
            "channel": self.channel,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "topics": self.topics,
            "ingested": self.ingested,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveredTalk":
        return cls(
            youtube_id=data["youtube_id"],
            title=data["title"],
            speaker=data.get("speaker"),
            source=data.get("source", "search"),
            discovered_at=data.get("discovered_at", datetime.now().isoformat()),
            url=data.get("url"),
            conference_name=data.get("conference_name"),
            conference_id=data.get("conference_id"),
            year=data.get("year"),
            view_count=data.get("view_count", 0),
            channel=data.get("channel"),
            thumbnail_url=data.get("thumbnail_url"),
            duration_seconds=data.get("duration_seconds"),
            topics=data.get("topics", []),
            ingested=data.get("ingested", False),
        )


@dataclass
class DiscoveryGraph:
    """Graph structure for tracking discovery relationships.

    Nodes:
    - Conferences: discovered from talks
    - Speakers: discovered from talks
    - Talks: discovered from searches/channels

    Edges:
    - Speaker -> Conference (via talks at that conference)
    - Conference -> Talk (talks from that conference)
    - Talk -> Speaker (speaker of that talk)
    - Talk -> Conference (conference the talk was at)
    - Speaker -> Speaker (co-speaking, via multi-speaker talks)
    - Conference -> Conference (via shared speakers or topics)
    """
    conferences: dict[str, DiscoveredConference] = field(default_factory=dict)
    speakers: dict[str, DiscoveredSpeaker] = field(default_factory=dict)
    talks: dict[str, DiscoveredTalk] = field(default_factory=dict)

    # Edge tracking: speaker -> conferences, conference -> speakers, etc.
    speaker_to_conferences: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    conference_to_speakers: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    talk_to_conference: dict[str, str] = field(default_factory=dict)
    talk_to_speaker: dict[str, str] = field(default_factory=dict)

    # Discovery queue for BFS-style exploration
    speaker_queue: list[str] = field(default_factory=list)
    conference_queue: list[str] = field(default_factory=list)

    # Stats
    stats: dict = field(default_factory=lambda: {
        "total_conferences": 0,
        "total_speakers": 0,
        "total_talks": 0,
        "discovered_this_session": 0,
        "ingested_this_session": 0,
    })

    def add_conference(self, conference: DiscoveredConference) -> bool:
        """Add a conference to the graph. Returns True if new."""
        if conference.conference_id in self.conferences:
            # Update existing
            existing = self.conferences[conference.conference_id]
            existing.talk_count = max(existing.talk_count, conference.talk_count)
            if conference.channel_url and not existing.channel_url:
                existing.channel_url = conference.channel_url
            return False

        self.conferences[conference.conference_id] = conference
        self.stats["total_conferences"] += 1
        self.stats["discovered_this_session"] += 1
        self.conference_queue.append(conference.conference_id)
        return True

    def add_speaker(self, speaker: DiscoveredSpeaker) -> bool:
        """Add a speaker to the graph. Returns True if new."""
        if speaker.slug in self.speakers:
            # Update existing
            existing = self.speakers[speaker.slug]
            existing.talk_count = max(existing.talk_count, speaker.talk_count)
            existing.total_views = max(existing.total_views, speaker.total_views)
            for conf in speaker.conferences:
                if conf not in existing.conferences:
                    existing.conferences.append(conf)
            return False

        self.speakers[speaker.slug] = speaker
        self.stats["total_speakers"] += 1
        self.stats["discovered_this_session"] += 1
        self.speaker_queue.append(speaker.slug)
        return True

    def add_talk(self, talk: DiscoveredTalk) -> bool:
        """Add a talk to the graph. Returns True if new."""
        if talk.youtube_id in self.talks:
            return False

        self.talks[talk.youtube_id] = talk
        self.stats["total_talks"] += 1
        self.stats["discovered_this_session"] += 1

        # Create edges
        if talk.conference_id:
            self.talk_to_conference[talk.youtube_id] = talk.conference_id
            if talk.speaker:
                self.conference_to_speakers[talk.conference_id].add(talk.speaker)

        if talk.speaker:
            self.talk_to_speaker[talk.youtube_id] = talk.speaker
            if talk.conference_id:
                self.speaker_to_conferences[talk.speaker].add(talk.conference_id)

        return True

    def link_speaker_to_conference(self, speaker_slug: str, conference_id: str) -> None:
        """Create an edge between a speaker and conference."""
        self.speaker_to_conferences[speaker_slug].add(conference_id)
        self.conference_to_speakers[conference_id].add(speaker_slug)

    def get_speakers_for_conference(self, conference_id: str) -> list[DiscoveredSpeaker]:
        """Get all speakers who spoke at a conference."""
        speaker_slugs = self.conference_to_speakers.get(conference_id, set())
        return [self.speakers[s] for s in speaker_slugs if s in self.speakers]

    def get_conferences_for_speaker(self, speaker_slug: str) -> list[DiscoveredConference]:
        """Get all conferences a speaker has talked at."""
        conf_ids = self.speaker_to_conferences.get(speaker_slug, set())
        return [self.conferences[c] for c in conf_ids if c in self.conferences]

    def get_talks_for_speaker(self, speaker_slug: str) -> list[DiscoveredTalk]:
        """Get all talks by a speaker."""
        speaker = self.speakers.get(speaker_slug)
        if not speaker:
            return []

        return [t for t in self.talks.values()
                if t.speaker and self._slugify(t.speaker) == speaker_slug]

    def get_talks_for_conference(self, conference_id: str) -> list[DiscoveredTalk]:
        """Get all talks from a conference."""
        return [t for t in self.talks.values() if t.conference_id == conference_id]

    def _slugify(self, name: str) -> str:
        """Slugify a name for consistency."""
        if not name:
            return ""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    def to_dict(self) -> dict:
        """Serialize graph to dict."""
        return {
            "conferences": {k: v.to_dict() for k, v in self.conferences.items()},
            "speakers": {k: v.to_dict() for k, v in self.speakers.items()},
            "talks": {k: v.to_dict() for k, v in self.talks.items()},
            "speaker_to_conferences": {k: list(v) for k, v in self.speaker_to_conferences.items()},
            "conference_to_speakers": {k: list(v) for k, v in self.conference_to_speakers.items()},
            "talk_to_conference": self.talk_to_conference,
            "talk_to_speaker": self.talk_to_speaker,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryGraph":
        """Deserialize graph from dict."""
        graph = cls()

        for k, v in data.get("conferences", {}).items():
            graph.add_conference(DiscoveredConference.from_dict(v))

        for k, v in data.get("speakers", {}).items():
            graph.add_speaker(DiscoveredSpeaker.from_dict(v))

        for k, v in data.get("talks", {}).items():
            graph.add_talk(DiscoveredTalk.from_dict(v))

        for k, v in data.get("speaker_to_conferences", {}).items():
            graph.speaker_to_conferences[k] = set(v)

        for k, v in data.get("conference_to_speakers", {}).items():
            graph.conference_to_speakers[k] = set(v)

        graph.talk_to_conference = data.get("talk_to_conference", {})
        graph.talk_to_speaker = data.get("talk_to_speaker", {})

        stats = data.get("stats", {})
        graph.stats = {
            "total_conferences": stats.get("total_conferences", len(graph.conferences)),
            "total_speakers": stats.get("total_speakers", len(graph.speakers)),
            "total_talks": stats.get("total_talks", len(graph.talks)),
            "discovered_this_session": 0,
            "ingested_this_session": 0,
        }

        return graph

    def export_for_explore(self) -> dict:
        """Export a simplified view for --explore deep dives."""
        return {
            "generated_at": datetime.now().isoformat(),
            "conferences": [
                {
                    "name": c.name,
                    "conference_id": c.conference_id,
                    "talk_count": c.talk_count,
                    "year": c.year,
                    "topics": c.topics,
                    "discovered_from": c.source,
                }
                for c in self.conferences.values()
            ],
            "speakers": [
                {
                    "name": s.name,
                    "slug": s.slug,
                    "talk_count": s.talk_count,
                    "total_views": s.total_views,
                    "topics": s.topics,
                    "discovered_from": s.source,
                }
                for s in self.speakers.values()
            ],
            "stats": self.stats,
        }


def load_graph() -> DiscoveryGraph:
    """Load discovery graph from disk."""
    if not DISCOVERY_GRAPH_FILE.exists():
        return DiscoveryGraph()

    try:
        with open(DISCOVERY_GRAPH_FILE) as f:
            data = json.load(f)
        return DiscoveryGraph.from_dict(data)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load discovery graph: {e}[/yellow]")
        return DiscoveryGraph()


def save_graph(graph: DiscoveryGraph) -> None:
    """Save discovery graph to disk."""
    DISCOVERY_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DISCOVERY_GRAPH_FILE, "w") as f:
        json.dump(graph.to_dict(), f, indent=2)


def load_discovery_list() -> dict:
    """Load the discovery list (simplified view for --explore)."""
    if not DISCOVERY_LIST_FILE.exists():
        return {"version": "1.0", "conferences": [], "speakers": [], "talks": [], "last_updated": None}

    try:
        with open(DISCOVERY_LIST_FILE) as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load discovery list: {e}[/yellow]")
        return {"version": "1.0", "conferences": [], "speakers": [], "talks": [], "last_updated": None}


def save_discovery_list(graph: DiscoveryGraph) -> None:
    """Save discovery list for --explore deep dives."""
    DISCOVERY_DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = graph.export_for_explore()
    data["last_updated"] = datetime.now().isoformat()

    with open(DISCOVERY_LIST_FILE, "w") as f:
        json.dump(data, f, indent=2)


def clear_discovery_graph() -> None:
    """Clear all discovery data."""
    if DISCOVERY_GRAPH_FILE.exists():
        DISCOVERY_GRAPH_FILE.unlink()
    if DISCOVERY_LIST_FILE.exists():
        DISCOVERY_LIST_FILE.unlink()
    console.print("[green]Discovery graph cleared[/green]")


def print_discovery_summary(graph: DiscoveryGraph) -> None:
    """Print a summary of the discovery graph."""
    console.print("\n[bold]Discovery Graph Summary[/bold]")
    console.print(f"  Conferences: {len(graph.conferences)}")
    console.print(f"  Speakers: {len(graph.speakers)}")
    console.print(f"  Talks: {len(graph.talks)}")
    console.print(f"  Speaker→Conference edges: {sum(len(v) for v in graph.speaker_to_conferences.values())}")
    console.print(f"  Conference→Speaker edges: {sum(len(v) for v in graph.conference_to_speakers.values())}")

    if graph.conference_queue:
        console.print(f"\n[cyan]Conferences ready for exploration: {len(graph.conference_queue)}[/cyan]")
    if graph.speaker_queue:
        console.print(f"[cyan]Speakers ready for exploration: {len(graph.speaker_queue)}[/cyan]")