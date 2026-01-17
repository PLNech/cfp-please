"""LLM enrichment using Algolia Enablers API (MiniMax M2.1).

Robust implementation with:
- Async parallel processing (up to 8 concurrent LLM calls)
- Step-by-step extraction for complex tasks
- Retries with exponential backoff
- DuckDuckGo search fallback for unreachable URLs
- Name-based inference as last resort
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional, Any

import httpx
from duckduckgo_search import DDGS
from rich.console import Console

from cfp_pipeline.enrichers.schema import (
    EnrichedData,
    TOPIC_TAXONOMY,
    LANGUAGE_OPTIONS,
)

console = Console()

# Enablers API config
ENABLERS_URL = "https://inference.api.enablers.algolia.net/v1/chat/completions"
MODEL = "minimax-m2.1"

# Shared httpx client for connection pooling
_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create shared async HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


async def close_http_client():
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None

# Cache for enrichments
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
ENRICHMENT_CACHE_FILE = CACHE_DIR / "enrichments.json"


def get_enablers_token() -> str:
    """Get Enablers API token from environment."""
    token = os.environ.get("ENABLERS_JWT")
    if not token:
        raise ValueError("ENABLERS_JWT environment variable not set")
    return token


def load_enrichment_cache() -> dict[str, EnrichedData]:
    """Load cached enrichments."""
    if not ENRICHMENT_CACHE_FILE.exists():
        return {}
    try:
        with open(ENRICHMENT_CACHE_FILE) as f:
            data = json.load(f)
        return {k: EnrichedData.model_validate(v) for k, v in data.items()}
    except (json.JSONDecodeError, Exception):
        return {}


def save_enrichment_cache(cache: dict[str, EnrichedData]) -> None:
    """Save enrichments to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENRICHMENT_CACHE_FILE, "w") as f:
        json.dump({k: v.model_dump() for k, v in cache.items()}, f, indent=2)


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, stripping scripts/styles."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    return text


# Realistic Firefox user-agent
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)


async def fetch_page(url: str, max_retries: int = 3) -> Optional[str]:
    """Fetch HTML content from a URL with retries and exponential backoff."""
    if not url:
        return None

    client = await get_http_client()

    for attempt in range(max_retries):
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text

        except httpx.TimeoutException:
            console.print(f"[dim]Attempt {attempt+1}: Timeout fetching {url}[/dim]")
        except httpx.HTTPStatusError as e:
            console.print(f"[dim]Attempt {attempt+1}: HTTP {e.response.status_code} for {url}[/dim]")
            if e.response.status_code in (403, 404, 410):
                return None  # Don't retry these
        except Exception as e:
            console.print(f"[dim]Attempt {attempt+1}: Failed to fetch {url}: {e}[/dim]")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    return None


