"""CallingAllPapers API client with local caching."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from pydantic import ValidationError
from rich.console import Console

from cfp_pipeline.models import CFP, GeoLoc, Location, RawCAPRecord

console = Console()


def _repair_encoding(text: Optional[str]) -> Optional[str]:
    """Repair common encoding issues in text fields."""
    if not text:
        return None

    # Fix common encoding errors
    # Remove null bytes
    text = text.replace('\x00', '')

    # Fix smart quotes and special chars that might be mangled
    replacements = {
        '\xe2\x80\x99': "'",  # Right single quote
        '\xe2\x80\x9c': '"',  # Left double quote
        '\xe2\x80\x9d': '"',  # Right double quote
        '\xe2\x80\x93': '-',  # En dash
        '\xe2\x80\x94': '--', # Em dash
        '\xc3\xa9': 'e',      # e with accent
        '\xc3\xa0': 'a',      # a with accent
        '\xc3\xb1': 'n',      # n with tilde
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good) if isinstance(bad, str) else text

    # Remove non-printable chars except newlines/tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Strip extra whitespace
    text = ' '.join(text.split())

    return text if text.strip() else None

CAP_API_URL = "https://api.callingallpapers.com/v1/cfp"
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "cap_cfps.json"
CACHE_TTL_HOURS = 6  # Refresh cache after 6 hours


def parse_iso_date(date_str: Optional[str]) -> Optional[int]:
    """Parse ISO 8601 date string to Unix timestamp."""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(date_str.replace("Z", "+00:00"), fmt)
                return int(dt.timestamp())
            except ValueError:
                continue
        # Try fromisoformat as fallback
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def generate_object_id(uri: str) -> str:
    """Generate a stable object ID from the CFP URI."""
    return hashlib.sha1(uri.encode()).hexdigest()[:16]


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
    """Load CFPs from cache file."""
    with open(CACHE_FILE) as f:
        cache = json.load(f)
    return cache.get("cfps", [])


def save_to_cache(cfps: list[dict]) -> None:
    """Save CFPs to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "cached_at": datetime.now().timestamp(),
        "cfps": cfps,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


async def fetch_cfps(force_refresh: bool = False) -> list[RawCAPRecord]:
    """Fetch all CFPs from CallingAllPapers API (with caching)."""

    # Check cache first
    if not force_refresh and is_cache_valid():
        console.print("[dim]Loading CFPs from cache...[/dim]")
        raw_cfps = load_from_cache()
        console.print(f"[green]Loaded {len(raw_cfps)} CFPs from cache[/green]")
    else:
        console.print("[cyan]Fetching CFPs from CallingAllPapers API...[/cyan]")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                CAP_API_URL,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        # API returns {"cfps": [...], "meta": {...}}
        raw_cfps = data.get("cfps", data) if isinstance(data, dict) else data

        # Save to cache
        save_to_cache(raw_cfps)
        console.print(f"[green]Fetched {len(raw_cfps)} CFPs (cached)[/green]")

    records = []
    for item in raw_cfps:
        try:
            record = RawCAPRecord.model_validate(item)
            records.append(record)
        except ValidationError as e:
            console.print(f"[yellow]Skipping invalid record: {e}[/yellow]")

    return records


def extract_iso_date(date_str: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD from ISO date string."""
    if not date_str:
        return None
    try:
        return date_str[:10]  # "2026-01-15T00:00:00Z" -> "2026-01-15"
    except (IndexError, TypeError):
        return None


def transform_cap_record(raw: RawCAPRecord) -> CFP:
    """Transform a raw CAP record into our CFP model."""
    # Filter out empty tags (CAP often sends [''] which is useless)
    clean_tags = [t for t in raw.tags if t and t.strip()]

    # Apply encoding repair to text fields
    repaired_name = _repair_encoding(raw.name)
    repaired_description = _repair_encoding(raw.description)

    cfp = CFP(
        objectID=generate_object_id(raw.uri),
        name=repaired_name or raw.name,  # Fallback to original if repair returns None
        description=repaired_description,
        url=raw.eventUri,
        cfp_url=raw.uri,
        icon_url=raw.iconUri,
        # CFP dates
        cfp_start_date=parse_iso_date(raw.dateCfpStart),
        cfp_end_date=parse_iso_date(raw.dateCfpEnd),
        cfp_start_date_iso=extract_iso_date(raw.dateCfpStart),
        cfp_end_date_iso=extract_iso_date(raw.dateCfpEnd),
        # Event dates
        event_start_date=parse_iso_date(raw.dateEventStart),
        event_end_date=parse_iso_date(raw.dateEventEnd),
        event_start_date_iso=extract_iso_date(raw.dateEventStart),
        event_end_date_iso=extract_iso_date(raw.dateEventEnd),
        # Other
        location=Location(raw=raw.location or ""),
        topics=clean_tags,
        source=raw.source or "callingallpapers",
    )

    # Assign geoloc post-construction (Pydantic ignores underscore fields in constructor)
    if raw.latitude and raw.longitude and raw.latitude != 0 and raw.longitude != 0:
        cfp._geoloc = GeoLoc(lat=raw.latitude, lng=raw.longitude)

    return cfp


async def get_cfps() -> list[CFP]:
    """Fetch and transform CFPs from CallingAllPapers."""
    raw_records = await fetch_cfps()
    return [transform_cap_record(r) for r in raw_records]
