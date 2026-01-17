"""HTML heuristics for CFP data extraction.

When structured data and platform-specific extractors fail,
fall back to pattern matching and keyword detection.
"""

import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, NavigableString
from rich.console import Console

from cfp_pipeline.extractors.structured import ExtractedData, parse_date

console = Console()

# Keywords that indicate CFP content
CFP_KEYWORDS = [
    "call for papers",
    "call for proposals",
    "call for speakers",
    "call for presentations",
    "call for talks",
    "submit a talk",
    "submit a paper",
    "submit a proposal",
    "submission deadline",
    "paper submission",
    "abstract submission",
    "speaker submission",
]

# Keywords that indicate deadline
DEADLINE_KEYWORDS = [
    "deadline",
    "due date",
    "closes",
    "submit by",
    "submissions close",
    "papers due",
    "abstracts due",
]

# Date patterns
DATE_PATTERNS = [
    # ISO: 2026-01-15
    r"\b(\d{4}-\d{2}-\d{2})\b",
    # US: January 15, 2026 or Jan 15, 2026
    r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b",
    # European: 15 January 2026 or 15 Jan 2026
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",
    # Numeric: 01/15/2026 or 15/01/2026
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
]


def extract_dates_near_keywords(text: str, keywords: list[str]) -> list[str]:
    """Find dates that appear near specific keywords."""
    found_dates = []
    text_lower = text.lower()

    for keyword in keywords:
        # Find keyword position
        idx = text_lower.find(keyword.lower())
        if idx == -1:
            continue

        # Look for dates within 100 chars after keyword
        context = text[idx:idx + 150]

        for pattern in DATE_PATTERNS:
            matches = re.findall(pattern, context, re.I)
            for match in matches:
                date = parse_date(match)
                if date:
                    found_dates.append(date)

    return found_dates


def extract_all_dates(text: str) -> list[tuple[str, str]]:
    """Extract all dates from text with surrounding context."""
    dates = []

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            date_str = match.group(1)
            date = parse_date(date_str)
            if date:
                # Get context around the date
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].lower()
                dates.append((date, context))

    return dates


def classify_date(date: str, context: str) -> Optional[str]:
    """Classify a date based on surrounding context.

    Returns: 'cfp_deadline', 'event_start', 'event_end', or None
    """
    context = context.lower()

    # CFP deadline indicators
    if any(kw in context for kw in ["deadline", "submit", "cfp", "due", "close", "paper", "proposal"]):
        return "cfp_deadline"

    # Event start indicators
    if any(kw in context for kw in ["conference date", "event date", "starts", "begins", "opens"]):
        return "event_start"

    # Event end indicators
    if any(kw in context for kw in ["ends", "through", "until"]):
        return "event_end"

    return None


def has_cfp_content(text: str) -> bool:
    """Check if text contains CFP-related content."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CFP_KEYWORDS)


def extract_topics_from_text(text: str) -> list[str]:
    """Extract potential topics from text using common patterns."""
    topics = set()
    text_lower = text.lower()

    # Look for "Topics include: X, Y, Z" patterns
    topics_section = re.search(
        r"topics?\s*(?:include|:)\s*([^.]+)",
        text, re.I
    )
    if topics_section:
        items = re.split(r"[,;]|\band\b", topics_section.group(1))
        for item in items:
            item = item.strip()
            if 3 < len(item) < 50:
                topics.add(item)

    # Look for bullet lists with tech keywords
    tech_keywords = [
        "python", "javascript", "rust", "go", "java", "kotlin", "swift",
        "react", "vue", "angular", "node", "django", "flask", "rails",
        "kubernetes", "docker", "aws", "gcp", "azure", "cloud",
        "machine learning", "ai", "data science", "devops", "security",
        "frontend", "backend", "fullstack", "mobile", "web",
        "api", "microservices", "serverless", "blockchain",
    ]

    for keyword in tech_keywords:
        if keyword in text_lower:
            topics.add(keyword.title())

    return list(topics)[:15]


def extract_location_from_text(text: str) -> tuple[Optional[str], bool]:
    """Extract location and online status from text.

    Returns: (location_string, is_online)
    """
    is_online = bool(re.search(r"\b(online|virtual|remote|hybrid)\b", text, re.I))

    # Look for "Location: City, Country" or "Venue: ..."
    location_match = re.search(
        r"(?:location|venue|where|place)[:\s]+([^,\n]{3,50}(?:,\s*[^,\n]{2,30})?)",
        text, re.I
    )
    if location_match:
        return location_match.group(1).strip(), is_online

    # Look for city + country patterns
    # "in City, Country" or "held in City"
    city_match = re.search(
        r"(?:in|at|held at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)",
        text
    )
    if city_match:
        return city_match.group(1).strip(), is_online

    return None, is_online


def clean_text_for_search(text: str, max_length: int = 10000) -> str:
    """Clean and truncate text for search indexing."""
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove very long words (likely base64 or encoded content)
    text = re.sub(r"\b\w{50,}\b", "", text)
    # Truncate
    return text[:max_length].strip()


def extract_heuristics(html: str) -> ExtractedData:
    """Extract CFP data using heuristic pattern matching.

    This is the fallback when structured data is not available.
    Uses keyword detection, date pattern matching, and text analysis.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove script, style, nav, footer elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    data = ExtractedData(extraction_method="heuristics", confidence=0.4)

    # Capture cleaned full text for search
    data.full_text = clean_text_for_search(text)

    # Check if this looks like CFP content at all
    if not has_cfp_content(text):
        data.confidence = 0.1

    # Title from h1 or title tag
    h1 = soup.find("h1")
    if h1:
        data.name = h1.get_text().strip()[:200]
    else:
        title = soup.find("title")
        if title:
            data.name = title.get_text().strip()[:200]

    # Description from first substantial paragraph
    for p in soup.find_all("p"):
        p_text = p.get_text().strip()
        if len(p_text) > 100:
            data.description = p_text[:500]
            break

    # Extract dates and classify them
    all_dates = extract_all_dates(text)

    # Also look for dates near deadline keywords specifically
    deadline_dates = extract_dates_near_keywords(text, DEADLINE_KEYWORDS)
    if deadline_dates:
        # Use the first deadline date found
        data.cfp_end_date = deadline_dates[0]
        data.confidence = min(data.confidence + 0.2, 1.0)

    # Classify remaining dates
    for date, context in all_dates:
        if data.cfp_end_date and date == data.cfp_end_date:
            continue  # Already handled

        date_type = classify_date(date, context)
        if date_type == "cfp_deadline" and not data.cfp_end_date:
            data.cfp_end_date = date
        elif date_type == "event_start" and not data.event_start_date:
            data.event_start_date = date
        elif date_type == "event_end" and not data.event_end_date:
            data.event_end_date = date

    # If we found a deadline, increase confidence
    if data.cfp_end_date:
        data.confidence = min(data.confidence + 0.2, 1.0)

    # Location
    location, is_online = extract_location_from_text(text)
    data.location_raw = location
    data.is_online = is_online

    # Topics
    data.topics = extract_topics_from_text(text)

    return data