async def call_llm_with_retry(
    prompt: str,
    token: str,
    max_retries: int = 3,
) -> Optional[str]:
    """Call LLM with retries and exponential backoff. Returns raw content string."""
    client = await get_http_client()

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.3,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    for attempt in range(max_retries):
        try:
            response = await client.post(ENABLERS_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content")

            if content:
                return content.strip()

            # Check if still reasoning (content is null)
            reasoning = data.get("choices", [{}])[0].get("message", {}).get("reasoning")
            if reasoning and not content:
                console.print(f"[dim]Attempt {attempt+1}: Model still reasoning, retrying...[/dim]")
                await asyncio.sleep(3)
                continue

            console.print(f"[yellow]Attempt {attempt+1}: Empty content[/yellow]")
            await asyncio.sleep(2 ** attempt)

        except httpx.TimeoutException:
            console.print(f"[yellow]Attempt {attempt+1}: Timeout[/yellow]")
            await asyncio.sleep(2 ** attempt)
        except json.JSONDecodeError as e:
            console.print(f"[yellow]Attempt {attempt+1}: JSON decode error: {e}[/yellow]")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            console.print(f"[yellow]Attempt {attempt+1}: Error: {e}[/yellow]")
            await asyncio.sleep(2 ** attempt)

    return None


def parse_json_response(content: str) -> Optional[dict]:
    """Parse JSON from LLM response, handling various formats."""
    if not content:
        return None

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    patterns = [
        r'```json\s*(.*?)```',
        r'```\s*(.*?)```',
        r'\{[^{}]*\}',  # Simple object
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if '```' in pattern else match.group(0))
            except json.JSONDecodeError:
                continue

    return None


async def extract_description(name: str, text: str, token: str) -> Optional[str]:
    """Step 1: Extract just the description."""
    prompt = f"""Based on this webpage, write a 1-2 sentence description of the conference.

RULES:
- Do NOT start with the conference name (we already know it)
- Focus on WHAT topics/tech are covered and WHO the audience is
- Be specific about technologies, not generic

GOOD examples:
- "A community-driven event exploring functional programming with Elixir, Erlang, and the BEAM VM. Covers distributed systems, fault tolerance, and real-time applications."
- "Deep-dive into Kubernetes, service mesh, and cloud-native architecture for platform engineers. Features hands-on workshops and production case studies."
- "Single-track conference for frontend developers covering React, TypeScript, and modern tooling. Emphasizes practical patterns over theory."

BAD examples (too generic or starts with name):
- "ReactConf 2026 is a conference about React."
- "A tech conference for developers."
- "KubeCon is an event about Kubernetes."

Conference: {name}
Text: {text[:2000]}

Write ONLY the description:"""

    content = await call_llm_with_retry(prompt, token, max_retries=2)
    if content:
        # Clean up - remove quotes, newlines at start
        content = content.strip().strip('"').strip("'").strip()
        # Remove markdown if present
        if content.startswith("```"):
            content = re.sub(r'```.*?```', '', content, flags=re.DOTALL).strip()
        return content[:500] if content else None
    return None


async def extract_topics(name: str, description: str, token: str) -> list[str]:
    """Step 2: Extract topics based on description."""
    topics_str = ", ".join(TOPIC_TAXONOMY)

    prompt = f"""Conference: {name}
Description: {description}

Which 2-4 topics apply? Choose ONLY from this list:
{topics_str}

Reply with ONLY the topics as a comma-separated list, nothing else.
Example: frontend, ai-ml, cloud"""

    content = await call_llm_with_retry(prompt, token, max_retries=2)
    if content:
        # Parse comma-separated list
        topics = [t.strip().lower() for t in content.replace('\n', ',').split(',')]
        # Filter to valid topics
        valid = [t for t in topics if t in TOPIC_TAXONOMY]
        return valid[:5]
    return []


async def extract_languages(name: str, text: str, token: str) -> list[str]:
    """Step 3: Extract programming languages."""
    langs_str = ", ".join(LANGUAGE_OPTIONS)

    prompt = f"""Conference: {name}
Webpage text (excerpt): {text[:1500]}

Which programming languages are mentioned or relevant? Choose ONLY from:
{langs_str}

Reply with ONLY the languages as a comma-separated list. If none, reply "none".
Example: javascript, python, go"""

    content = await call_llm_with_retry(prompt, token, max_retries=2)
    if content:
        if content.lower().strip() == "none":
            return []
        langs = [l.strip().lower() for l in content.replace('\n', ',').split(',')]
        valid = [l for l in langs if l in LANGUAGE_OPTIONS]
        return valid[:5]
    return []


async def extract_technologies(name: str, text: str, token: str) -> list[str]:
    """Step 4: Extract specific technologies/frameworks."""
    prompt = f"""Conference: {name}
Webpage text: {text[:1500]}

List specific technologies, frameworks, or tools mentioned (React, Kubernetes, TensorFlow, etc).
Reply with ONLY a comma-separated list. If none specific, reply "none".
Example: React, Next.js, Vercel"""

    content = await call_llm_with_retry(prompt, token, max_retries=2)
    if content:
        if content.lower().strip() == "none":
            return []
        techs = [t.strip() for t in content.replace('\n', ',').split(',')]
        # Filter out empty and very long entries
        techs = [t for t in techs if t and len(t) < 30 and t.lower() != "none"]
        return techs[:8]
    return []


def search_ddg(query: str, max_results: int = 3) -> list[dict]:
    """Search DuckDuckGo for conference info. Returns list of {title, href, body}."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return results
    except Exception as e:
        console.print(f"[dim]DDG search failed: {e}[/dim]")
        return []


async def enrich_from_search(name: str, token: str) -> Optional[EnrichedData]:
    """Fallback: Search DuckDuckGo and use snippets + result URLs."""
    console.print(f"[dim]  Searching DDG for '{name}'...[/dim]")

    # Search for the conference
    results = await asyncio.get_event_loop().run_in_executor(
        None, search_ddg, f"{name} conference CFP call for papers"
    )

    if not results:
        return None

    # Combine snippets for context
    snippets = "\n".join([
        f"- {r.get('title', '')}: {r.get('body', '')}"
        for r in results[:3]
    ])

    # Try to fetch the first result URL
    first_url = results[0].get('href') if results else None
    extra_text = ""
    if first_url:
        html = await fetch_page(first_url, max_retries=1)
        if html:
            extra_text = extract_text_from_html(html)[:1500]

    # Combine snippets + fetched content
    combined_text = f"Search results:\n{snippets}\n\nPage content:\n{extra_text}" if extra_text else snippets

    if len(combined_text) < 50:
        return None

    console.print(f"[dim]  Got {len(combined_text)} chars from search...[/dim]")

    # Extract description from search results
    description = await extract_description(name, combined_text, token)
    if not description:
        return None

    console.print(f"[dim]  Got description: {description[:60]}...[/dim]")

    # Extract topics
    topics = await extract_topics(name, description, token)

    return EnrichedData(
        description=description,
        topics=topics,
        languages=[],
        technologies=[],
        audience_level=None,
        format=None,
        talk_types=[],
        industries=[],
    )


async def infer_from_name(name: str, token: str) -> Optional[EnrichedData]:
    """Last resort: Infer topics from conference name alone."""
    topics_str = ", ".join(TOPIC_TAXONOMY)

    prompt = f"""Given ONLY the conference name, infer what topics it likely covers.

Conference name: {name}

Available topics: {topics_str}

Reply with ONLY 2-4 matching topics as a comma-separated list.
If you can't infer anything, reply "unknown".
Example: frontend, ai-ml, cloud"""

    content = await call_llm_with_retry(prompt, token, max_retries=2)
    if content and content.lower().strip() != "unknown":
        topics = [t.strip().lower() for t in content.replace('\n', ',').split(',')]
        valid = [t for t in topics if t in TOPIC_TAXONOMY]
        if valid:
            return EnrichedData(
                description=None,  # Can't generate description without content
                topics=valid[:5],
                languages=[],
                technologies=[],
                audience_level=None,
                format=None,
                talk_types=[],
                industries=[],
            )
    return None


async def enrich_from_url(
    name: str,
    url: str,
    token: str,
) -> Optional[EnrichedData]:
    """Fetch a page and extract enrichment data via LLM (step by step).

    Steps 1 & 2 are sequential (topics depend on description).
    Steps 3 & 4 run in parallel (independent of each other).
    Falls back to name-based inference if URL unreachable.
    """

    # Fetch page
    html = await fetch_page(url)
    if not html:
        # Fallback 1: Try DuckDuckGo search
        console.print(f"[dim]  URL unreachable, trying search...[/dim]")
        result = await enrich_from_search(name, token)
        if result:
            return result

        # Fallback 2: Infer from name alone
        console.print(f"[dim]  Search failed, inferring from name...[/dim]")
        return await infer_from_name(name, token)

    # Extract text
    text = extract_text_from_html(html)
    if len(text) < 50:
        console.print(f"[dim]Page too short: {len(text)} chars[/dim]")
        return None

    console.print(f"[dim]  Extracting from {len(text)} chars...[/dim]")

    # Step 1: Description (most important)
    description = await extract_description(name, text, token)
    if not description:
        console.print(f"[yellow]  Failed to extract description[/yellow]")
        return None

    console.print(f"[dim]  Got description: {description[:60]}...[/dim]")

    # Step 2: Topics (depends on description)
    topics = await extract_topics(name, description, token)
    console.print(f"[dim]  Topics: {topics}[/dim]")

    # Steps 3 & 4 in parallel (independent)
    languages, technologies = await asyncio.gather(
        extract_languages(name, text, token),
        extract_technologies(name, text, token),
    )

    return EnrichedData(
        description=description,
        topics=topics,
        languages=languages,
        technologies=technologies,
        audience_level=None,
        format=None,
        talk_types=[],
        industries=[],
    )
