"""Speaker model for conference speakers.

Aggregated from talks index, stored in separate Algolia index.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, computed_field


def slugify_name(name: str) -> str:
    """Convert speaker name to URL-friendly slug."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


class Speaker(BaseModel):
    """A conference speaker profile aggregated from talks."""

    # ===== IDENTITY =====
    objectID: str = Field(description="Slugified name: 'paul-louis-nech'")
    name: str = Field(description="Display name")
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative name forms: ['PLN', 'Paul-Louis NECH']"
    )
    company: Optional[str] = Field(
        default=None,
        description="Current company/affiliation"
    )
    is_algolia_speaker: bool = Field(
        default=False,
        description="True if speaker is/was an Algolia employee (for UI boost)"
    )

    # ===== AGGREGATED STATS =====
    talk_count: int = Field(default=0, description="Total talks in index")
    total_views: int = Field(default=0, description="Sum of all talk views")
    max_views: int = Field(default=0, description="Highest view count single talk")

    # ===== ACTIVITY TIMELINE =====
    years_active: list[int] = Field(
        default_factory=list,
        description="Years with talks: [2017, 2018, ..., 2025]"
    )
    first_talk_year: Optional[int] = Field(
        default=None,
        description="First year with a talk"
    )
    latest_talk_year: Optional[int] = Field(
        default=None,
        description="Most recent year with a talk"
    )

    # ===== TOPICS (aggregated) =====
    topics: list[str] = Field(
        default_factory=list,
        description="Top topics across all talks"
    )
    topic_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count per topic: {'AI': 5, 'Search': 8}"
    )

    # ===== CONFERENCES =====
    conferences: list[str] = Field(
        default_factory=list,
        description="Conference names spoken at"
    )
    conference_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Talks per conference: {'DevCon': 6, 'MICES': 3}"
    )

    # ===== TALK REFERENCES (FK) =====
    top_talk_ids: list[str] = Field(
        default_factory=list,
        description="Top 5 talks by views (objectIDs)"
    )
    all_talk_ids: list[str] = Field(
        default_factory=list,
        description="All talk objectIDs for this speaker"
    )

    # ===== EXTERNAL LINKS (optional) =====
    profile_url: Optional[str] = Field(
        default=None,
        description="Personal website or speaker page"
    )
    twitter: Optional[str] = Field(default=None, description="Twitter handle")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn URL")
    github: Optional[str] = Field(default=None, description="GitHub username")

    # ===== IMAGE & BIO (from Sessionize) =====
    image_url: Optional[str] = Field(
        default=None,
        description="Profile photo URL (from Sessionize)"
    )
    tagline: Optional[str] = Field(
        default=None,
        description="Short bio/tagline"
    )
    location: Optional[str] = Field(
        default=None,
        description="Speaker location (city, country)"
    )
    sessionize_slug: Optional[str] = Field(
        default=None,
        description="Sessionize profile slug for linking"
    )

    # ===== ACHIEVEMENTS (computed) =====
    achievements: list[str] = Field(
        default_factory=list,
        description="Achievement badges: ['100K Club', 'Veteran']"
    )

    # ===== COMPUTED FIELDS =====

    @computed_field
    @property
    def active_years(self) -> int:
        """Number of distinct years with talks."""
        return len(self.years_active)

    @computed_field
    @property
    def conference_count(self) -> int:
        """Number of distinct conferences."""
        return len(self.conferences)

    @computed_field
    @property
    def avg_views(self) -> float:
        """Average views per talk."""
        if self.talk_count == 0:
            return 0.0
        return self.total_views / self.talk_count

    @computed_field
    @property
    def influence_score(self) -> float:
        """Influence = total views / years active. Higher = more impactful."""
        if self.active_years == 0:
            return 0.0
        return self.total_views / self.active_years

    @computed_field
    @property
    def consistency_score(self) -> float:
        """Consistency = talks / years active. Higher = more consistent."""
        if self.active_years == 0:
            return 0.0
        return self.talk_count / self.active_years

    def compute_achievements(self) -> list[str]:
        """Compute achievement badges based on stats."""
        achievements = []
        from datetime import datetime
        current_year = datetime.now().year

        # ===== VIEW-BASED =====
        if self.total_views >= 1_000_000:
            achievements.append("Million Club")
        elif self.total_views >= 100_000:
            achievements.append("100K Club")
        elif self.total_views >= 10_000:
            achievements.append("10K Club")

        if self.max_views >= 100_000:
            achievements.append("Viral Sensation")
        elif self.max_views >= 50_000:
            achievements.append("Viral Hit")

        # ===== ACTIVITY-BASED =====
        if self.talk_count >= 50:
            achievements.append("Legend")
        elif self.talk_count >= 20:
            achievements.append("Prolific")
        elif self.talk_count >= 10:
            achievements.append("Frequent Flyer")

        if self.active_years >= 10:
            achievements.append("Decade Veteran")
        elif self.active_years >= 5:
            achievements.append("Veteran")
        elif self.active_years >= 3:
            achievements.append("Established")

        # Rising star: first talk in last 2 years AND growing
        if self.first_talk_year and self.first_talk_year >= current_year - 2:
            if self.talk_count >= 3:
                achievements.append("Rising Star")

        # ===== CONFERENCE DIVERSITY =====
        if self.conference_count >= 10:
            achievements.append("Globe Trotter")
        elif self.conference_count >= 5:
            achievements.append("Multi-Conference")

        # ===== TOPIC EXPERTISE =====
        if len(self.topics) >= 5:
            achievements.append("Polymath")
        elif len(self.topics) >= 3:
            achievements.append("Multi-Domain")

        # Topic leader (top topic with 5+ talks)
        if self.topic_counts:
            top_topic = max(self.topic_counts.items(), key=lambda x: x[1])
            if top_topic[1] >= 5:
                achievements.append(f"Expert: {top_topic[0]}")

        # ===== CONSISTENCY =====
        if self.consistency_score >= 3.0:
            achievements.append("Consistent")  # 3+ talks per active year

        # ===== REGIONAL (based on conference names) =====
        conf_lower = " ".join(self.conferences).lower()
        continents_spoken = set()
        if any(x in conf_lower for x in ["pycon us", "kubecon na", "render", "strangeloop", "defcon"]):
            continents_spoken.add("NA")
        if any(x in conf_lower for x in ["europe", " eu", "berlin", "london", "paris", "devoxx", "fosdem"]):
            continents_spoken.add("EU")
        if any(x in conf_lower for x in ["asia", "tokyo", "singapore", "india", "china", "jsconf asia"]):
            continents_spoken.add("Asia")
        if any(x in conf_lower for x in ["australia", "sydney", "melbourne"]):
            continents_spoken.add("Oceania")
        if any(x in conf_lower for x in ["africa", "lagos", "cape town"]):
            continents_spoken.add("Africa")
        if any(x in conf_lower for x in ["latam", "brazil", "argentina", "jsconf ar"]):
            continents_spoken.add("LATAM")

        if len(continents_spoken) >= 3:
            achievements.append("World Traveler")
        elif len(continents_spoken) >= 2:
            achievements.append("International")

        # ===== EVENT SCALE (based on well-known conferences) =====
        large_conferences = ["kubecon", "reinvent", "google i/o", "wwdc", "microsoft build",
                           "aws summit", "defcon", "black hat", "pycon", "jsconf"]
        if any(lc in conf_lower for lc in large_conferences):
            achievements.append("Main Stage")

        return achievements

    def model_post_init(self, __context) -> None:
        """Compute derived fields after init."""
        # Compute achievements if not already set
        if not self.achievements:
            self.achievements = self.compute_achievements()


def speaker_to_algolia(speaker: Speaker) -> dict:
    """Convert Speaker to Algolia record."""
    record = speaker.model_dump(exclude_none=True)

    # Ensure required fields
    if 'objectID' not in record:
        raise ValueError("Speaker must have objectID")

    return record
