"""Enrichment schema - structured data extracted by LLM."""

from typing import Optional
from pydantic import BaseModel, Field


class ExampleTalk(BaseModel):
    """A notable talk from this conference found on YouTube."""
    title: str
    speaker: Optional[str] = None
    description: Optional[str] = Field(
        default=None,
        description="Talk description/abstract (truncated)"
    )
    url: str
    thumbnail_url: Optional[str] = None
    year: Optional[int] = None
    duration_seconds: Optional[int] = None
    view_count: Optional[int] = None
    channel: Optional[str] = None


class LocationContext(BaseModel):
    """Tech scene context for a city/country."""
    city: Optional[str] = None
    country: Optional[str] = None
    tech_scene_description: Optional[str] = Field(
        default=None,
        description="Description of the local tech scene, major companies, community"
    )
    notable_companies: list[str] = Field(
        default_factory=list,
        description="Major tech companies headquartered or with offices here"
    )
    tech_hubs: list[str] = Field(
        default_factory=list,
        description="Nearby tech hubs, coworking spaces, university partnerships"
    )


class EnrichedData(BaseModel):
    """Rich metadata extracted from conference pages via LLM."""

    # ===== CORE DESCRIPTIONS (long, searchable) =====

    # Short description (1-2 sentences, for cards)
    description: Optional[str] = Field(
        default=None,
        description="1-2 sentence description of the conference"
    )

    # Rich description (3-5 paragraphs, for detail pages and search)
    rich_description: Optional[str] = Field(
        default=None,
        description="Comprehensive description covering history, focus areas, notable speakers, community impact"
    )

    # Audience description (who should attend)
    audience_description: Optional[str] = Field(
        default=None,
        description="Detailed description of who should attend, what they'll learn, career benefits"
    )

    # ===== SEARCHABLE KEYWORDS =====

    # Keywords for full-text search (extracted + generated)
    keywords: list[str] = Field(
        default_factory=list,
        description="Searchable keywords: technologies, concepts, buzzwords, related terms"
    )

    # ===== TAXONOMY FIELDS =====

    # Topic taxonomy (from our fixed list)
    topics: list[str] = Field(
        default_factory=list,
        description="Primary topic categories from taxonomy"
    )

    # Programming languages focus
    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages relevant to this conference"
    )

    # Specific technologies/frameworks mentioned
    technologies: list[str] = Field(
        default_factory=list,
        description="Specific frameworks/tools: React, Kubernetes, TensorFlow, etc."
    )

    # ===== AUDIENCE & FORMAT =====

    # Audience level
    audience_level: Optional[str] = Field(
        default=None,
        description="Target audience: beginner, intermediate, advanced, all-levels"
    )

    # Conference format
    format: Optional[str] = Field(
        default=None,
        description="Conference format: in-person, virtual, hybrid"
    )

    # Talk types accepted
    talk_types: list[str] = Field(
        default_factory=list,
        description="Types of talks accepted: talk, workshop, lightning, keynote, panel"
    )

    # Industry/domain focus
    industries: list[str] = Field(
        default_factory=list,
        description="Industry verticals: fintech, healthcare, gaming, enterprise, startup"
    )

    # ===== LOCATION CONTEXT =====

    location_context: Optional[LocationContext] = Field(
        default=None,
        description="Tech scene context for the conference location"
    )

    # ===== EXAMPLE TALKS =====

    example_talks: list[ExampleTalk] = Field(
        default_factory=list,
        description="Notable talks from previous editions found on YouTube"
    )


# Controlled vocabularies for the LLM prompt

TOPIC_TAXONOMY = [
    "frontend", "backend", "fullstack", "mobile",
    "devops", "cloud", "ai-ml", "data",
    "security", "design", "architecture", "languages",
    "testing", "agile", "leadership", "career",
    "open-source", "gaming", "iot", "blockchain",
]

LANGUAGE_OPTIONS = [
    "javascript", "typescript", "python", "java", "go", "rust",
    "c#", "c++", "ruby", "php", "swift", "kotlin", "scala",
    "elixir", "haskell", "clojure", "sql", "r", "julia",
]

AUDIENCE_LEVELS = ["beginner", "intermediate", "advanced", "all-levels"]

FORMAT_OPTIONS = ["in-person", "virtual", "hybrid"]

TALK_TYPES = ["talk", "workshop", "lightning", "keynote", "panel", "tutorial"]

INDUSTRY_OPTIONS = [
    "fintech", "healthcare", "gaming", "enterprise", "startup",
    "ecommerce", "media", "education", "government", "nonprofit",
]


def build_enrichment_prompt(name: str, content: str) -> str:
    """Build the LLM prompt for enrichment."""
    return f"""You are extracting structured conference metadata from a webpage.

Conference name: {name}
Webpage content (truncated): {content[:3000]}

Extract information and respond with ONLY valid JSON (no markdown, no backticks, no explanation):

{{
  "description": "1-2 sentence description of the conference focus and target audience",
  "topics": ["topic1", "topic2"],
  "languages": ["lang1", "lang2"],
  "audience_level": "level",
  "format": "format",
  "talk_types": ["type1"],
  "industries": ["industry1"],
  "technologies": ["tech1", "tech2"]
}}

CONSTRAINTS - use ONLY these values:

topics (pick 2-4): {', '.join(TOPIC_TAXONOMY)}
languages (if mentioned): {', '.join(LANGUAGE_OPTIONS)}
audience_level (pick 1): {', '.join(AUDIENCE_LEVELS)}
format (pick 1): {', '.join(FORMAT_OPTIONS)}
talk_types (pick relevant): {', '.join(TALK_TYPES)}
industries (if specific): {', '.join(INDUSTRY_OPTIONS)}
technologies: any specific frameworks/tools mentioned (React, Kubernetes, etc.)

If information is not available, use empty arrays [] or null. Be concise."""
