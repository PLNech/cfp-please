"""Platform-specific CFP extractors for known conference platforms."""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rich.console import Console

from cfp_pipeline.extractors.structured import ExtractedData, parse_date

console = Console()


def is_sessionize_url(url: str) -> bool:
    """Check if URL is a Sessionize page."""
    return "sessionize.com" in url.lower()


def is_papercall_url(url: str) -> bool:
    """Check if URL is a PaperCall page."""
    return "papercall.io" in url.lower()


def is_eventbrite_url(url: str) -> bool:
    """Check if URL is an Eventbrite page."""
    return "eventbrite" in url.lower()


def is_pretalx_url(url: str) -> bool:
    """Check if URL is a Pretalx CFP page."""
    return "pretalx" in url.lower()


def is_easychair_url(url: str) -> bool:
    """Check if URL is an EasyChair page."""
    return "easychair.org" in url.lower()


def extract_sessionize(html: str, url: str) -> Optional[ExtractedData]:
    """Extract CFP data from Sessionize pages.

    Sessionize has a consistent structure:
    - Event name in h1 or og:title
    - Deadline in a specific section
    - Topics/categories listed
    """
    soup = BeautifulSoup(html, "lxml")
    data = ExtractedData(extraction_method="sessionize", confidence=0.9)

    # Event name
    h1 = soup.find("h1")
    if h1:
        data.name = h1.get_text().strip()

    # Description - usually in meta or a specific div
    desc_div = soup.find("div", class_=re.compile(r"description|about", re.I))
    if desc_div:
        data.description = desc_div.get_text()[:500].strip()

    # Deadline - Sessionize shows "Submissions close: DATE"
    deadline_patterns = [
        r"submissions?\s+close[s:]?\s*(\w+\s+\d{1,2},?\s+\d{4})",
        r"deadline[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"closes?\s+on\s+(\w+\s+\d{1,2},?\s+\d{4})",
    ]
    text = soup.get_text()
    for pattern in deadline_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            data.cfp_end_date = parse_date(match.group(1))
            break

    # Event dates - "Event: DATE - DATE"
    event_date_match = re.search(
        r"event[:\s]+(\w+\s+\d{1,2},?\s+\d{4})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})",
        text, re.I
    )
    if event_date_match:
        data.event_start_date = parse_date(event_date_match.group(1))
        data.event_end_date = parse_date(event_date_match.group(2))

    # Location - often in a specific section
    location_div = soup.find(string=re.compile(r"location|venue", re.I))
    if location_div:
        parent = location_div.find_parent()
        if parent:
            loc_text = parent.get_text()
            data.location_raw = loc_text[:100].strip()

    # Check for online/virtual
    if re.search(r"\b(online|virtual|remote)\b", text, re.I):
        data.is_online = True

    # Categories/topics - often in tags or a list
    topics = []
    for tag in soup.find_all(class_=re.compile(r"tag|category|topic", re.I)):
        topic = tag.get_text().strip()
        if topic and len(topic) < 50:
            topics.append(topic)
    data.topics = topics[:10]

    return data if data.name else None


