"""Intel Indexer - Store raw intel data in separate indexes.

Splits large intel data across multiple indexes to avoid Algolia's 100KB limit:
- cfps_intel_hn: Full Hacker News data
- cfps_intel_github: Full GitHub data
- cfps_intel_reddit: Full Reddit data
- cfps_intel_devto: Full DEV.to data

Main cfps index gets only compact summaries + scores.
"""

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from dataclasses import asdict, is_dataclass
from algoliasearch.search.client import SearchClientSync
from rich.console import Console

console = Console()


def _to_dict(obj):
    """Convert dataclass to dict, or return dict as-is."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj if isinstance(obj, dict) else {}


def _get_attr(obj, key, default=None):
    """Get attribute from dict or dataclass."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

# Index names
INTEL_INDEX_HN = "cfps_intel_hn"
INTEL_INDEX_GITHUB = "cfps_intel_github"
INTEL_INDEX_REDDIT = "cfps_intel_reddit"
INTEL_INDEX_DEVTO = "cfps_intel_devto"


def get_client() -> SearchClientSync:
    """Get Algolia client."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")
    if not app_id or not api_key:
        raise ValueError("ALGOLIA_APP_ID and ALGOLIA_API_KEY required")
    return SearchClientSync(app_id, api_key)


def configure_intel_indexes(client: SearchClientSync):
    """Configure all intel indexes with proper settings."""

    # Common settings for intel indexes
    base_settings = {
        "searchableAttributes": ["cfpName", "objectID"],
        "attributesForFaceting": ["cfpName", "filterOnly(objectID)"],
        "ranking": ["desc(fetchedAt)", "typo", "geo", "words", "filters", "proximity", "attribute", "exact", "custom"],
    }

    # HN index
    hn_settings = {
        **base_settings,
        "searchableAttributes": ["cfpName", "storyTitles", "topComments", "commentAuthors"],
        "attributesForFaceting": ["cfpName", "filterOnly(objectID)", "commentAuthors"],
    }
    client.set_settings(INTEL_INDEX_HN, hn_settings)
    console.print(f"[green]Configured {INTEL_INDEX_HN}[/green]")

    # GitHub index
    github_settings = {
        **base_settings,
        "searchableAttributes": ["cfpName", "repoNames", "descriptions", "languages", "topics"],
        "attributesForFaceting": ["cfpName", "filterOnly(objectID)", "languages", "topics"],
    }
    client.set_settings(INTEL_INDEX_GITHUB, github_settings)
    console.print(f"[green]Configured {INTEL_INDEX_GITHUB}[/green]")

    # Reddit index
    reddit_settings = {
        **base_settings,
        "searchableAttributes": ["cfpName", "postTitles", "subreddits", "comments"],
        "attributesForFaceting": ["cfpName", "filterOnly(objectID)", "subreddits"],
    }
    client.set_settings(INTEL_INDEX_REDDIT, reddit_settings)
    console.print(f"[green]Configured {INTEL_INDEX_REDDIT}[/green]")

    # DEV.to index
    devto_settings = {
        **base_settings,
        "searchableAttributes": ["cfpName", "articleTitles", "tags", "authors"],
        "attributesForFaceting": ["cfpName", "filterOnly(objectID)", "tags"],
    }
    client.set_settings(INTEL_INDEX_DEVTO, devto_settings)
    console.print(f"[green]Configured {INTEL_INDEX_DEVTO}[/green]")


def index_hn_intel(client: SearchClientSync, cfp_id: str, cfp_name: str, intel: dict) -> bool:
    """Index HN intel data to separate index."""
    if not intel.get("stories") and not intel.get("total_stories"):
        return False

    # Convert dataclass objects to dicts for Algolia serialization
    stories_raw = intel.get("stories", [])[:50]
    stories = [_to_dict(s) for s in stories_raw]

    record = {
        "objectID": cfp_id,
        "cfpName": cfp_name,
        "fetchedAt": datetime.utcnow().isoformat(),

        # Full story data
        "stories": stories,
        "totalStories": intel.get("total_stories", 0),
        "totalPoints": intel.get("total_points", 0),

        # Searchable extracts
        "storyTitles": intel.get("story_titles", [])[:30],
        "topComments": intel.get("top_comments", [])[:50],
        "commentAuthors": intel.get("comment_authors", [])[:20],

        # URLs for reference
        "storyUrls": [_get_attr(s, "hn_url") for s in stories_raw[:20] if _get_attr(s, "hn_url")],
    }

    try:
        client.save_object(INTEL_INDEX_HN, record)
        return True
    except Exception as e:
        console.print(f"[red]Error indexing HN intel for {cfp_name}: {e}[/red]")
        return False


def index_github_intel(client: SearchClientSync, cfp_id: str, cfp_name: str, intel: dict) -> bool:
    """Index GitHub intel data to separate index."""
    if not intel.get("repos") and not intel.get("total_repos"):
        return False

    # Convert dataclass objects to dicts for Algolia serialization
    repos_raw = intel.get("repos", [])[:30]
    repos = [_to_dict(r) for r in repos_raw]

    record = {
        "objectID": cfp_id,
        "cfpName": cfp_name,
        "fetchedAt": datetime.utcnow().isoformat(),

        # Full repo data
        "repos": repos,
        "totalRepos": intel.get("total_repos", 0),
        "totalStars": intel.get("total_stars", 0),

        # Searchable extracts
        "repoNames": [_get_attr(r, "name") for r in repos_raw if _get_attr(r, "name")],
        "descriptions": [_get_attr(r, "description") for r in repos_raw if _get_attr(r, "description")],
        "languages": intel.get("languages", []),
        "topics": intel.get("topics", []),

        # URLs
        "repoUrls": [_get_attr(r, "url") for r in repos_raw if _get_attr(r, "url")],
    }

    try:
        client.save_object(INTEL_INDEX_GITHUB, record)
        return True
    except Exception as e:
        console.print(f"[red]Error indexing GitHub intel for {cfp_name}: {e}[/red]")
        return False


def index_reddit_intel(client: SearchClientSync, cfp_id: str, cfp_name: str, intel: dict) -> bool:
    """Index Reddit intel data to separate index."""
    if not intel.get("posts") and not intel.get("total_posts"):
        return False

    # Convert dataclass objects to dicts for Algolia serialization
    posts_raw = intel.get("posts", [])[:30]
    posts = [_to_dict(p) for p in posts_raw]

    record = {
        "objectID": cfp_id,
        "cfpName": cfp_name,
        "fetchedAt": datetime.utcnow().isoformat(),

        # Full post data
        "posts": posts,
        "totalPosts": intel.get("total_posts", 0),

        # Searchable extracts
        "postTitles": [_get_attr(p, "title") for p in posts_raw if _get_attr(p, "title")],
        "subreddits": intel.get("subreddits", []),
        "comments": intel.get("all_comments", [])[:30],
        "flairs": intel.get("top_flairs", []),

        # URLs
        "postUrls": [_get_attr(p, "url") for p in posts_raw if _get_attr(p, "url")],
    }

    try:
        client.save_object(INTEL_INDEX_REDDIT, record)
        return True
    except Exception as e:
        console.print(f"[red]Error indexing Reddit intel for {cfp_name}: {e}[/red]")
        return False


def index_devto_intel(client: SearchClientSync, cfp_id: str, cfp_name: str, intel: dict) -> bool:
    """Index DEV.to intel data to separate index."""
    if not intel.get("articles") and not intel.get("total_articles"):
        return False

    # Convert dataclass objects to dicts for Algolia serialization
    articles_raw = intel.get("articles", [])[:30]
    articles = [_to_dict(a) for a in articles_raw]

    record = {
        "objectID": cfp_id,
        "cfpName": cfp_name,
        "fetchedAt": datetime.utcnow().isoformat(),

        # Full article data
        "articles": articles,
        "totalArticles": intel.get("total_articles", 0),

        # Searchable extracts
        "articleTitles": [_get_attr(a, "title") for a in articles_raw if _get_attr(a, "title")],
        "tags": intel.get("tags", []),
        "authors": [_get_attr(a, "author") for a in articles_raw if _get_attr(a, "author")],

        # URLs
        "articleUrls": [_get_attr(a, "url") for a in articles_raw if _get_attr(a, "url")],
    }

    try:
        client.save_object(INTEL_INDEX_DEVTO, record)
        return True
    except Exception as e:
        console.print(f"[red]Error indexing DEV.to intel for {cfp_name}: {e}[/red]")
        return False


def get_intel_stats(client: SearchClientSync) -> dict:
    """Get stats for all intel indexes."""
    stats = {}

    for index_name in [INTEL_INDEX_HN, INTEL_INDEX_GITHUB, INTEL_INDEX_REDDIT, INTEL_INDEX_DEVTO]:
        try:
            settings = client.get_settings(index_name)
            # Try to get record count via search
            result = client.search_single_index(index_name, {"query": "", "hitsPerPage": 0})
            stats[index_name] = {
                "records": getattr(result, "nb_hits", 0),
            }
        except Exception:
            stats[index_name] = {"records": 0, "error": "Index not found"}

    return stats
