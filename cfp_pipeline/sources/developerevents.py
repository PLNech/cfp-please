"""developers.events data source - Community-curated developer conferences."""

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

CFPS_URL = "https://developers.events/all-cfps.json"
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "developerevents_cfps.json"
CACHE_TTL_HOURS = 6


class ConfDetails(BaseModel):
    """Conference details nested object."""
    name: str
    date: list[int] = Field(default_factory=list)  # Unix timestamps in ms
    hyperlink: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None

    class Config:
        extra = "ignore"


class RawDevEventsRecord(BaseModel):
    """Raw record from developers.events CFPs JSON."""
    link: str  # CFP submission URL
    until: Optional[str] = None  # Human-readable deadline
    untilDate: Optional[int] = None  # Unix timestamp in milliseconds
    conf: ConfDetails

    class Config:
        extra = "ignore"


def ms_to_timestamp(ms: Optional[int]) -> Optional[int]:
    """Convert milliseconds to seconds timestamp."""
    if not ms:
        return None
    return ms // 1000


def timestamp_to_iso(ts: Optional[int]) -> Optional[str]:
    """Convert Unix timestamp to ISO date string."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return None


def generate_object_id(link: str, name: str) -> str:
    """Generate stable object ID."""
    key = f"developerevents:{link}:{name}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def is_cache_valid() -> bool:
    """Check if cache is valid."""
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


def load_from_cache() -> list[dict]:
    """Load from cache."""
    with open(CACHE_FILE) as f:
        return json.load(f).get("cfps", [])


def save_to_cache(cfps: list[dict]) -> None:
    """Save to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"cached_at": datetime.now().timestamp(), "cfps": cfps}, f)


async def fetch_cfps_data(force_refresh: bool = False) -> list[dict]:
    """Fetch CFP data from developers.events."""
    if not force_refresh and is_cache_valid():
        console.print("[dim]Loading developers.events from cache...[/dim]")
        return load_from_cache()

    console.print("[cyan]Fetching developers.events CFPs...[/cyan]")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(CFPS_URL)
        response.raise_for_status()
        cfps = response.json()

    save_to_cache(cfps)
    console.print(f"[green]Fetched {len(cfps)} CFPs from developers.events[/green]")
    return cfps


def parse_location(loc_str: Optional[str]) -> Location:
    """Parse location string like 'Paris (France)' or 'Austin, TX (USA)'."""
    if not loc_str:
        return Location(raw="")

    raw = loc_str

    # Handle "& Online" suffix
    online = "online" in loc_str.lower()
    loc_str = loc_str.replace("& Online", "").replace("&amp; Online", "").strip()

    # Pattern: "City (Country)" or "City, State (Country)"
    if "(" in loc_str and ")" in loc_str:
        parts = loc_str.split("(")
        city_part = parts[0].strip().rstrip(",")
        country = parts[1].rstrip(")").strip()

        # Check if city_part has state (e.g., "Austin, TX")
        if "," in city_part:
            city_parts = city_part.split(",")
            city = city_parts[0].strip()
            state = city_parts[1].strip() if len(city_parts) > 1 else None
            return Location(city=city, state=state, country=country, raw=raw)

        return Location(city=city_part, country=country, raw=raw)

    # Just city or "Online"
    if loc_str.lower() == "online":
        return Location(raw="Online")

    return Location(city=loc_str, raw=raw)


def transform_record(raw: RawDevEventsRecord) -> CFP:
    """Transform developers.events record to CFP model."""
    conf = raw.conf

    # Parse deadline
    deadline_ts = ms_to_timestamp(raw.untilDate)
    deadline_iso = timestamp_to_iso(deadline_ts)

    # Parse event dates (array of 1-2 timestamps in ms)
    event_start = ms_to_timestamp(conf.date[0]) if conf.date else None
    event_end = ms_to_timestamp(conf.date[1]) if len(conf.date) > 1 else event_start

    cfp = CFP(
        objectID=generate_object_id(raw.link, conf.name),
        name=conf.name,
        description=None,  # No descriptions in this source
        url=conf.hyperlink,
        cfp_url=raw.link,
        # CFP dates
        cfp_end_date=deadline_ts,
        cfp_end_date_iso=deadline_iso,
        # Event dates
        event_start_date=event_start,
        event_end_date=event_end,
        event_start_date_iso=timestamp_to_iso(event_start),
        event_end_date_iso=timestamp_to_iso(event_end),
        # Location
        location=parse_location(conf.location),
        # Topics - we'll rely on normalizers to infer from name
        topics=[],
        topics_normalized=[],
        # Meta
        source="developers.events",
    )

    return cfp


async def get_cfps(force_refresh: bool = False) -> list[CFP]:
    """Fetch and transform CFPs from developers.events."""
    cfps_data = await fetch_cfps_data(force_refresh)

    cfps = []
    now = datetime.now().timestamp()

    for cfp_data in cfps_data:
        try:
            raw = RawDevEventsRecord.model_validate(cfp_data)
            cfp = transform_record(raw)

            # Skip if deadline passed
            if cfp.cfp_end_date and cfp.cfp_end_date < now:
                continue

            cfps.append(cfp)

        except Exception as e:
            console.print(f"[yellow]Skipping invalid developers.events record: {e}[/yellow]")

    console.print(f"[green]Found {len(cfps)} open CFPs from developers.events[/green]")
    return cfps
