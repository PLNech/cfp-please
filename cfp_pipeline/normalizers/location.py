"""Location normalizer with region mapping."""

import re
from typing import Optional

from cfp_pipeline.models import Location

# US state abbreviations to full names
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
US_STATE_NAMES = {v.lower(): v for v in US_STATES.values()}

# US Regions
US_REGIONS = {
    "Midwest": ["Illinois", "Indiana", "Iowa", "Kansas", "Michigan", "Minnesota",
                "Missouri", "Nebraska", "North Dakota", "Ohio", "South Dakota", "Wisconsin"],
    "Northeast": ["Connecticut", "Maine", "Massachusetts", "New Hampshire", "New Jersey",
                  "New York", "Pennsylvania", "Rhode Island", "Vermont"],
    "Southeast": ["Alabama", "Arkansas", "Delaware", "Florida", "Georgia", "Kentucky",
                  "Louisiana", "Maryland", "Mississippi", "North Carolina", "South Carolina",
                  "Tennessee", "Virginia", "West Virginia", "District of Columbia"],
    "Southwest": ["Arizona", "New Mexico", "Oklahoma", "Texas"],
    "West": ["Alaska", "California", "Colorado", "Hawaii", "Idaho", "Montana",
             "Nevada", "Oregon", "Utah", "Washington", "Wyoming"],
}

# Country to continent mapping (common ones)
COUNTRY_CONTINENTS = {
    # North America
    "USA": "North America", "United States": "North America", "US": "North America",
    "Canada": "North America", "Mexico": "North America",
    # Europe
    "UK": "Europe", "United Kingdom": "Europe", "England": "Europe", "Scotland": "Europe",
    "Germany": "Europe", "France": "Europe", "Spain": "Europe", "Italy": "Europe",
    "Netherlands": "Europe", "Belgium": "Europe", "Austria": "Europe", "Switzerland": "Europe",
    "Poland": "Europe", "Czech Republic": "Europe", "Czechia": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe",
    "Ireland": "Europe", "Portugal": "Europe", "Greece": "Europe", "Romania": "Europe",
    "Hungary": "Europe", "Bulgaria": "Europe", "Croatia": "Europe", "Slovenia": "Europe",
    "Slovakia": "Europe", "Serbia": "Europe", "Ukraine": "Europe", "Estonia": "Europe",
    "Latvia": "Europe", "Lithuania": "Europe", "Luxembourg": "Europe", "Malta": "Europe",
    "Cyprus": "Europe", "Iceland": "Europe",
    # Asia
    "Japan": "Asia", "China": "Asia", "India": "Asia", "South Korea": "Asia", "Korea": "Asia",
    "Singapore": "Asia", "Thailand": "Asia", "Vietnam": "Asia", "Malaysia": "Asia",
    "Indonesia": "Asia", "Philippines": "Asia", "Taiwan": "Asia", "Hong Kong": "Asia",
    "Israel": "Asia", "UAE": "Asia", "United Arab Emirates": "Asia", "Dubai": "Asia",
    # Oceania
    "Australia": "Oceania", "New Zealand": "Oceania",
    # South America
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America",
    "Colombia": "South America", "Peru": "South America",
    # Africa
    "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Egypt": "Africa",
}

# European regions
EUROPE_REGIONS = {
    "Western Europe": ["France", "Belgium", "Netherlands", "Luxembourg", "Germany",
                       "Austria", "Switzerland"],
    "Northern Europe": ["UK", "United Kingdom", "England", "Scotland", "Ireland",
                        "Sweden", "Norway", "Denmark", "Finland", "Iceland",
                        "Estonia", "Latvia", "Lithuania"],
    "Southern Europe": ["Spain", "Portugal", "Italy", "Greece", "Malta", "Cyprus",
                        "Croatia", "Slovenia"],
    "Eastern Europe": ["Poland", "Czech Republic", "Czechia", "Hungary", "Romania",
                       "Bulgaria", "Slovakia", "Serbia", "Ukraine"],
}


def get_us_region(state: str) -> Optional[str]:
    """Get US region for a state."""
    for region, states in US_REGIONS.items():
        if state in states:
            return region
    return None


def get_europe_region(country: str) -> Optional[str]:
    """Get European region for a country."""
    for region, countries in EUROPE_REGIONS.items():
        if country in countries:
            return region
    return None


def normalize_country(country_str: str) -> str:
    """Normalize country names."""
    normalized = country_str.strip()

    # Common aliases
    aliases = {
        "US": "USA",
        "United States": "USA",
        "United States of America": "USA",
        "UK": "United Kingdom",
        "England": "United Kingdom",
        "Scotland": "United Kingdom",
        "Wales": "United Kingdom",
        "Czechia": "Czech Republic",
        "Korea": "South Korea",
        "Holland": "Netherlands",
    }
    return aliases.get(normalized, normalized)


def parse_location_string(location_str: str) -> Location:
    """Parse a raw location string into structured Location.

    Handles formats like:
    - "Chicago, Illinois, USA"
    - "London, UK"
    - "Berlin, Germany"
    - "San Francisco, CA"
    - "Online"
    """
    if not location_str:
        return Location(raw=location_str)

    raw = location_str.strip()
    location = Location(raw=raw)

    # Handle "Online" or virtual
    if raw.lower() in ("online", "virtual", "remote", "worldwide"):
        location.city = "Online"
        return location

    # Split by comma and clean
    parts = [p.strip() for p in raw.split(",")]

    if len(parts) >= 3:
        # Assume: City, State/Region, Country
        location.city = parts[0]
        location.country = normalize_country(parts[-1])

        # Middle part could be state (US) or region
        middle = parts[-2]
        if middle.upper() in US_STATES:
            location.state = US_STATES[middle.upper()]
        elif middle.lower() in US_STATE_NAMES:
            location.state = US_STATE_NAMES[middle.lower()]
        else:
            location.state = middle

    elif len(parts) == 2:
        location.city = parts[0]
        second = parts[1]

        # Check if second part is US state abbreviation
        if second.upper() in US_STATES:
            location.state = US_STATES[second.upper()]
            location.country = "USA"
        elif second.lower() in US_STATE_NAMES:
            location.state = US_STATE_NAMES[second.lower()]
            location.country = "USA"
        else:
            # Assume it's a country
            location.country = normalize_country(second)

    elif len(parts) == 1:
        # Could be a city or country
        part = parts[0]
        if part in COUNTRY_CONTINENTS:
            location.country = normalize_country(part)
        else:
            location.city = part

    # Derive continent
    if location.country:
        location.continent = COUNTRY_CONTINENTS.get(location.country)

    # Derive region
    if location.state and location.country == "USA":
        location.region = get_us_region(location.state)
    elif location.country and location.continent == "Europe":
        location.region = get_europe_region(location.country)

    return location


def normalize_location(location: Location) -> Location:
    """Normalize and enrich a location object."""
    if location.raw and not location.city and not location.country:
        # Parse from raw string
        return parse_location_string(location.raw)

    # Enrich existing data
    if location.country:
        location.country = normalize_country(location.country)
        if not location.continent:
            location.continent = COUNTRY_CONTINENTS.get(location.country)

    if location.state and location.country == "USA":
        if not location.region:
            location.region = get_us_region(location.state)

    if location.country and location.continent == "Europe" and not location.region:
        location.region = get_europe_region(location.country)

    return location
