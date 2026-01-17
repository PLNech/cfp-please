"""Confs.tech GitHub data source."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Field
from rich.console import Console

from cfp_pipeline.models import CFP, Location

console = Console()

GITHUB_API_URL = "https://api.github.com/repos/tech-conferences/conference-data/contents/conferences/2026"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences/2026"
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "confstech_cfps.json"
CACHE_TTL_HOURS = 6


class RawConfsTechRecord(BaseModel):
    """Raw record from confs.tech JSON."""

    name: str
    url: str
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    online: bool = False
    cfpUrl: Optional[str] = None
    cfpEndDate: Optional[str] = None
    twitter: Optional[str] = None
    bluesky: Optional[str] = None
    locales: Optional[list[str] | str] = None
    cocUrl: Optional[str] = None
    offersSignLanguageOrCC: Optional[bool] = None

    class Config:
        extra = "ignore"


def parse_date_to_timestamp(date_str: Optional[str]) -> Optional[int]:
    """Parse YYYY-MM-DD to Unix timestamp (end of day for deadlines)."""
    if not date_str:
        return None
    try:
        # Parse as end of day (23:59:59) for CFP deadlines
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        return int(dt.timestamp())
    except ValueError:
        return None


def generate_object_id(url: str, name: str) -> str:
    """Generate stable object ID from URL + name."""
    key = f"confstech:{url}:{name}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def is_cache_valid() -> bool:
    """Check if cache exists and is within TTL."""
    if not CACHE_FILE.exists():
        return False
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        cached_at = cache.get("cached_at", 0)
        age_hours = (datetime.now().timestamp() - cached_at) / 3600
        return age_hours < CACHE_TTL_HOURS
    except (json.JSONDecodeError, KeyError):
        return False


def load_from_cache() -> dict:
    """Load data from cache file."""
    with open(CACHE_FILE) as f:
        return json.load(f)


def save_to_cache(data: dict) -> None:
    """Save data to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["cached_at"] = datetime.now().timestamp()
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


async def fetch_topic_files() -> list[str]:
    """Get list of topic JSON files from GitHub API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        response.raise_for_status()
        files = response.json()

    return [f["name"] for f in files if f["name"].endswith(".json")]


async def fetch_topic_conferences(topic_file: str) -> tuple[str, list[dict]]:
    """Fetch conferences for a specific topic file."""
    topic = topic_file.replace(".json", "")
    url = f"{GITHUB_RAW_URL}/{topic_file}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        conferences = response.json()

    return topic, conferences


async def fetch_all_conferences(force_refresh: bool = False) -> dict[str, list[dict]]:
    """Fetch all conferences from all topic files."""

    if not force_refresh and is_cache_valid():
        console.print("[dim]Loading confs.tech from cache...[/dim]")
        cache = load_from_cache()
        return cache.get("conferences", {})

    console.print("[cyan]Fetching confs.tech data from GitHub...[/cyan]")

    topic_files = await fetch_topic_files()
    console.print(f"[dim]Found {len(topic_files)} topic files[/dim]")

    all_conferences: dict[str, list[dict]] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for topic_file in topic_files:
            topic = topic_file.replace(".json", "")
            url = f"{GITHUB_RAW_URL}/{topic_file}"
            try:
                response = await client.get(url)
                response.raise_for_status()
                conferences = response.json()
                all_conferences[topic] = conferences
            except Exception as e:
                console.print(f"[yellow]Failed to fetch {topic_file}: {e}[/yellow]")

    total = sum(len(v) for v in all_conferences.values())
    console.print(f"[green]Fetched {total} conferences from {len(all_conferences)} topics[/green]")

    save_to_cache({"conferences": all_conferences})
    return all_conferences


def infer_topic_from_filename(topic: str) -> str:
    """Map confs.tech topic filename to our taxonomy."""
    mapping = {
        "android": "mobile",
        "ios": "mobile",
        "css": "frontend",
        "javascript": "frontend",
        "typescript": "frontend",
        "ux": "design",
        "data": "data",
        "devops": "devops",
        "dotnet": "backend",
        "elixir": "backend",
        "golang": "backend",
        "graphql": "api",
        "java": "backend",
        "kotlin": "backend",
        "networking": "infrastructure",
        "php": "backend",
        "python": "backend",
        "ruby": "backend",
        "rust": "backend",
        "scala": "backend",
        "security": "security",
        "tech-comm": "career",
        "general": "general",
        "leadership": "leadership",
        "product": "product",
        "api": "api",
        "clojure": "backend",
    }
    return mapping.get(topic, topic)


def transform_confstech_record(raw: RawConfsTechRecord, topic: str) -> CFP:
    """Transform a confs.tech record into our CFP model."""

    # Determine event format
    event_format = "virtual" if raw.online else "in-person"
    if raw.city and raw.online:
        event_format = "hybrid"

    # Build location
    location = Location(
        city=raw.city,
        country=raw.country,
        raw=f"{raw.city or ''}, {raw.country or ''}".strip(", "),
    )

    cfp = CFP(
        objectID=generate_object_id(raw.url, raw.name),
        name=raw.name,
        description=None,  # confs.tech doesn't have descriptions
        url=raw.url,
        cfp_url=raw.cfpUrl,
        # CFP dates
        cfp_end_date=parse_date_to_timestamp(raw.cfpEndDate),
        cfp_end_date_iso=raw.cfpEndDate,
        # Event dates
        event_start_date=parse_date_to_timestamp(raw.startDate),
        event_end_date=parse_date_to_timestamp(raw.endDate),
        event_start_date_iso=raw.startDate,
        event_end_date_iso=raw.endDate,
        # Location
        location=location,
        # Topics
        topics=[topic],
        topics_normalized=[infer_topic_from_filename(topic)],
        # Meta
        event_format=event_format,
        source="confs.tech",
    )

    return cfp


async def get_cfps(force_refresh: bool = False) -> list[CFP]:
    """Fetch and transform CFPs from confs.tech."""
    all_conferences = await fetch_all_conferences(force_refresh)

    cfps = []
    now = datetime.now().timestamp()

    for topic, conferences in all_conferences.items():
        for conf_data in conferences:
            try:
                raw = RawConfsTechRecord.model_validate(conf_data)

                # Skip if no CFP URL (no open CFP)
                if not raw.cfpUrl:
                    continue

                cfp = transform_confstech_record(raw, topic)

                # Skip if CFP already closed
                if cfp.cfp_end_date and cfp.cfp_end_date < now:
                    continue

                cfps.append(cfp)

            except Exception as e:
                console.print(f"[yellow]Skipping invalid record in {topic}: {e}[/yellow]")

    console.print(f"[green]Found {len(cfps)} open CFPs from confs.tech[/green]")
    return cfps
