"""Conference popularity & content extraction using keyless APIs.

Pulls MAXIMUM data from multiple sources for dashboard richness:
- Hacker News: stories, comments, discussions, links
- GitHub: repos, stars, topics, descriptions, README snippets
- Reddit: posts, subreddits, comments, upvotes
- DEV.to: articles, tags, reactions
- DuckDuckGo: web results, news

All APIs are keyless - no authentication required.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
from rich.console import Console

console = Console()

RATE_LIMIT_DELAY = 0.3


@dataclass
class HNStory:
    """Hacker News story/discussion."""
    title: str
    url: str
    hn_url: str
    points: int
    comments: int
    author: str
    created_at: str
    top_comments: list[str] = field(default_factory=list)


@dataclass
class GitHubRepo:
    """GitHub repository related to conference."""
    name: str
    full_name: str
    url: str
    description: Optional[str]
    stars: int
    forks: int
    language: Optional[str]
    topics: list[str] = field(default_factory=list)
    updated_at: Optional[str] = None


@dataclass
class RedditPost:
    """Reddit post/discussion."""
    title: str
    url: str
    subreddit: str
    score: int
    comments: int
    author: str
    created_utc: float
    selftext_preview: Optional[str] = None
    flair: Optional[str] = None


@dataclass
class DevToArticle:
    """DEV.to article."""
    title: str
    url: str
    author: str
    published_at: str
    tags: list[str]
    reactions: int
    comments: int
    reading_time: int
    description: Optional[str] = None


@dataclass
class WebResult:
    """Generic web search result."""
    title: str
    url: str
    snippet: str
    source: str  # "ddg", "news", etc.


@dataclass
class ConferenceIntel:
    """Full intelligence gathered about a conference."""
    name: str
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Hacker News
    hn_stories: list[HNStory] = field(default_factory=list)
    hn_total_stories: int = 0
    hn_total_points: int = 0
    hn_total_comments: int = 0
    hn_top_topics: list[str] = field(default_factory=list)

    # GitHub
    github_repos: list[GitHubRepo] = field(default_factory=list)
    github_total_repos: int = 0
    github_total_stars: int = 0
    github_languages: list[str] = field(default_factory=list)
    github_topics: list[str] = field(default_factory=list)

    # Reddit
    reddit_posts: list[RedditPost] = field(default_factory=list)
    reddit_total_posts: int = 0
    reddit_subreddits: list[str] = field(default_factory=list)
    reddit_top_flairs: list[str] = field(default_factory=list)

    # DEV.to
    devto_articles: list[DevToArticle] = field(default_factory=list)
    devto_total_articles: int = 0
    devto_tags: list[str] = field(default_factory=list)
    devto_top_authors: list[str] = field(default_factory=list)

    # Web/News
    web_results: list[WebResult] = field(default_factory=list)
    news_results: list[WebResult] = field(default_factory=list)

    # Aggregated
    all_topics: list[str] = field(default_factory=list)
    all_related_urls: list[str] = field(default_factory=list)
    popularity_score: float = 0.0

    # Errors
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict for JSON/Algolia."""
        return {
            "name": self.name,
            "fetched_at": self.fetched_at,
            "hn": {
                "stories": [s.__dict__ for s in self.hn_stories[:10]],
                "total_stories": self.hn_total_stories,
                "total_points": self.hn_total_points,
                "total_comments": self.hn_total_comments,
                "top_topics": self.hn_top_topics,
            },
            "github": {
                "repos": [r.__dict__ for r in self.github_repos[:10]],
                "total_repos": self.github_total_repos,
                "total_stars": self.github_total_stars,
                "languages": self.github_languages,
                "topics": self.github_topics,
            },
            "reddit": {
                "posts": [p.__dict__ for p in self.reddit_posts[:10]],
                "total_posts": self.reddit_total_posts,
                "subreddits": self.reddit_subreddits,
                "top_flairs": self.reddit_top_flairs,
            },
            "devto": {
                "articles": [a.__dict__ for a in self.devto_articles[:10]],
                "total_articles": self.devto_total_articles,
                "tags": self.devto_tags,
                "top_authors": self.devto_top_authors,
            },
            "web_results": [w.__dict__ for w in self.web_results[:10]],
            "news_results": [n.__dict__ for n in self.news_results[:10]],
            "all_topics": self.all_topics[:30],
            "all_related_urls": self.all_related_urls[:50],
            "popularity_score": self.popularity_score,
        }


def _clean_name(name: str) -> str:
    """Clean conference name for search."""
    # Remove year
    name = re.sub(r'\s*20\d{2}\s*', ' ', name)
    # Remove common suffixes
    name = re.sub(r'\s*-\s*CFP.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(.*\)$', '', name)
    return name.strip()


