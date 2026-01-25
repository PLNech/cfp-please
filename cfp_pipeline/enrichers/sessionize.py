"""Sessionize public page scraper for CFP enrichment.

Extracts rich CFP data from Sessionize public pages:
- Session formats (name, duration)
- Speaker benefits (travel, hotel, ticket, payment)
- Attendance estimates
- Tracks/topics
- Target audience

Multi-pass extraction approach:
1. Pass 1: Grabby regex extraction for common patterns
2. Pass 2: Structured HTML parsing for specific sections
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rich.console import Console

from cfp_pipeline.extractors.fetch import fetch_url
from cfp_pipeline.models import CFP

console = Console()


# =============================================================================
# UNIFIED CLEANUP SYSTEM
# =============================================================================
# Architecture: All patterns that extract data also mark text for removal.
# This ensures adding new extraction = automatic cleanup. Maintainable!

class TextCleaner:
    """Unified text processing: extract data AND track spans for removal.

    Usage:
        cleaner = TextCleaner(raw_text)
        value = cleaner.extract_and_remove(pattern, group=1)  # Extract + mark
        cleaner.remove_pattern(pattern)  # Just mark for removal
        clean_text = cleaner.get_clean_text()  # Apply all removals
    """

    def __init__(self, text: str):
        self.original = text
        self.text = text
        self._removals: list[re.Pattern] = []

    def extract_and_remove(self, pattern: re.Pattern, group: int = 1) -> Optional[str]:
        """Extract value from pattern AND mark the match for removal."""
        match = pattern.search(self.text)
        if match:
            self._removals.append(pattern)
            # Handle patterns with no groups or group index out of range
            if match.lastindex and match.lastindex >= group:
                return match.group(group).strip()
            return match.group(0).strip()
        return None

    def extract_all_and_remove(self, pattern: re.Pattern, group: int = 1) -> list[str]:
        """Extract all matches AND mark for removal."""
        matches = list(pattern.finditer(self.text))
        if matches:
            self._removals.append(pattern)
            return [m.group(group).strip() for m in matches if m.lastindex >= group]
        return []

    def remove_pattern(self, pattern: re.Pattern) -> None:
        """Mark pattern for removal (no extraction)."""
        self._removals.append(pattern)

    def remove_string(self, s: str) -> None:
        """Mark exact string for removal."""
        self._removals.append(re.compile(re.escape(s)))

    def get_clean_text(self, max_length: int = 4000) -> str:
        """Apply all removals and return clean text."""
        text = self.text
        for pattern in self._removals:
            text = pattern.sub('', text)
        text = ' '.join(text.split())  # Normalize whitespace
        return text.strip()[:max_length]


# Static boilerplate patterns (always removed, no extraction needed)
_STATIC_BOILERPLATE = [
    # Header: "EventName: Call for Speakers @ Sessionize.com"
    re.compile(r'^[^:]+:\s*Call for (?:Speakers|Proposals|Papers)\s*@\s*Sessionize\.com\s*', re.IGNORECASE),
    # "Call for Speakers/Proposals in X days/months"
    re.compile(r'Call for (?:Speakers|Proposals|Papers)\s+in\s+\d+\s+(?:days?|months?|hours?)\s*', re.IGNORECASE),
    # Timezone boilerplate
    re.compile(r'Call (?:opens|closes) in\s+[^.]+timezone\.\s*', re.IGNORECASE),
    re.compile(r'Closing time in your timezone\s*\([^)]*\)\s*is\s*\.?\s*', re.IGNORECASE),
    re.compile(r'[A-Z][^(]+\s*\(UTC[+-]\d{2}:\d{2}\)\s*timezone\.?\s*', re.IGNORECASE),
    # Status messages (transient)
    re.compile(r'open,?\s+\d+\s+(?:days?|hours?|months?)\s+left\s*', re.IGNORECASE),
    # Login modal (end of page)
    re.compile(r'Submit a session\s+Login with your preferred account.*$', re.IGNORECASE | re.DOTALL),
    re.compile(r'Login with your preferred account.*Classic Login.*$', re.IGNORECASE | re.DOTALL),
    # 404 page
    re.compile(r'404\s*@\s*Sessionize\.com\s*404\s*Page Not Found.*$', re.IGNORECASE | re.DOTALL),
]

_STATIC_STRINGS = [
    '×Close Classic login Remember me on this computer Login Forgot password? Create new classic account',
    'Download iCalendar file',
    '(please login first!)',
    'Add to calendar',
    'Send to email',
]


def _apply_static_cleanup(cleaner: TextCleaner) -> None:
    """Apply static boilerplate removal patterns."""
    for pattern in _STATIC_BOILERPLATE:
        cleaner.remove_pattern(pattern)
    for s in _STATIC_STRINGS:
        cleaner.remove_string(s)


@dataclass
class SessionFormat:
    """A session format with optional duration."""
    name: str
    duration: Optional[str] = None


@dataclass
class SpeakerBenefits:
    """Speaker benefits extracted from CFP."""
    travel: Optional[str] = None  # e.g., "$500-800", "covered"
    hotel: Optional[str] = None   # e.g., "2-3 nights", "covered"
    ticket: bool = False          # Free admission
    payment: Optional[str] = None # e.g., "workshop speakers paid"


@dataclass
class SessionizeData:
    """Raw data extracted from a Sessionize page."""
    url: str

    # Dates (raw strings, not parsed)
    cfp_opens: Optional[str] = None
    cfp_closes: Optional[str] = None
    event_start: Optional[str] = None
    event_end: Optional[str] = None

    # Content
    description: Optional[str] = None
    attendance: Optional[str] = None
    target_audience: Optional[str] = None
    max_submissions: Optional[int] = None
    clean_text: Optional[str] = None  # Truncated clean text for later augmentation

    # Contact & location metadata
    contact_email: Optional[str] = None
    location_raw: Optional[str] = None  # e.g., "Austin, Texas, United States"
    website: Optional[str] = None

    # Structured
    session_formats: list[SessionFormat] = field(default_factory=list)
    benefits: SpeakerBenefits = field(default_factory=SpeakerBenefits)
    tracks: list[str] = field(default_factory=list)

    # Status
    is_open: bool = True
    event_format: Optional[str] = None  # 'virtual', 'in-person', or 'hybrid'
    error: Optional[str] = None


# =============================================================================
# PASS 1: GRABBY REGEX EXTRACTION
# =============================================================================

# Duration patterns: "25 minutes", "45min", "20-25 min", "40 minuter" (Swedish)
DURATION_PATTERN = re.compile(
    r'(\d+(?:\s*[-–]\s*\d+)?)\s*(?:min(?:ute)?s?|minuter?|hrs?|hours?)',
    re.IGNORECASE
)

# Session format patterns
SESSION_FORMAT_PATTERNS = [
    # "Full-length presentations: 20-25 minutes"
    re.compile(r'((?:full[- ]?length|standard|regular|breakout)\s*(?:talk|presentation|session)s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Lightning talks: 5-10 minutes"
    re.compile(r'(lightning\s*(?:talk|presentation)s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Keynote: 60 minutes"
    re.compile(r'(keynote\s*(?:talk|presentation|session)?s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Workshop: 3 hours"
    re.compile(r'((?:full[- ]?day\s+)?workshop\s*(?:session)?s?)[:\s]*(\d+[-–]?\d*\s*(?:min(?:ute)?|hour|hr)s?)?', re.IGNORECASE),
    # "Panel: 45 minutes"
    re.compile(r'(panel\s*(?:discussion|session)?s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Ignite: 5 minutes"
    re.compile(r'(ignite\s*(?:talk|session)?s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Deep dive: 90 minutes"
    re.compile(r'(deep\s*dive\s*(?:session)?s?)[:\s]*(\d+[-–]?\d*\s*min(?:ute)?s?)?', re.IGNORECASE),
    # "Tech Session: 25 or 50 minutes"
    re.compile(r'(tech\s*session\s*(?:talk)?s?)[:\s]*(\d+(?:\s*(?:or|and)\s*\d+)?\s*min(?:ute)?s?)?', re.IGNORECASE),
]

# Additional patterns with different group order (handled specially)
SESSION_FORMAT_PATTERNS_ALT = [
    # "25min talks" or "45 minute talks" - duration first, then type
    re.compile(r'(\d+[-–]?\d*)\s*min(?:ute)?s?\s*(talk|presentation|session)s?', re.IGNORECASE),
    # "talks of 25 or 50 minutes"
    re.compile(r'(talk|presentation|session)s?\s+(?:of\s+)?(\d+(?:\s*(?:or|and)\s*\d+)?)\s*min(?:ute)?s?', re.IGNORECASE),
    # "20-25 minutes (full-length)" or "7-10 minutes (lightning)"
    re.compile(r'(\d+[-–]\d+)\s*min(?:ute)?s?\s*\(([^)]+)\)', re.IGNORECASE),
    # "all sessions are 45 minutes" or "sessions are 60 minutes long" or "sessions will be 60 minutes"
    re.compile(r'(?:all\s+)?sessions?\s+(?:are|is|will\s+be)\s+(\d+)\s*min(?:ute)?s?', re.IGNORECASE),
    # "30-minute sessions" or "60 minute sessions"
    re.compile(r'(\d+[-–]?\d*)[- ]min(?:ute)?s?\s*(session|talk|presentation)s?', re.IGNORECASE),
    # "4 hour workshops" or "half-day workshop"
    re.compile(r'(\d+|half)[- ]?(hour|hr|day)\s*(workshop)s?', re.IGNORECASE),
    # "host 30-minute sessions"
    re.compile(r'host\s+(\d+[-–]?\d*)[- ]?min(?:ute)?s?\s*(session|talk)s?', re.IGNORECASE),
    # "Duration: 45 minutes" or "Timeslot: 35 mins"
    re.compile(r'(?:duration|timeslot)[:\s]+(\d+[-–]?\d*)\s*min', re.IGNORECASE),
    # "Talks typically run 20-30 minutes"
    re.compile(r'(talk|session)s?\s+(?:typically\s+)?run\s+(\d+[-–]?\d*)\s*min', re.IGNORECASE),
    # Italian: "sessioni di 40 min" or "sessione di 50 minuti"
    re.compile(r'(session[ie])\s+di\s+(\d+[-–]?\d*)\s*min', re.IGNORECASE),
    # Spanish: "sesiones de 50 minutos" or "Duración: 30 a 45 minutos"
    re.compile(r'(?:sesion[es]*|duración)[:\s]+(?:de\s+)?(\d+)(?:\s*a\s*(\d+))?\s*min', re.IGNORECASE),
    # "15 or 45 minutes" or "20-30 minutes"
    re.compile(r'(?:can\s+be\s+)?(\d+)(?:\s*(?:or|-|to)\s*(\d+))?\s*min(?:ute)?s?', re.IGNORECASE),
    # "25-minute Take-Off Talk" or "75-minute Peer-to-Peer"
    re.compile(r'(\d+)[- ]min(?:ute)?s?\s+([A-Z][a-zA-Z\s-]+(?:Talk|Session|Round))', re.IGNORECASE),
]

# Attendance patterns - require at least 3 digits to avoid false positives
ATTENDANCE_PATTERNS = [
    # "10,000+" or "10000+" - require comma or 4+ digits
    re.compile(r'(\d{1,3},\d{3}\+?|\d{4,}\+?)\s*(?:attendees?|participants?|people|developers?|professionals?)', re.IGNORECASE),
    # "approximately 250 participants" - require 3+ digits
    re.compile(r'(?:approximately|approx\.?|around|about|nearly|over|more\s+than)\s*(\d{3,}(?:,\d{3})*)\s*(?:attendees?|participants?|people|developers?)?', re.IGNORECASE),
    # "expected attendance: 500" - require 3+ digits
    re.compile(r'(?:expected\s+)?attendance[:\s]+(\d{3,}(?:,\d{3})*\+?)', re.IGNORECASE),
    # "drew 2,000 attendees" with commas or 4+ digits
    re.compile(r'drew\s+(?:nearly\s+)?(\d{1,3},\d{3}|\d{4,})\s*(?:attendees?)?', re.IGNORECASE),
    # "200+ attendees" - only if 3+ digits
    re.compile(r'(\d{3,}\+)\s*(?:attendees?|participants?|people|developers?)', re.IGNORECASE),
    # "audience of 500" or "capacity of 500"
    re.compile(r'(?:audience\s+of|capacity\s+of)\s+(\d{3,}(?:,\d{3})*)', re.IGNORECASE),
    # "capacity up to 300 participants"
    re.compile(r'capacity\s+(?:up\s+to|of)\s+(\d{3,}(?:,\d{3})*)\s*(?:attendees?|participants?|people)?', re.IGNORECASE),
    # "500-person event"
    re.compile(r'(\d{3,})[- ]person\s+(?:event|conference)', re.IGNORECASE),
    # "aim for 200 people" or "expect 300 attendees"
    re.compile(r'(?:aim|expect|target)\s+(?:for\s+)?(\d{3,})\s*(?:attendees?|participants?|people)?', re.IGNORECASE),
]

# Speaker benefit patterns
BENEFIT_PATTERNS = {
    'travel': [
        # "$500-800 flight reimbursement"
        re.compile(r'\$\s*(\d+(?:\s*[-–]\s*\d+)?)\s*(?:flight|travel|airfare)', re.IGNORECASE),
        # "travel covered", "travel expenses covered"
        re.compile(r'travel\s*(?:expenses?)?\s*(?:are\s+)?covered', re.IGNORECASE),
        # "up to $800 for travel"
        re.compile(r'up\s+to\s+\$\s*(\d+)\s*(?:for\s+)?(?:flight|travel)', re.IGNORECASE),
        # "cover travel", "covering travel"
        re.compile(r'cover(?:ing)?\s+(?:your\s+)?travel', re.IGNORECASE),
        # "travel assistance", "travel support"
        re.compile(r'travel\s+(?:assistance|support|reimbursement)', re.IGNORECASE),
        # "we pay for travel"
        re.compile(r'(?:we\s+)?pay\s+(?:for\s+)?(?:your\s+)?travel', re.IGNORECASE),
    ],
    'hotel': [
        # "2-3 hotel nights"
        re.compile(r'(\d+(?:\s*[-–]\s*\d+)?)\s*(?:hotel\s+)?nights?', re.IGNORECASE),
        # "three hotel nights" (word numbers)
        re.compile(r'(one|two|three|four|five)\s+(?:hotel\s+)?nights?\s+covered', re.IGNORECASE),
        # "accommodation covered"
        re.compile(r'(?:accommodation|hotel|lodging)\s*(?:expenses?)?\s*(?:are\s+)?covered', re.IGNORECASE),
        # "complimentary hotel night"
        re.compile(r'complimentary\s*(?:hotel\s+)?night', re.IGNORECASE),
        # "cover accommodation"
        re.compile(r'cover(?:ing)?\s+(?:your\s+)?(?:accommodation|hotel|lodging)', re.IGNORECASE),
        # "we provide accommodation"
        re.compile(r'(?:we\s+)?provide\s+(?:hotel|accommodation|lodging)', re.IGNORECASE),
    ],
    'ticket': [
        # "free for speakers", "free admission"
        re.compile(r'free\s+(?:for\s+speakers?|admission|entry|ticket|attendance)', re.IGNORECASE),
        # "complimentary ticket"
        re.compile(r'complimentary\s+(?:conference\s+)?(?:ticket|pass|entry|attendance)', re.IGNORECASE),
        # "event fee: free"
        re.compile(r'event\s+fee[:\s]+free', re.IGNORECASE),
        # "free-to-attend" or "free to attend"
        re.compile(r'free[- ]?to[- ]?attend', re.IGNORECASE),
        # "free community event" or "free conference" or "free, community-driven event"
        re.compile(r'free,?\s+(?:community[- ]?driven\s+)?(?:community\s+)?(?:event|conference)', re.IGNORECASE),
        # "speakers attend free"
        re.compile(r'speakers?\s+(?:attend|get\s+in)\s+free', re.IGNORECASE),
        # "free ticket for speakers"
        re.compile(r'free\s+(?:conference\s+)?ticket\s+(?:for\s+)?speakers?', re.IGNORECASE),
    ],
    'payment': [
        # "speakers will be paid"
        re.compile(r'(?:speakers?\s+)?will\s+be\s+(?:paid|compensated)', re.IGNORECASE),
        # "honorarium"
        re.compile(r'(?:speaker\s+)?honorarium', re.IGNORECASE),
    ],
}

# Negative patterns that indicate benefit is NOT provided
BENEFIT_NEGATIVE_PATTERNS = {
    'travel': [
        re.compile(r'(?:not|no|don\'t|won\'t|cannot)\s+(?:cover(?:ing)?|provid(?:e|ing)|pay(?:ing)?)\s+(?:any\s+)?travel', re.IGNORECASE),
        re.compile(r'travel\s+(?:expenses?\s+)?(?:are\s+)?not\s+(?:covered|provided|paid)', re.IGNORECASE),
        re.compile(r'(?:we\'re|we\s+are)\s+not\s+covering\s+(?:any\s+)?travel', re.IGNORECASE),
    ],
    'hotel': [
        re.compile(r'(?:not|no|don\'t|won\'t|cannot)\s+(?:cover(?:ing)?|provid(?:e|ing)|pay(?:ing)?)\s+(?:any\s+)?(?:accommodation|hotel|lodging)', re.IGNORECASE),
        re.compile(r'(?:accommodation|hotel|lodging)\s+(?:expenses?\s+)?(?:are\s+)?not\s+(?:covered|provided|paid)', re.IGNORECASE),
    ],
}

# Target audience patterns
AUDIENCE_PATTERNS = [
    # "attendees with at least three years of experience"
    re.compile(r'(?:attendees?|audience)\s+with\s+(?:at\s+least\s+)?(\d+\+?\s*years?(?:\s+of)?\s+experience)', re.IGNORECASE),
    # "target audience: developers"
    re.compile(r'(?:target\s+)?audience[:\s]+([^.]+)', re.IGNORECASE),
]

# Date patterns for CFP and event dates
# Format: "Call opens at 12:00 AM 09 Jan 2026" or "Call closes at 11:59 PM 28 Feb 2026"
CFP_DATE_PATTERNS = {
    'cfp_opens': re.compile(r'Call\s+opens\s+at\s+\d{1,2}:\d{2}\s*[AP]M\s+(\d{1,2}\s+\w{3}\s+\d{4})', re.IGNORECASE),
    'cfp_closes': re.compile(r'Call\s+closes\s+at\s+\d{1,2}:\d{2}\s*[AP]M\s+(\d{1,2}\s+\w{3}\s+\d{4})', re.IGNORECASE),
    'event_date': re.compile(r'event\s+date\s+(\d{1,2}\s+\w{3}\s+\d{4})', re.IGNORECASE),
    'event_starts': re.compile(r'event\s+starts\s+(\d{1,2}\s+\w{3}\s+\d{4})', re.IGNORECASE),
    'event_ends': re.compile(r'event\s+ends\s+(\d{1,2}\s+\w{3}\s+\d{4})', re.IGNORECASE),
}

# Timezone pattern
TIMEZONE_PATTERN = re.compile(r'([A-Z][^(]+)\s*\(UTC[+-]\d{2}:\d{2}\)\s*timezone', re.IGNORECASE)

# Email pattern - regex is appropriate here (well-defined format)
EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

# Location pattern - Sessionize has consistent "location ... website" structure
# Regex captures full address (venue + street + city + country)
# Tested: 93% success rate on 30 pages, captures full address vs NER which only gets city/country
LOCATION_PATTERN = re.compile(
    r'location\s+(.+?)(?:\s+website|\s+event\s+(?:date|starts)|We\'ve|🚀|\$)',
    re.IGNORECASE
)

# Website pattern
WEBSITE_PATTERN = re.compile(r'website\s+([\w.-]+\.[a-z]{2,}(?:/[\w./-]*)?)', re.IGNORECASE)


def extract_location_entities(location_raw: str) -> dict:
    """Use spaCy NER to extract city/country from raw location string.

    Optional post-processing for search facets. Call only when needed
    as spaCy loading has overhead.

    Returns: {'city': str|None, 'country': str|None}
    """
    try:
        import spacy
        nlp = spacy.load('en_core_web_sm')
    except (ImportError, OSError):
        return {'city': None, 'country': None}

    doc = nlp(location_raw)
    gpes = [ent.text for ent in doc.ents if ent.label_ == 'GPE']

    # Heuristic: last GPE is usually country, second-to-last is city
    city = None
    country = None
    if len(gpes) >= 2:
        country = gpes[-1]
        city = gpes[-2]
    elif len(gpes) == 1:
        # Could be city or country - assume country for single GPE
        country = gpes[0]

    return {'city': city, 'country': country}


async def geocode_location(location_raw: str) -> Optional[tuple[float, float]]:
    """Geocode location using OSM Nominatim, fallback to NER city/country.

    Returns: (lat, lng) or None if geocoding fails.
    """
    import httpx

    async def nominatim_geocode(query: str) -> Optional[tuple[float, float]]:
        """Query OSM Nominatim API."""
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
        }
        headers = {
            "User-Agent": "CFPPipeline/1.0 (conference discovery tool)"
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return (float(data[0]["lat"]), float(data[0]["lon"]))
        except Exception as e:
            console.print(f"[dim]Nominatim error: {e}[/dim]")
        return None

    # Try full location_raw first (most accurate)
    result = await nominatim_geocode(location_raw)
    if result:
        return result

    # Fallback: extract city/country with NER and geocode that
    entities = extract_location_entities(location_raw)
    if entities.get('city') and entities.get('country'):
        fallback_query = f"{entities['city']}, {entities['country']}"
        result = await nominatim_geocode(fallback_query)
        if result:
            return result

    # Last resort: just country
    if entities.get('country'):
        result = await nominatim_geocode(entities['country'])
        if result:
            return result

    return None


def detect_event_format(data: 'SessionizeData') -> str:
    """Detect event format using multiple signals from SessionizeData.

    Returns: 'virtual', 'in-person', or 'hybrid'

    Scoring approach (avoids brittle single-signal detection):
    - Location = "Online"/"Virtual" → strong virtual signal
    - Detailed venue location → strong physical signal
    - Travel/hotel benefits → strong physical signal
    - Empty location + no benefits → weak virtual signal
    """
    loc = (data.location_raw or '').lower().strip()
    text = (data.clean_text or '').lower()

    # === STRONG SIGNALS (definitive) ===

    # Explicit virtual location
    virtual_locations = ['online', 'virtual', 'worldwide', 'global', 'digital', 'remote']
    if loc in virtual_locations:
        return 'virtual'

    # Explicit hybrid mention
    if 'hybrid' in loc or 'hybrid' in text[:500]:
        return 'hybrid'

    # Travel/hotel benefits = definitely physical
    if data.benefits.travel or data.benefits.hotel:
        return 'in-person'

    # Detailed venue location (e.g., "Convention Center City, Country")
    # Physical locations are typically 20+ chars with venue names
    if len(loc) > 20 and ',' in loc:
        return 'in-person'

    # === WEAK SIGNALS (for edge cases) ===

    # Physical keywords in text
    physical_keywords = ['venue', 'on-site', 'in person', 'in-person', 'catering', 'lunch', 'dinner']
    if any(kw in text for kw in physical_keywords):
        return 'in-person'

    # Virtual keywords in text
    virtual_keywords = ['online event', 'virtual event', 'join online', 'fully online', 'virtual conference']
    if any(kw in text for kw in virtual_keywords):
        return 'virtual'

    # Has any location at all → likely physical
    if loc and loc not in ['', 'tba', 'tbd', 'to be announced']:
        return 'in-person'

    # Default: can't determine (treat as in-person to avoid false positives)
    return 'in-person'


# Format name normalization for deduplication
FORMAT_ALIASES = {
    'fulllengthpresentation': 'Talk',
    'fulllengthpresentations': 'Talk',
    'fulllengthsession': 'Talk',
    'fulllengthsessions': 'Talk',
    'fulllengttalk': 'Talk',
    'fulllengthtalks': 'Talk',
    'standardtalk': 'Talk',
    'standardtalks': 'Talk',
    'standardpresentation': 'Talk',
    'standardpresentations': 'Talk',
    'standardsession': 'Talk',
    'regulartalk': 'Talk',
    'regulartalks': 'Talk',
    'regularsession': 'Talk',
    'breakoutsession': 'Breakout Session',
    'breakoutsessions': 'Breakout Session',
    'techsession': 'Tech Session',
    'techsessions': 'Tech Session',
    'lightningtalk': 'Lightning Talk',
    'lightningtalks': 'Lightning Talk',
    'lightningpresentation': 'Lightning Talk',
    'lightningpresentations': 'Lightning Talk',
    'keynote': 'Keynote',
    'keynotes': 'Keynote',
    'keynotetalk': 'Keynote',
    'keynotetalks': 'Keynote',
    'keynotesession': 'Keynote',
    'keynotesessions': 'Keynote',
    'workshop': 'Workshop',
    'workshops': 'Workshop',
    'workshopsession': 'Workshop',
    'workshopsessions': 'Workshop',
    'fulldayworkshop': 'Full-Day Workshop',
    'fulldayworkshops': 'Full-Day Workshop',
    'panel': 'Panel',
    'panels': 'Panel',
    'paneldiscussion': 'Panel',
    'paneldiscussions': 'Panel',
    'panelsession': 'Panel',
    'panelsessions': 'Panel',
    'ignite': 'Ignite Talk',
    'ignites': 'Ignite Talk',
    'ignitetalk': 'Ignite Talk',
    'ignitetalks': 'Ignite Talk',
    'ignitesession': 'Ignite Talk',
    'ignitesessions': 'Ignite Talk',
    'deepdive': 'Deep Dive',
    'deepdives': 'Deep Dive',
    'deepdivesession': 'Deep Dive',
    'deepdivesessions': 'Deep Dive',
}


def normalize_format_name(name: str) -> str:
    """Normalize session format name for deduplication."""
    key = name.lower().replace(' ', '').replace('-', '')
    return FORMAT_ALIASES.get(key, name.title())


def extract_grabby(text: str, url: str) -> SessionizeData:
    """Pass 1: Grabby extraction using regex patterns."""
    data = SessionizeData(url=url)

    # Clean text for matching
    text_clean = re.sub(r'\s+', ' ', text)

    # Check if CFP is closed
    if re.search(r'call\s+(?:for\s+)?(?:speakers?|papers?|proposals?)\s+is\s+closed', text_clean, re.IGNORECASE):
        data.is_open = False

    # Extract session formats
    seen_formats = {}  # Map normalized name -> SessionFormat (keep best one with duration)

    # Standard patterns (name, duration)
    for pattern in SESSION_FORMAT_PATTERNS:
        for match in pattern.finditer(text_clean):
            raw_name = match.group(1).strip()
            duration = match.group(2).strip() if match.group(2) else None

            # Normalize format name
            normalized = normalize_format_name(raw_name)

            # Keep the version with duration if we have one
            if normalized not in seen_formats or (duration and not seen_formats[normalized].duration):
                seen_formats[normalized] = SessionFormat(name=normalized, duration=duration)

    # Alternative patterns with different group order
    for pattern in SESSION_FORMAT_PATTERNS_ALT:
        for match in pattern.finditer(text_clean):
            g1 = match.group(1).strip() if match.group(1) else ''
            g2 = match.group(2).strip() if match.lastindex >= 2 and match.group(2) else ''

            # Determine which is name and which is duration
            if g1.isdigit() or re.match(r'^\d', g1):
                # First group is duration
                duration = g1 + ' min'
                raw_name = g2 if g2 and g2.lower() != 'long' else 'Session'
            else:
                # First group is name
                raw_name = g1
                duration = g2 + ' min' if g2 else None

            # Skip if we couldn't determine a meaningful name
            if not raw_name or raw_name.lower() in ('long', ''):
                raw_name = 'Session'

            normalized = normalize_format_name(raw_name)

            if normalized not in seen_formats or (duration and not seen_formats[normalized].duration):
                seen_formats[normalized] = SessionFormat(name=normalized, duration=duration)

    data.session_formats = list(seen_formats.values())

    # Extract attendance
    for pattern in ATTENDANCE_PATTERNS:
        match = pattern.search(text_clean)
        if match:
            data.attendance = match.group(1)
            break

    # Extract speaker benefits
    # First check for negative patterns (not provided)
    negative_benefits = set()
    for benefit_type, patterns in BENEFIT_NEGATIVE_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text_clean):
                negative_benefits.add(benefit_type)
                break

    for benefit_type, patterns in BENEFIT_PATTERNS.items():
        # Skip if explicitly stated as NOT provided
        if benefit_type in negative_benefits:
            continue

        for pattern in patterns:
            match = pattern.search(text_clean)
            if match:
                if benefit_type == 'travel':
                    if match.groups() and match.group(1) and match.group(1).isdigit():
                        data.benefits.travel = f"${match.group(1)}"
                    else:
                        data.benefits.travel = "covered"
                elif benefit_type == 'hotel':
                    if match.groups() and match.group(1) and match.group(1)[0].isdigit():
                        data.benefits.hotel = f"{match.group(1)} nights"
                    else:
                        data.benefits.hotel = "covered"
                elif benefit_type == 'ticket':
                    data.benefits.ticket = True
                elif benefit_type == 'payment':
                    data.benefits.payment = "paid"
                break

    # Extract target audience
    for pattern in AUDIENCE_PATTERNS:
        match = pattern.search(text_clean)
        if match:
            data.target_audience = match.group(1).strip()[:200]
            break

    # NOTE: dates, location, email, website are now extracted in scrape_sessionize
    # using TextCleaner (unified extraction + cleanup approach)

    return data


# =============================================================================
# PASS 2: STRUCTURED HTML PARSING
# =============================================================================

def extract_structured(html: str, data: SessionizeData) -> SessionizeData:
    """Pass 2: Structured extraction using BeautifulSoup."""
    soup = BeautifulSoup(html, 'html.parser')

    # Extract tracks from submission form if present
    # Sessionize often has track categories in select elements or radio buttons
    track_selects = soup.find_all('select', {'name': re.compile(r'track|category|topic', re.I)})
    for select in track_selects:
        for option in select.find_all('option'):
            track_name = option.get_text(strip=True)
            if track_name and track_name not in ['Select', 'Choose', '--']:
                data.tracks.append(track_name)

    # Also look for track lists in content
    track_headers = soup.find_all(['h2', 'h3', 'h4', 'strong'], string=re.compile(r'track|topic|categor', re.I))
    for header in track_headers:
        # Look for subsequent list
        next_el = header.find_next(['ul', 'ol'])
        if next_el and next_el.find_parent() == header.find_parent():
            for li in next_el.find_all('li'):
                track = li.get_text(strip=True)
                if track and len(track) < 100 and track not in data.tracks:
                    data.tracks.append(track)

    # Extract description from meta or main content
    meta_desc = soup.find('meta', {'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        data.description = meta_desc['content'][:500]

    # Look for max submissions limit
    max_match = re.search(r'max(?:imum)?\s*(\d+)\s*(?:submission|proposal)', html, re.I)
    if max_match:
        data.max_submissions = int(max_match.group(1))

    return data


# =============================================================================
# MAIN EXTRACTION FLOW
# =============================================================================

def is_sessionize_url(url: Optional[str]) -> bool:
    """Check if URL is a Sessionize CFP page."""
    if not url:
        return False
    parsed = urlparse(url)
    return 'sessionize.com' in parsed.netloc.lower()


def extract_sessionize_slug(url: str) -> Optional[str]:
    """Extract the event slug from a Sessionize URL."""
    # https://sessionize.com/kubecon-2026 -> kubecon-2026
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if path and '/' not in path:
        return path
    return None


async def scrape_sessionize(url: str) -> SessionizeData:
    """Scrape a Sessionize page and extract CFP data.

    Multi-pass extraction:
    1. Fetch HTML
    2. Pass 1: Grabby regex extraction (content stays in text)
    3. Pass 2: Structured HTML parsing
    4. Pass 3: Metadata extraction + cleanup (extract AND remove)
    """
    data = SessionizeData(url=url)

    # Fetch HTML
    html = await fetch_url(url, use_cache=True)
    if not html:
        data.error = "fetch_failed"
        return data

    # Get plain text for regex matching
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style elements
    for tag in soup(['script', 'style', 'nav', 'footer']):
        tag.decompose()

    text = soup.get_text(separator=' ')
    text_normalized = ' '.join(text.split())

    # Pass 1: Grabby extraction (session formats, benefits, attendance)
    data = extract_grabby(text_normalized, url)

    # Pass 2: Structured extraction (tracks from HTML)
    data = extract_structured(html, data)

    # Pass 3: Metadata extraction + unified cleanup using TextCleaner
    cleaner = TextCleaner(text_normalized)

    # Extract metadata AND mark for removal (unified approach)
    data.cfp_opens = cleaner.extract_and_remove(CFP_DATE_PATTERNS['cfp_opens'])
    data.cfp_closes = cleaner.extract_and_remove(CFP_DATE_PATTERNS['cfp_closes'])
    data.event_start = cleaner.extract_and_remove(CFP_DATE_PATTERNS['event_date']) or \
                       cleaner.extract_and_remove(CFP_DATE_PATTERNS['event_starts'])
    data.event_end = cleaner.extract_and_remove(CFP_DATE_PATTERNS['event_ends'])
    data.location_raw = cleaner.extract_and_remove(LOCATION_PATTERN)
    data.website = cleaner.extract_and_remove(WEBSITE_PATTERN)
    data.contact_email = cleaner.extract_and_remove(EMAIL_PATTERN)

    # Apply static boilerplate removal (login modal, headers, etc.)
    _apply_static_cleanup(cleaner)

    # Get clean text - naturally result of extraction + cleanup
    data.clean_text = cleaner.get_clean_text(max_length=4000)

    # Detect event format (virtual/in-person/hybrid) using multiple signals
    data.event_format = detect_event_format(data)

    return data


def sessionize_data_to_cfp_fields(data: SessionizeData) -> dict:
    """Convert SessionizeData to CFP field updates."""
    updates = {
        'sessionize_url': data.url,
        'sessionize_enriched': True,
    }

    if data.attendance:
        updates['attendance'] = data.attendance

    if data.session_formats:
        updates['session_formats'] = [
            {'name': sf.name, 'duration': sf.duration}
            for sf in data.session_formats
        ]

    if data.benefits.travel or data.benefits.hotel or data.benefits.ticket or data.benefits.payment:
        benefits = {}
        if data.benefits.travel:
            benefits['travel'] = data.benefits.travel
        if data.benefits.hotel:
            benefits['hotel'] = data.benefits.hotel
        if data.benefits.ticket:
            benefits['ticket'] = True
        if data.benefits.payment:
            benefits['payment'] = data.benefits.payment
        updates['speaker_benefits'] = benefits

    if data.target_audience:
        updates['target_audience'] = data.target_audience

    if data.tracks:
        updates['tracks'] = data.tracks[:20]  # Limit to 20 tracks

    # Merge description if we got one and CFP doesn't have one
    if data.description:
        updates['_sessionize_description'] = data.description

    # Store clean text for later augmentation (translation, LLM re-extraction)
    if data.clean_text:
        updates['_sessionize_full_text'] = data.clean_text

    # Event format (virtual/in-person/hybrid)
    if data.event_format:
        updates['event_format'] = data.event_format

    # Store location_raw for geocoding (done in enrich_cfp_with_sessionize)
    if data.location_raw:
        updates['_location_raw'] = data.location_raw

    return updates


async def enrich_cfp_with_sessionize(cfp: CFP) -> CFP:
    """Enrich a single CFP with Sessionize data.

    Checks cfp_url for Sessionize URL and scrapes if found.
    """
    # Check if already enriched
    if cfp.sessionize_enriched:
        return cfp

    # Find Sessionize URL
    sessionize_url = None
    if is_sessionize_url(cfp.cfp_url):
        sessionize_url = cfp.cfp_url
    elif is_sessionize_url(cfp.url):
        sessionize_url = cfp.url

    if not sessionize_url:
        return cfp

    # Scrape
    console.print(f"[dim]Sessionize: {cfp.name[:40]}...[/dim]")
    data = await scrape_sessionize(sessionize_url)

    if data.error:
        console.print(f"[yellow]Sessionize error for {cfp.name}: {data.error}[/yellow]")
        return cfp

    # Apply updates
    updates = sessionize_data_to_cfp_fields(data)
    location_raw = None

    for key, value in updates.items():
        if key.startswith('_'):
            # Special handling for conditional updates
            if key == '_sessionize_description' and not cfp.description:
                cfp.description = value
            elif key == '_sessionize_full_text' and not cfp.full_text:
                cfp.full_text = value
            elif key == '_location_raw':
                location_raw = value
        else:
            setattr(cfp, key, value)

    # Geocoding: populate _geoloc and enrich location model
    if location_raw and data.event_format != 'virtual':
        # Geocode to lat/lng
        coords = await geocode_location(location_raw)
        if coords:
            from cfp_pipeline.models import GeoLoc
            cfp._geoloc = GeoLoc(lat=coords[0], lng=coords[1])

        # Enrich location model with NER-extracted city/country
        entities = extract_location_entities(location_raw)
        if entities.get('city') and not cfp.location.city:
            cfp.location.city = entities['city']
        if entities.get('country') and not cfp.location.country:
            cfp.location.country = entities['country']
        if not cfp.location.raw:
            cfp.location.raw = location_raw

    return cfp


async def enrich_cfps_with_sessionize(
    cfps: list[CFP],
    limit: Optional[int] = None,
    skip_existing: bool = True,
    max_concurrent: int = 5,
    delay: float = 0.5,
) -> list[CFP]:
    """Enrich multiple CFPs with Sessionize data.

    Args:
        cfps: List of CFPs to enrich
        limit: Max CFPs to process (None = all)
        skip_existing: Skip CFPs already enriched
        max_concurrent: Max concurrent requests
        delay: Delay between requests (rate limiting)

    Returns:
        All CFPs (enriched + untouched)
    """
    # Find CFPs with Sessionize URLs
    sessionize_cfps = [
        cfp for cfp in cfps
        if is_sessionize_url(cfp.cfp_url) or is_sessionize_url(cfp.url)
    ]

    if skip_existing:
        sessionize_cfps = [cfp for cfp in sessionize_cfps if not cfp.sessionize_enriched]

    if limit:
        sessionize_cfps = sessionize_cfps[:limit]

    console.print(f"[cyan]Enriching {len(sessionize_cfps)} CFPs with Sessionize data...[/cyan]")

    if not sessionize_cfps:
        return cfps

    # Process with semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_with_rate_limit(cfp: CFP) -> CFP:
        async with semaphore:
            result = await enrich_cfp_with_sessionize(cfp)
            await asyncio.sleep(delay)
            return result

    # Create tasks
    tasks = [enrich_with_rate_limit(cfp) for cfp in sessionize_cfps]
    enriched = await asyncio.gather(*tasks)

    # Build result - replace enriched CFPs in original list
    enriched_by_id = {cfp.object_id: cfp for cfp in enriched}
    result = []
    for cfp in cfps:
        if cfp.object_id in enriched_by_id:
            result.append(enriched_by_id[cfp.object_id])
        else:
            result.append(cfp)

    # Stats
    enriched_count = sum(1 for cfp in result if cfp.sessionize_enriched)
    console.print(f"[green]Sessionize enrichment complete: {enriched_count} CFPs enriched[/green]")

    return result


# =============================================================================
# CLI HELPERS
# =============================================================================

async def test_scrape(url: str) -> None:
    """Test scraping a single Sessionize URL."""
    console.print(f"[cyan]Scraping: {url}[/cyan]\n")

    data = await scrape_sessionize(url)

    if data.error:
        console.print(f"[red]Error: {data.error}[/red]")
        return

    console.print(f"[bold]Status:[/bold] {'Open' if data.is_open else 'Closed'}")

    if data.attendance:
        console.print(f"[bold]Attendance:[/bold] {data.attendance}")

    if data.session_formats:
        console.print(f"\n[bold]Session Formats:[/bold]")
        for sf in data.session_formats:
            duration_str = f" ({sf.duration})" if sf.duration else ""
            console.print(f"  - {sf.name}{duration_str}")

    console.print(f"\n[bold]Speaker Benefits:[/bold]")
    if data.benefits.travel:
        console.print(f"  Travel: {data.benefits.travel}")
    if data.benefits.hotel:
        console.print(f"  Hotel: {data.benefits.hotel}")
    if data.benefits.ticket:
        console.print(f"  Free ticket: Yes")
    if data.benefits.payment:
        console.print(f"  Payment: {data.benefits.payment}")

    if data.tracks:
        console.print(f"\n[bold]Tracks:[/bold]")
        for track in data.tracks[:10]:
            console.print(f"  - {track}")

    if data.target_audience:
        console.print(f"\n[bold]Target Audience:[/bold] {data.target_audience}")

    if data.max_submissions:
        console.print(f"[bold]Max Submissions:[/bold] {data.max_submissions}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m cfp_pipeline.enrichers.sessionize <sessionize_url>")
        print("Example: python -m cfp_pipeline.enrichers.sessionize https://sessionize.com/kubecon-2026")
        sys.exit(1)

    url = sys.argv[1]
    asyncio.run(test_scrape(url))
