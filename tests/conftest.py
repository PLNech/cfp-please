"""Shared test fixtures and configuration."""

import pytest
from cfp_pipeline.models import CFP, Location, GeoLoc


@pytest.fixture
def sample_cfp() -> CFP:
    """Create a sample CFP for testing."""
    cfp = CFP(
        objectID="test-123",
        name="ReactConf 2026",
        description="Annual React conference for frontend developers",
        url="https://reactconf.com",
        cfpUrl="https://sessionize.com/reactconf-2026",
        cfpStartDate=1704067200,
        cfpEndDate=1706745600,
        cfpStartDateISO="2024-01-01",
        cfpEndDateISO="2024-02-01",
        eventStartDate=1712016000,
        eventEndDate=1712188800,
        eventStartDateISO="2024-04-01",
        eventEndDateISO="2024-04-03",
        location=Location(
            city="Chicago",
            state="Illinois",
            country="USA",
            region="Midwest",
            continent="North America",
            raw="Chicago, IL, USA",
        ),
        topics=["React", "JavaScript", "Frontend"],
        topicsNormalized=["frontend", "javascript"],
        source="callingallpapers",
        enriched=True,
    )
    cfp._geoloc = GeoLoc(lat=41.8781, lng=-87.6298)
    return cfp