async def fetch_hn_intel(client: httpx.AsyncClient, name: str) -> dict:
    """Fetch comprehensive Hacker News data."""
    clean = _clean_name(name)
    result = {
        "stories": [],
        "total_stories": 0,
        "total_points": 0,
        "total_comments": 0,
        "top_topics": [],
    }

    try:
        # Search stories
        r = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": clean,
                "tags": "story",
                "hitsPerPage": 50,
                "attributesToRetrieve": "title,url,points,num_comments,author,created_at,objectID",
            }
        )
        r.raise_for_status()
        data = r.json()

        result["total_stories"] = data.get("nbHits", 0)

        # Extract topics from titles
        topic_words = []

        for hit in data.get("hits", []):
            story = HNStory(
                title=hit.get("title", ""),
                url=hit.get("url", ""),
                hn_url=f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                points=hit.get("points", 0) or 0,
                comments=hit.get("num_comments", 0) or 0,
                author=hit.get("author", ""),
                created_at=hit.get("created_at", ""),
            )
            result["stories"].append(story)
            result["total_points"] += story.points
            result["total_comments"] += story.comments

            # Extract topic words
            words = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', story.title)
            topic_words.extend(words)

        # Get top comments for top 3 stories
        for story in result["stories"][:3]:
            try:
                story_id = story.hn_url.split("id=")[-1]
                cr = await client.get(
                    f"https://hn.algolia.com/api/v1/search",
                    params={
                        "tags": f"comment,story_{story_id}",
                        "hitsPerPage": 5,
                    }
                )
                if cr.status_code == 200:
                    comments = cr.json().get("hits", [])
                    story.top_comments = [
                        c.get("comment_text", "")[:200]
                        for c in comments if c.get("comment_text")
                    ][:3]
            except:
                pass

        # Count topic frequencies
        from collections import Counter
        topic_counts = Counter(topic_words)
        result["top_topics"] = [t for t, _ in topic_counts.most_common(10)]

    except Exception as e:
        result["error"] = str(e)

    return result


async def fetch_github_intel(client: httpx.AsyncClient, name: str) -> dict:
    """Fetch comprehensive GitHub data."""
    clean = _clean_name(name)
    result = {
        "repos": [],
        "total_repos": 0,
        "total_stars": 0,
        "languages": [],
        "topics": [],
    }

    try:
        r = await client.get(
            "https://api.github.com/search/repositories",
            params={"q": clean, "per_page": 30, "sort": "stars"},
            headers={"Accept": "application/vnd.github.v3+json"}
        )

        if r.status_code == 403:
            result["error"] = "Rate limited"
            return result

        r.raise_for_status()
        data = r.json()

        result["total_repos"] = data.get("total_count", 0)

        languages = []
        all_topics = []

        for item in data.get("items", []):
            repo = GitHubRepo(
                name=item.get("name", ""),
                full_name=item.get("full_name", ""),
                url=item.get("html_url", ""),
                description=item.get("description"),
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                language=item.get("language"),
                topics=item.get("topics", []),
                updated_at=item.get("updated_at"),
            )
            result["repos"].append(repo)
            result["total_stars"] += repo.stars

            if repo.language:
                languages.append(repo.language)
            all_topics.extend(repo.topics)

        # Dedupe and count
        from collections import Counter
        result["languages"] = [l for l, _ in Counter(languages).most_common(10)]
        result["topics"] = [t for t, _ in Counter(all_topics).most_common(20)]

    except Exception as e:
        result["error"] = str(e)

    return result


async def fetch_reddit_intel(client: httpx.AsyncClient, name: str) -> dict:
    """Fetch comprehensive Reddit data."""
    clean = _clean_name(name)
    result = {
        "posts": [],
        "total_posts": 0,
        "subreddits": [],
        "top_flairs": [],
    }

    try:
        r = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": clean, "limit": 100, "sort": "relevance", "t": "all"},
            headers={"User-Agent": "CFPPlease/1.0 (conference discovery tool)"}
        )

        if r.status_code != 200:
            result["error"] = f"Status {r.status_code}"
            return result

        data = r.json()
        children = data.get("data", {}).get("children", [])

        result["total_posts"] = len(children)

        subreddits = []
        flairs = []

        for child in children:
            post_data = child.get("data", {})
            post = RedditPost(
                title=post_data.get("title", ""),
                url=f"https://reddit.com{post_data.get('permalink', '')}",
                subreddit=post_data.get("subreddit", ""),
                score=post_data.get("score", 0),
                comments=post_data.get("num_comments", 0),
                author=post_data.get("author", ""),
                created_utc=post_data.get("created_utc", 0),
                selftext_preview=(post_data.get("selftext") or "")[:200],
                flair=post_data.get("link_flair_text"),
            )
            result["posts"].append(post)
            subreddits.append(post.subreddit)
            if post.flair:
                flairs.append(post.flair)

        from collections import Counter
        result["subreddits"] = [s for s, _ in Counter(subreddits).most_common(10)]
        result["top_flairs"] = [f for f, _ in Counter(flairs).most_common(10)]

    except Exception as e:
        result["error"] = str(e)

    return result


