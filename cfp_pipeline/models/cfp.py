"""Data models for CFP pipeline."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class Location(BaseModel):
    """Normalized location data."""

    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None  # e.g., "Midwest", "Western Europe"
    continent: Optional[str] = None
    raw: str = ""  # Original location string


class GeoLoc(BaseModel):
    """Algolia-compatible geolocation."""

    lat: float
    lng: float


class CFP(BaseModel):
    """Call for Papers record."""

    # Identity
    object_id: str = Field(alias="objectID")
    name: str
    description: Optional[str] = None

    # URLs
    url: Optional[str] = None  # Event website
    cfp_url: Optional[str] = None  # Submission URL
    icon_url: Optional[str] = None

    # CFP Dates - both timestamp (for filtering) and ISO (for date_aware agent)
    cfp_start_date: Optional[int] = None  # Unix timestamp
    cfp_end_date: Optional[int] = None  # Unix timestamp
    cfp_start_date_iso: Optional[str] = None  # "2026-01-15" for agent date_aware
    cfp_end_date_iso: Optional[str] = None  # "2026-02-28" for agent date_aware

    # Event Dates
    event_start_date: Optional[int] = None
    event_end_date: Optional[int] = None
    event_start_date_iso: Optional[str] = None
    event_end_date_iso: Optional[str] = None

    # Location
    location: Location = Field(default_factory=Location)
    _geoloc: Optional[GeoLoc] = None

    # Topics (from source)
    topics: list[str] = Field(default_factory=list)  # Original tags
    topics_normalized: list[str] = Field(default_factory=list)  # Mapped to taxonomy

    # Enrichment fields (from LLM)
    languages: list[str] = Field(default_factory=list)  # Programming languages
    audience_level: Optional[str] = None  # beginner, intermediate, advanced, all-levels
    event_format: Optional[str] = None  # in-person, virtual, hybrid
    talk_types: list[str] = Field(default_factory=list)  # talk, workshop, lightning, etc.
    industries: list[str] = Field(default_factory=list)  # fintech, healthcare, etc.
    technologies: list[str] = Field(default_factory=list)  # React, Kubernetes, etc.

    # Full text for search (cleaned page content)
    full_text: Optional[str] = None

    # Intel data (from HN, GitHub, Reddit, DEV.to, DDG)
    popularity_score: Optional[float] = None  # 0-100 aggregated score

    # Hacker News
    hn_stories: int = 0  # Story count
    hn_points: int = 0  # Total points
    hn_story_titles: list[str] = Field(default_factory=list)  # Top story titles (searchable)
    hn_comments: list[str] = Field(default_factory=list)  # Top comments (max 20)

    # GitHub
    github_repos: int = 0  # Related repo count
    github_stars: int = 0  # Total stars
    github_languages: list[str] = Field(default_factory=list)  # Top languages
    github_topics: list[str] = Field(default_factory=list)  # Repo topics
    github_descriptions: list[str] = Field(default_factory=list)  # Top repo descriptions

    # Reddit
    reddit_posts: int = 0  # Post count
    reddit_subreddits: list[str] = Field(default_factory=list)  # Related subreddits
    reddit_titles: list[str] = Field(default_factory=list)  # Top post titles
    reddit_comments: list[str] = Field(default_factory=list)  # Top comments (max 20)

    # DEV.to
    devto_articles: int = 0  # Article count
    devto_tags: list[str] = Field(default_factory=list)  # Tags
    devto_titles: list[str] = Field(default_factory=list)  # Article titles

    # Aggregated
    intel_topics: list[str] = Field(default_factory=list)  # All topics from all sources
    intel_urls: list[str] = Field(default_factory=list)  # Related URLs

    # Meta
    source: str = "callingallpapers"
    enriched: bool = False  # True if LLM enrichment was applied
    intel_enriched: bool = False  # True if intel data was fetched
    last_updated: int = Field(default_factory=lambda: int(datetime.now().timestamp()))

    @computed_field
    @property
    def days_until_cfp_close(self) -> Optional[int]:
        """Days until CFP closes (negative if past)."""
        if not self.cfp_end_date:
            return None
        now = int(datetime.now().timestamp())
        diff_seconds = self.cfp_end_date - now
        return diff_seconds // 86400

    def to_algolia_record(self) -> dict:
        """Convert to Algolia-compatible dict."""
        record = {
            "objectID": self.object_id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "cfpUrl": self.cfp_url,
            "iconUrl": self.icon_url,
            # CFP dates (timestamp for filtering, ISO for date_aware agent)
            "cfpStartDate": self.cfp_start_date,
            "cfpEndDate": self.cfp_end_date,
            "cfpStartDateISO": self.cfp_start_date_iso,
            "cfpEndDateISO": self.cfp_end_date_iso,
            # Event dates
            "eventStartDate": self.event_start_date,
            "eventEndDate": self.event_end_date,
            "eventStartDateISO": self.event_start_date_iso,
            "eventEndDateISO": self.event_end_date_iso,
            # Location
            "location": self.location.model_dump(),
            # Topics
            "topics": self.topics,
            "topicsNormalized": self.topics_normalized,
            # Enrichment (from LLM)
            "languages": self.languages,
            "audienceLevel": self.audience_level,
            "eventFormat": self.event_format,
            "talkTypes": self.talk_types,
            "industries": self.industries,
            "technologies": self.technologies,
            # Full text for search
            "fullText": self.full_text,
            # Intel data (popularity, community, freeform text for search)
            "popularityScore": self.popularity_score,
            # HN
            "hnStories": self.hn_stories,
            "hnPoints": self.hn_points,
            "hnStoryTitles": self.hn_story_titles[:10],
            "hnComments": self.hn_comments[:20],  # Rich text for search
            # GitHub
            "githubRepos": self.github_repos,
            "githubStars": self.github_stars,
            "githubLanguages": self.github_languages,
            "githubTopics": self.github_topics,
            "githubDescriptions": self.github_descriptions[:10],
            # Reddit
            "redditPosts": self.reddit_posts,
            "redditSubreddits": self.reddit_subreddits,
            "redditTitles": self.reddit_titles[:10],
            "redditComments": self.reddit_comments[:20],  # Rich text for search
            # DEV.to
            "devtoArticles": self.devto_articles,
            "devtoTags": self.devto_tags,
            "devtoTitles": self.devto_titles[:10],
            # Aggregated
            "intelTopics": self.intel_topics,
            "intelUrls": self.intel_urls[:20],
            # Meta
            "source": self.source,
            "enriched": self.enriched,
            "intelEnriched": self.intel_enriched,
            "lastUpdated": self.last_updated,
        }
        if self._geoloc:
            record["_geoloc"] = self._geoloc.model_dump()
        # Filter out None/empty values
        return {k: v for k, v in record.items() if v is not None and v != [] and v != ""}


class RawCAPRecord(BaseModel):
    """Raw record from CallingAllPapers API."""

    name: str
    uri: str  # CFP submission URL
    dateCfpStart: Optional[str] = None
    dateCfpEnd: Optional[str] = None
    dateEventStart: Optional[str] = None
    dateEventEnd: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    eventUri: Optional[str] = None
    iconUri: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    lastChange: Optional[str] = None

    class Config:
        extra = "ignore"  # Ignore unknown fields from API
