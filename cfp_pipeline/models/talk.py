"""Talk model for YouTube conference talks.

Stored in separate Algolia index with conference FK for rich querying.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Talk(BaseModel):
    """A conference talk from YouTube."""

    # Algolia object ID (youtube video ID)
    objectID: str = Field(description="YouTube video ID")

    # ===== CONFERENCE LINK =====
    conference_id: str = Field(description="FK to cfps index objectID")
    conference_name: str = Field(description="Denormalized for display/search")
    conference_slug: Optional[str] = Field(
        default=None,
        description="URL-friendly conference name for filtering"
    )

    # ===== TALK METADATA =====
    title: str
    speaker: Optional[str] = None
    speakers: list[str] = Field(
        default_factory=list,
        description="Multiple speakers if panel/duo"
    )
    description: Optional[str] = Field(
        default=None,
        description="Talk description/abstract (first 1000 chars)"
    )

    # ===== YOUTUBE DATA =====
    url: str = Field(description="YouTube watch URL")
    thumbnail_url: Optional[str] = None
    channel: Optional[str] = Field(
        default=None,
        description="YouTube channel name"
    )
    duration_seconds: Optional[int] = None
    view_count: Optional[int] = None

    # ===== FACETS =====
    year: Optional[int] = Field(
        default=None,
        description="Year talk was uploaded/presented"
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Inferred topics from title/description"
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages mentioned"
    )

    # ===== COMPUTED =====
    duration_minutes: Optional[int] = Field(
        default=None,
        description="Duration in minutes for display"
    )
    popularity_score: Optional[float] = Field(
        default=None,
        description="Normalized score based on views/age"
    )

    def model_post_init(self, __context) -> None:
        """Compute derived fields."""
        if self.duration_seconds and not self.duration_minutes:
            self.duration_minutes = self.duration_seconds // 60

        # Simple popularity: views per year since upload
        if self.view_count and self.year:
            from datetime import datetime
            years_old = max(1, datetime.now().year - self.year)
            self.popularity_score = self.view_count / years_old


def talk_to_algolia(talk: Talk) -> dict:
    """Convert Talk to Algolia record."""
    record = talk.model_dump(exclude_none=True)

    # Ensure required fields
    if 'objectID' not in record:
        raise ValueError("Talk must have objectID")

    return record