async def fetch_devto_intel(client: httpx.AsyncClient, name: str) -> dict:
    """Fetch comprehensive DEV.to data."""
    clean = _clean_name(name)
    # Create tag from name (lowercase, no spaces)
    tag = re.sub(r'[^a-z0-9]', '', clean.lower())

    result = {
        "articles": [],
        "total_articles": 0,
        "tags": [],
        "top_authors": [],
    }

    try:
        # Try tag-based search first
        r = await client.get(
            "https://dev.to/api/articles",
            params={"tag": tag, "per_page": 50}
        )

        articles = []
        if r.status_code == 200:
            articles = r.json()

        # Also try text search
        r2 = await client.get(
            "https://dev.to/api/articles",
            params={"per_page": 50},
            headers={"User-Agent": "CFPPlease/1.0"}
        )
        # DEV.to doesn't have great text search, so we filter client-side
        if r2.status_code == 200:
            all_articles = r2.json()
            name_lower = clean.lower()
            for a in all_articles:
                title = (a.get("title") or "").lower()
                desc = (a.get("description") or "").lower()
                if name_lower in title or name_lower in desc:
                    if a not in articles:
                        articles.append(a)

        result["total_articles"] = len(articles)

        all_tags = []
        authors = []

        for a in articles:
            article = DevToArticle(
                title=a.get("title", ""),
                url=a.get("url", ""),
                author=a.get("user", {}).get("username", ""),
                published_at=a.get("published_at", ""),
                tags=a.get("tag_list", []),
                reactions=a.get("positive_reactions_count", 0),
                comments=a.get("comments_count", 0),
                reading_time=a.get("reading_time_minutes", 0),
                description=a.get("description"),
            )
            result["articles"].append(article)
            all_tags.extend(article.tags)
            authors.append(article.author)

        from collections import Counter
        result["tags"] = [t for t, _ in Counter(all_tags).most_common(15)]
        result["top_authors"] = [a for a, _ in Counter(authors).most_common(10)]

    except Exception as e:
        result["error"] = str(e)

    return result


async def fetch_ddg_intel(name: str) -> dict:
    """Fetch DuckDuckGo web and news results."""
    clean = _clean_name(name)
    result = {
        "web_results": [],
        "news_results": [],
    }

    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            # Web results
            web = list(ddgs.text(f'"{clean}" conference', max_results=20))
            for w in web:
                result["web_results"].append(WebResult(
                    title=w.get("title", ""),
                    url=w.get("href", ""),
                    snippet=w.get("body", ""),
                    source="ddg_web",
                ))

            # News results
            try:
                news = list(ddgs.news(f'"{clean}" conference', max_results=10))
                for n in news:
                    result["news_results"].append(WebResult(
                        title=n.get("title", ""),
                        url=n.get("url", ""),
                        snippet=n.get("body", ""),
                        source="ddg_news",
                    ))
            except:
                pass  # News search might not be available

    except Exception as e:
        result["error"] = str(e)

    return result