def extract_papercall(html: str, url: str) -> Optional[ExtractedData]:
    """Extract CFP data from PaperCall.io pages.

    PaperCall structure:
    - Event name in h1 or title
    - CFP dates in sidebar or header
    - Description in main content area
    """
    soup = BeautifulSoup(html, "lxml")
    data = ExtractedData(extraction_method="papercall", confidence=0.9)

    # Event name
    h1 = soup.find("h1")
    if h1:
        data.name = h1.get_text().strip()

    # Description
    desc_section = soup.find("section", class_=re.compile(r"description|about", re.I))
    if not desc_section:
        desc_section = soup.find("div", class_=re.compile(r"description|about|content", re.I))
    if desc_section:
        data.description = desc_section.get_text()[:500].strip()

    # Deadline - PaperCall shows "CFP closes DATE"
    text = soup.get_text()
    deadline_patterns = [
        r"cfp\s+closes?\s+(\w+\s+\d{1,2},?\s+\d{4})",
        r"closes?\s+(\w+\s+\d{1,2},?\s+\d{4})",
        r"deadline[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
    ]
    for pattern in deadline_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            data.cfp_end_date = parse_date(match.group(1))
            break

    # Event dates
    event_match = re.search(
        r"event\s+date[s]?[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        text, re.I
    )
    if event_match:
        data.event_start_date = parse_date(event_match.group(1))

    # Location
    location_match = re.search(r"location[:\s]+([^,\n]+(?:,\s*[^,\n]+)?)", text, re.I)
    if location_match:
        data.location_raw = location_match.group(1).strip()

    if re.search(r"\b(online|virtual|remote)\b", text, re.I):
        data.is_online = True

    # Topics
    topics = []
    for tag in soup.find_all(class_=re.compile(r"tag|topic|track", re.I)):
        topic = tag.get_text().strip()
        if topic and len(topic) < 50:
            topics.append(topic)
    data.topics = topics[:10]

    return data if data.name else None


def extract_pretalx(html: str, url: str) -> Optional[ExtractedData]:
    """Extract CFP data from Pretalx pages.

    Pretalx is common for open source conferences.
    """
    soup = BeautifulSoup(html, "lxml")
    data = ExtractedData(extraction_method="pretalx", confidence=0.85)

    # Title
    h1 = soup.find("h1")
    if h1:
        data.name = h1.get_text().strip()

    # Description
    main = soup.find("main") or soup.find("article")
    if main:
        paragraphs = main.find_all("p")
        if paragraphs:
            data.description = " ".join(p.get_text() for p in paragraphs[:2])[:500]

    # Dates - Pretalx shows deadline prominently
    text = soup.get_text()
    deadline_match = re.search(
        r"(?:deadline|cfp\s+end|submissions?\s+until)[:\s]+(\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2},?\s+\d{4})",
        text, re.I
    )
    if deadline_match:
        data.cfp_end_date = parse_date(deadline_match.group(1))

    # Location
    if re.search(r"\b(online|virtual|remote)\b", text, re.I):
        data.is_online = True

    return data if data.name else None


def extract_eventbrite(html: str, url: str) -> Optional[ExtractedData]:
    """Extract data from Eventbrite pages.

    Note: Eventbrite is primarily for event registration, not CFPs.
    But sometimes conferences list CFP info on their Eventbrite page.
    """
    soup = BeautifulSoup(html, "lxml")
    data = ExtractedData(extraction_method="eventbrite", confidence=0.6)

    # Event name
    title = soup.find("h1", class_=re.compile(r"event-title", re.I))
    if title:
        data.name = title.get_text().strip()

    # Description
    desc = soup.find("div", class_=re.compile(r"structured-content|description", re.I))
    if desc:
        data.description = desc.get_text()[:500].strip()

    # Dates - Eventbrite has structured date sections
    date_section = soup.find(class_=re.compile(r"date-info|event-date", re.I))
    if date_section:
        date_text = date_section.get_text()
        date_match = re.search(r"(\w+\s+\d{1,2},?\s+\d{4})", date_text)
        if date_match:
            data.event_start_date = parse_date(date_match.group(1))

    # Location
    location_section = soup.find(class_=re.compile(r"location-info|venue", re.I))
    if location_section:
        data.location_raw = location_section.get_text()[:100].strip()

    return data if data.name else None


def extract_platform_specific(html: str, url: str) -> Optional[ExtractedData]:
    """Try platform-specific extractors based on URL.

    Returns extracted data if URL matches a known platform, None otherwise.
    """
    if is_sessionize_url(url):
        return extract_sessionize(html, url)

    if is_papercall_url(url):
        return extract_papercall(html, url)

    if is_pretalx_url(url):
        return extract_pretalx(html, url)

    if is_eventbrite_url(url):
        return extract_eventbrite(html, url)

    # EasyChair is mostly for academic paper submission, structure varies
    # if is_easychair_url(url):
    #     return extract_easychair(html, url)

    return None
