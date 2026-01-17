"""Extract structured data from HTML (Schema.org JSON-LD, OpenGraph)."""

import json
import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel
from rich.console import Console

console = Console()


class ExtractedData(BaseModel):
    """Extracted CFP metadata from a page."""

    # Basic info
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

    # Dates (ISO format)
    cfp_end_date: Optional[str] = None  # Submission deadline
    cfp_start_date: Optional[str] = None
    event_start_date: Optional[str] = None
    event_end_date: Optional[str] = None

    # Location
    city: Optional[str] = None
    country: Optional[str] = None
    location_raw: Optional[str] = None
    is_online: bool = False

    # Topics
    topics: list[str] = []

    # Full text for search (cleaned page content)
    full_text: Optional[str] = None

    # Source info
    extraction_method: str = "unknown"
    confidence: float = 0.0  # 0-1 confidence score

    class Config:
        extra = "ignore"


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse various date formats to ISO YYYY-MM-DD."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]

    # Common formats
    formats = [
        "%B %d, %Y",      # January 15, 2026
        "%b %d, %Y",      # Jan 15, 2026
        "%d %B %Y",       # 15 January 2026
        "%d %b %Y",       # 15 Jan 2026
        "%m/%d/%Y",       # 01/15/2026
        "%d/%m/%Y",       # 15/01/2026
        "%Y/%m/%d",       # 2026/01/15
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Extract all JSON-LD blocks from page."""
    json_ld_blocks = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                json_ld_blocks.extend(data)
            else:
                json_ld_blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            continue

    return json_ld_blocks


def extract_from_schema_org(json_ld_blocks: list[dict]) -> Optional[ExtractedData]:
    """Extract CFP data from Schema.org JSON-LD."""
    # Event types we care about
    event_types = {"Event", "EducationEvent", "BusinessEvent", "SocialEvent", "Festival"}

    for block in json_ld_blocks:
        block_type = block.get("@type", "")

        # Handle arrays of types
        if isinstance(block_type, list):
            if not any(t in event_types for t in block_type):
                continue
        elif block_type not in event_types:
            continue

        # Found an Event!
        data = ExtractedData(extraction_method="schema.org", confidence=0.8)

        # Name
        data.name = block.get("name")

        # Description
        data.description = block.get("description")

        # URL
        data.url = block.get("url")

        # Dates
        data.event_start_date = parse_date(block.get("startDate"))
        data.event_end_date = parse_date(block.get("endDate"))

        # Location
        location = block.get("location", {})
        if isinstance(location, dict):
            if location.get("@type") == "VirtualLocation":
                data.is_online = True
            else:
                address = location.get("address", {})
                if isinstance(address, dict):
                    data.city = address.get("addressLocality")
                    data.country = address.get("addressCountry")
                elif isinstance(address, str):
                    data.location_raw = address
                data.location_raw = data.location_raw or location.get("name")
        elif isinstance(location, str):
            data.location_raw = location
            if "online" in location.lower() or "virtual" in location.lower():
                data.is_online = True

        # Attendance mode
        attendance = block.get("eventAttendanceMode", "")
        if "Online" in attendance:
            data.is_online = True

        # Topics from keywords
        keywords = block.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]
        data.topics = keywords[:10]  # Limit

        return data

    return None


def extract_opengraph(soup: BeautifulSoup) -> Optional[ExtractedData]:
    """Extract data from OpenGraph meta tags."""
    og_tags: dict[str, str] = {}

    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        content = meta.get("content", "")

        if prop.startswith("og:") and content:
            key = prop[3:]  # Remove "og:" prefix
            og_tags[key] = content

    if not og_tags:
        return None

    data = ExtractedData(extraction_method="opengraph", confidence=0.5)

    data.name = og_tags.get("title")
    data.description = og_tags.get("description")
    data.url = og_tags.get("url")

    # OG doesn't typically have dates, but sometimes custom properties
    # og:event:start_time, og:event:end_time (Facebook events)
    data.event_start_date = parse_date(og_tags.get("event:start_time"))
    data.event_end_date = parse_date(og_tags.get("event:end_time"))

    # Location
    data.location_raw = og_tags.get("locale")

    return data


def extract_meta_tags(soup: BeautifulSoup) -> Optional[ExtractedData]:
    """Extract data from standard meta tags."""
    data = ExtractedData(extraction_method="meta", confidence=0.3)

    # Title
    title_tag = soup.find("title")
    if title_tag:
        data.name = title_tag.get_text().strip()

    # Meta description
    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta:
        data.description = desc_meta.get("content", "").strip()

    # Keywords
    kw_meta = soup.find("meta", attrs={"name": "keywords"})
    if kw_meta:
        keywords = kw_meta.get("content", "")
        data.topics = [k.strip() for k in keywords.split(",")][:10]

    if data.name or data.description:
        return data

    return None


def extract_structured_data(html: str) -> ExtractedData:
    """Extract structured data from HTML using multiple methods.

    Tries in order of preference:
    1. Schema.org JSON-LD
    2. OpenGraph meta tags
    3. Standard meta tags

    Returns merged data with highest confidence values.
    """
    soup = BeautifulSoup(html, "lxml")

    # Try Schema.org first (highest quality)
    json_ld_blocks = extract_json_ld(soup)
    schema_data = extract_from_schema_org(json_ld_blocks)

    # Try OpenGraph
    og_data = extract_opengraph(soup)

    # Try meta tags
    meta_data = extract_meta_tags(soup)

    # Merge: prefer higher confidence sources
    candidates = [d for d in [schema_data, og_data, meta_data] if d]

    if not candidates:
        return ExtractedData(extraction_method="none", confidence=0.0)

    # Sort by confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)

    # Start with highest confidence, fill gaps from lower
    result = candidates[0].model_copy()

    for candidate in candidates[1:]:
        for field, value in candidate.model_dump().items():
            if field in ("extraction_method", "confidence"):
                continue
            current = getattr(result, field)
            if (current is None or current == [] or current == "") and value:
                setattr(result, field, value)

    # Update method to reflect merge
    if len(candidates) > 1:
        result.extraction_method = "+".join(c.extraction_method for c in candidates if c.extraction_method)

    return result