async def gather_conference_intel(
    name: str,
    include_ddg: bool = True,
) -> ConferenceIntel:
    """Gather all available intelligence about a conference.

    Args:
        name: Conference name
        include_ddg: Include DuckDuckGo search (slower)

    Returns:
        ConferenceIntel with all gathered data
    """
    intel = ConferenceIntel(name=name)

    async with httpx.AsyncClient(timeout=20) as client:
        # Fetch all sources in parallel
        tasks = {
            "hn": fetch_hn_intel(client, name),
            "github": fetch_github_intel(client, name),
            "reddit": fetch_reddit_intel(client, name),
            "devto": fetch_devto_intel(client, name),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for source, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                intel.errors.append(f"{source}: {result}")
                continue

            if "error" in result:
                intel.errors.append(f"{source}: {result['error']}")

            # Map results to intel object
            if source == "hn":
                intel.hn_stories = result.get("stories", [])
                intel.hn_total_stories = result.get("total_stories", 0)
                intel.hn_total_points = result.get("total_points", 0)
                intel.hn_total_comments = result.get("total_comments", 0)
                intel.hn_top_topics = result.get("top_topics", [])

            elif source == "github":
                intel.github_repos = result.get("repos", [])
                intel.github_total_repos = result.get("total_repos", 0)
                intel.github_total_stars = result.get("total_stars", 0)
                intel.github_languages = result.get("languages", [])
                intel.github_topics = result.get("topics", [])

            elif source == "reddit":
                intel.reddit_posts = result.get("posts", [])
                intel.reddit_total_posts = result.get("total_posts", 0)
                intel.reddit_subreddits = result.get("subreddits", [])
                intel.reddit_top_flairs = result.get("top_flairs", [])

            elif source == "devto":
                intel.devto_articles = result.get("articles", [])
                intel.devto_total_articles = result.get("total_articles", 0)
                intel.devto_tags = result.get("tags", [])
                intel.devto_top_authors = result.get("top_authors", [])

    # DDG is sync, run separately
    if include_ddg:
        ddg_result = await fetch_ddg_intel(name)
        if "error" not in ddg_result:
            intel.web_results = ddg_result.get("web_results", [])
            intel.news_results = ddg_result.get("news_results", [])
        else:
            intel.errors.append(f"ddg: {ddg_result['error']}")

    # Aggregate all topics
    all_topics = set()
    all_topics.update(intel.hn_top_topics)
    all_topics.update(intel.github_topics)
    all_topics.update(intel.github_languages)
    all_topics.update(intel.devto_tags)
    all_topics.update(intel.reddit_subreddits)
    intel.all_topics = list(all_topics)[:30]

    # Collect all related URLs
    urls = set()
    for s in intel.hn_stories:
        if s.url:
            urls.add(s.url)
        urls.add(s.hn_url)
    for r in intel.github_repos:
        urls.add(r.url)
    for p in intel.reddit_posts:
        urls.add(p.url)
    for a in intel.devto_articles:
        urls.add(a.url)
    for w in intel.web_results + intel.news_results:
        urls.add(w.url)
    intel.all_related_urls = list(urls)[:50]

    # Compute popularity score
    import math
    raw = (
        intel.hn_total_stories * 5 +
        intel.hn_total_points * 0.01 +
        intel.github_total_repos * 2 +
        intel.github_total_stars * 0.01 +
        intel.reddit_total_posts * 1 +
        intel.devto_total_articles * 3 +
        len(intel.web_results) * 0.5
    )
    intel.popularity_score = min(100, math.log1p(raw) * 10)

    return intel


async def gather_intel_batch(
    names: list[str],
    max_concurrent: int = 2,
    include_ddg: bool = False,  # DDG is slow, skip by default for batches
) -> dict[str, ConferenceIntel]:
    """Gather intelligence for multiple conferences.

    Args:
        names: List of conference names
        max_concurrent: Max concurrent fetches
        include_ddg: Include DuckDuckGo (slower)

    Returns:
        Dict mapping name to ConferenceIntel
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, ConferenceIntel] = {}

    async def fetch_one(name: str) -> tuple[str, ConferenceIntel]:
        async with semaphore:
            await asyncio.sleep(RATE_LIMIT_DELAY)
            intel = await gather_conference_intel(name, include_ddg=include_ddg)
            console.print(
                f"[dim]  {name}: score={intel.popularity_score:.1f}, "
                f"hn={intel.hn_total_stories}, gh={intel.github_total_repos}, "
                f"reddit={intel.reddit_total_posts}[/dim]"
            )
            return name, intel

    tasks = [fetch_one(name) for name in names]

    for coro in asyncio.as_completed(tasks):
        name, intel = await coro
        results[name] = intel

    return results


# CLI test
if __name__ == "__main__":
    import json
    import sys

    async def main():
        name = sys.argv[1] if len(sys.argv) > 1 else "KubeCon"
        print(f"\n🔍 Gathering intelligence for: {name}\n")

        intel = await gather_conference_intel(name, include_ddg=True)

        print(f"📊 Results:")
        print(f"  Hacker News: {intel.hn_total_stories} stories, {intel.hn_total_points} points")
        print(f"  GitHub: {intel.github_total_repos} repos, {intel.github_total_stars} stars")
        print(f"  Reddit: {intel.reddit_total_posts} posts in r/{', r/'.join(intel.reddit_subreddits[:3])}")
        print(f"  DEV.to: {intel.devto_total_articles} articles")
        print(f"  Web: {len(intel.web_results)} results, {len(intel.news_results)} news")

        print(f"\n📚 Topics: {', '.join(intel.all_topics[:15])}")
        print(f"🔗 Related URLs: {len(intel.all_related_urls)}")
        print(f"\n⭐ Popularity Score: {intel.popularity_score:.1f}/100")

        if intel.errors:
            print(f"\n⚠️  Errors: {intel.errors}")

        # Show sample data
        if intel.hn_stories:
            print(f"\n📰 Top HN Story: {intel.hn_stories[0].title}")
            print(f"   {intel.hn_stories[0].hn_url}")

        if intel.github_repos:
            print(f"\n💻 Top Repo: {intel.github_repos[0].full_name} ({intel.github_repos[0].stars}⭐)")
            print(f"   {intel.github_repos[0].description}")

    asyncio.run(main())
