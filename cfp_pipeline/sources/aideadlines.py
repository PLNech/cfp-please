"""AI Deadlines (aideadlin.es) data source - ML/AI academic conferences."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from cfp_pipeline.models import CFP, Location

console = Console()

YAML_URL = "https://raw.githubusercontent.com/paperswithcode/ai-deadlines/gh-pages/_data/conferences.yml"
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "aideadlines_cfps.json"
CACHE_TTL_HOURS = 12  # Academic deadlines change less frequently


class RawAIDeadlineRecord(BaseModel):
    """Raw record from AI Deadlines YAML."""

    title: str
    year: int
    id: str
    link: str
    deadline: str  # "YYYY-MM-DD HH:MM:SS" or "TBA"
    timezone: str = "UTC"
    date: Optional[str] = None  # Human readable "May 03-05, 2025"
    place: Optional[str] = None
    sub: str | list[str] = "ML"  # Subject area(s)
    abstract_deadline: Optional[str] = None
    note: Optional[str] = None
    hindex: Optional[int] = None  # H5-index from Google Scholar (quality signal!)
    full_name: Optional[str] = None
    start: Optional[str | object] = None  # YYYY-MM-DD or date object
    end: Optional[str | object] = None  # YYYY-MM-DD or date object
    paperslink: Optional[str] = None
    pwclink: Optional[str] = None

    class Config:
        extra = "ignore"


# Map AI Deadlines subjects to our taxonomy
SUBJECT_MAP = {
    "ML": "ai-ml",
    "CV": "ai-ml",  # Computer Vision
    "NLP": "ai-ml",  # Natural Language Processing
    "RO": "robotics",  # Robotics
    "SP": "ai-ml",  # Speech
    "DM": "data",  # Data Mining
    "AP": "ai-ml",  # Applications
    "KR": "ai-ml",  # Knowledge Representation
    "HCI": "design",  # Human-Computer Interaction
    "IRSM": "data",  # Information Retrieval & Social Media
    "MISC": "general",
}


def parse_deadline(deadline_str: str, timezone: str = "UTC") -> Optional[int]:
    """Parse deadline string to Unix timestamp."""
    if not deadline_str or deadline_str.upper() == "TBA":
        return None
    try:
        # Format: "2025-01-15 23:59:59" or "2025-01-15 23:59"
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(deadline_str.strip(), fmt)
                return int(dt.timestamp())
            except ValueError:
                continue
        return None
    except Exception:
        return None


def parse_date_str(date_val: Optional[str | object]) -> Optional[str]:
    """Extract ISO date from string or date object."""
    if not date_val:
        return None
    # Handle date objects from YAML
    if hasattr(date_val, 'isoformat'):
        return date_val.isoformat()[:10]
    try:
        # String in YYYY-MM-DD format
        datetime.strptime(str(date_val), "%Y-%m-%d")
        return str(date_val)
    except ValueError:
        return None


def generate_object_id(conf_id: str, year: int) -> str:
    """Generate stable object ID."""
    key = f"aideadlines:{conf_id}:{year}"
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


def load_from_cache() -> list[dict]:
    """Load data from cache."""
    with open(CACHE_FILE) as f:
        return json.load(f).get("conferences", [])


def serialize_for_json(obj):
    """Convert non-JSON-serializable objects."""
    if hasattr(obj, 'isoformat'):  # date/datetime
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def save_to_cache(conferences: list[dict]) -> None:
    """Save data to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(
            {"cached_at": datetime.now().timestamp(), "conferences": conferences},
            f,
            default=serialize_for_json
        )


async def fetch_conferences(force_refresh: bool = False) -> list[dict]:
    """Fetch conference data from GitHub."""
    if not force_refresh and is_cache_valid():
        console.print("[dim]Loading AI Deadlines from cache...[/dim]")
        return load_from_cache()

    console.print("[cyan]Fetching AI Deadlines from GitHub...[/cyan]")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(YAML_URL)
        response.raise_for_status()
        conferences = yaml.safe_load(response.text)

    save_to_cache(conferences)
    console.print(f"[green]Fetched {len(conferences)} conferences from AI Deadlines[/green]")
    return conferences


def parse_place(place: Optional[str]) -> Location:
    """Parse place string into Location."""
    if not place:
        return Location(raw="")

    # Common patterns: "City, Country" or "City, State, Country"
    parts = [p.strip() for p in place.split(",")]

    if len(parts) >= 2:
        city = parts[0]
        country = parts[-1]
        return Location(city=city, country=country, raw=place)
    elif len(parts) == 1:
        return Location(city=parts[0], raw=place)

    return Location(raw=place)


def transform_record(raw: RawAIDeadlineRecord) -> CFP:
    """Transform AI Deadlines record to CFP model."""
    # Handle subject as list or string
    subjects = raw.sub if isinstance(raw.sub, list) else [raw.sub]
    topics_normalized = list(set(SUBJECT_MAP.get(s, "ai-ml") for s in subjects))

    # Build full name with year
    name = f"{raw.title} {raw.year}"
    if raw.full_name:
        name = f"{raw.full_name} ({raw.title} {raw.year})"

    # Parse deadline
    deadline_ts = parse_deadline(raw.deadline, raw.timezone)
    deadline_iso = raw.deadline[:10] if raw.deadline and raw.deadline != "TBA" else None

    cfp = CFP(
        objectID=generate_object_id(raw.id, raw.year),
        name=name,
        description=raw.note,  # Notes often contain useful info
        url=raw.link,
        cfp_url=raw.link,  # Usually same as conference link for academic
        # CFP dates
        cfp_end_date=deadline_ts,
        cfp_end_date_iso=deadline_iso,
        # Event dates
        event_start_date=parse_deadline(raw.start) if raw.start else None,
        event_end_date=parse_deadline(raw.end) if raw.end else None,
        event_start_date_iso=parse_date_str(raw.start),
        event_end_date_iso=parse_date_str(raw.end),
        # Location
        location=parse_place(raw.place),
        # Topics - include raw subjects plus our normalized ones
        topics=subjects,
        topics_normalized=topics_normalized,
        # Meta
        source="aideadlines",
        audience_level="advanced",  # Academic conferences are typically advanced
    )

    # Store hindex as a quality signal (we'll use this in dedup)
    if raw.hindex:
        cfp._hindex = raw.hindex  # type: ignore

    return cfp


async def get_cfps(force_refresh: bool = False) -> list[CFP]:
    """Fetch and transform CFPs from AI Deadlines."""
    conferences = await fetch_conferences(force_refresh)

    cfps = []
    now = datetime.now().timestamp()
    current_year = datetime.now().year

    for conf_data in conferences:
        try:
            raw = RawAIDeadlineRecord.model_validate(conf_data)

            # Only include current/future years
            if raw.year < current_year:
                continue

            cfp = transform_record(raw)

            # Skip if deadline passed (but keep TBA)
            if cfp.cfp_end_date and cfp.cfp_end_date < now:
                continue

            cfps.append(cfp)

        except Exception as e:
            console.print(f"[yellow]Skipping invalid AI Deadlines record: {e}[/yellow]")

    console.print(f"[green]Found {len(cfps)} open CFPs from AI Deadlines[/green]")
    return cfps
