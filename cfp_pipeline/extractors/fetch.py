"""Smart HTTP fetcher with UA rotation, retries, caching, and Playwright fallback.

Two-tier fetching strategy:
1. Fast path: httpx for static sites (90% of cases)
2. Slow path: Playwright headful Firefox for JS-heavy SPAs

Includes cookie consent banner dismissal for GDPR compliance screens.
"""

import asyncio
import hashlib
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from rich.console import Console

console = Console()

# Realistic Firefox User-Agents (2025-2026)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "html"
CACHE_TTL_HOURS = 24  # Cache HTML for 24h

# SPA detection patterns - if page matches these AND has little content, use Playwright
SPA_MARKERS = [
    r'<div\s+id=["\'](?:root|app|__next|__nuxt)["\']',  # React, Vue, Next.js, Nuxt
    r'<script[^>]*(?:react|vue|angular|svelte)',  # Framework scripts
    r'window\.__INITIAL_STATE__',  # SSR hydration
    r'data-reactroot',
    r'ng-app',
    r'data-v-[a-f0-9]+',  # Vue scoped styles
]

# Minimum content threshold - if less text than this, probably SPA shell
MIN_TEXT_LENGTH = 500


def get_cache_path(url: str) -> Path:
    """Get cache file path for URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    domain = urlparse(url).netloc.replace(".", "_")
    return CACHE_DIR / f"{domain}_{url_hash}.json"


def is_cache_valid(cache_path: Path) -> bool:
    """Check if cached HTML is still valid."""
    if not cache_path.exists():
        return False
    try:
        with open(cache_path) as f:
            cache = json.load(f)
        cached_at = cache.get("cached_at", 0)
        age_hours = (datetime.now().timestamp() - cached_at) / 3600
        return age_hours < CACHE_TTL_HOURS
    except (json.JSONDecodeError, KeyError):
        return False


def load_from_cache(cache_path: Path) -> Optional[str]:
    """Load HTML from cache."""
    try:
        with open(cache_path) as f:
            cache = json.load(f)
        return cache.get("html")
    except Exception:
        return None


def save_to_cache(cache_path: Path, url: str, html: str, method: str = "httpx") -> None:
    """Save HTML to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({
            "url": url,
            "cached_at": datetime.now().timestamp(),
            "method": method,
            "html": html,
        }, f)


def needs_javascript(html: str) -> bool:
    """Detect if page is a SPA shell that needs JavaScript rendering."""
    # Check for SPA markers
    has_spa_markers = any(re.search(pattern, html, re.I) for pattern in SPA_MARKERS)

    # Extract text content (rough)
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    has_little_content = len(text) < MIN_TEXT_LENGTH

    # Need JS if we have SPA markers AND little content
    return has_spa_markers and has_little_content


class HttpxResult:
    """Result from httpx fetch with error details."""
    def __init__(
        self,
        html: Optional[str] = None,
        status: Optional[int] = None,
        error: Optional[str] = None,
    ):
        self.html = html
        self.status = status
        self.error = error  # "timeout", "connection", "ssl", etc.


async def fetch_with_httpx(
    url: str,
    timeout: float = 30.0,
    retries: int = 3,
) -> HttpxResult:
    """Fast fetch with httpx. Returns result with error details."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    last_error = None
    last_status = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, headers=headers)
                last_status = response.status_code
                response.raise_for_status()
                return HttpxResult(html=response.text, status=response.status_code)

        except httpx.TimeoutException as e:
            last_error = "timeout"
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code
            last_error = str(e.response.status_code)
            if e.response.status_code in (403, 429):
                await asyncio.sleep(2 ** attempt)
        except httpx.ConnectError as e:
            last_error = "connection"
        except Exception as e:
            last_error = str(type(e).__name__).lower()

        if attempt < retries - 1:
            await asyncio.sleep(0.5 * (2 ** attempt))

    console.print(f"[dim]httpx failed for {url}: {last_error}[/dim]")
    return HttpxResult(status=last_status, error=last_error)


# Cookie consent button selectors (common patterns)
COOKIE_SELECTORS = [
    # Reject/Decline buttons (preferred)
    'button:has-text("Reject All")',
    'button:has-text("Reject all")',
    'button:has-text("Decline")',
    'button:has-text("Decline All")',
    'button:has-text("Refuse")',
    'button:has-text("Refuser")',
    '[data-testid="reject-all"]',
    '#onetrust-reject-all-handler',
    '.cc-deny',

    # Accept buttons (fallback)
    'button:has-text("Accept All")',
    'button:has-text("Accept all")',
    'button:has-text("Accept")',
    'button:has-text("I Agree")',
    'button:has-text("Got it")',
    'button:has-text("OK")',
    '[data-testid="accept-all"]',
    '#onetrust-accept-btn-handler',
    '.cc-accept',
    '.cookie-consent-accept',

    # Close buttons
    'button:has-text("Close")',
    '[aria-label="Close"]',
    '.modal-close',
    '.cookie-banner-close',
]


async def dismiss_cookie_banner(page) -> bool:
    """Try to dismiss cookie consent banners."""
    for selector in COOKIE_SELECTORS:
        try:
            button = page.locator(selector).first
            if await button.is_visible(timeout=500):
                await button.click(timeout=2000)
                await page.wait_for_timeout(500)  # Wait for banner to close
                return True
        except Exception:
            continue
    return False


async def fetch_with_playwright(
    url: str,
    timeout: float = 30000,
    headless: bool = True,  # Headless for CI/batch, set False for debugging
) -> Optional[str]:
    """Fetch with Playwright Firefox, handling JS and cookie banners."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        console.print("[yellow]Playwright not installed, skipping JS rendering[/yellow]")
        return None

    console.print(f"[cyan]Playwright fetching: {url[:60]}...[/cyan]")

    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            page = await context.new_page()

            # Navigate
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except Exception as e:
                console.print(f"[yellow]Navigation timeout, continuing anyway: {e}[/yellow]")

            # Wait a bit for JS to render
            await page.wait_for_timeout(2000)

            # Try to dismiss cookie banners
            await dismiss_cookie_banner(page)

            # Wait for more content to load
            await page.wait_for_timeout(1000)

            # Get fully rendered HTML
            html = await page.content()

            await browser.close()

            return html

    except Exception as e:
        console.print(f"[red]Playwright error for {url}: {e}[/red]")
        return None


class FetchResult:
    """Result of a URL fetch with metadata."""
    def __init__(
        self,
        html: Optional[str],
        method: str,
        is_spa: bool,
        http_status: Optional[int] = None,
        error_reason: Optional[str] = None,
    ):
        self.html = html
        self.method = method  # "httpx" or "playwright"
        self.is_spa = is_spa  # True if needed JS rendering
        self.http_status = http_status  # HTTP status code
        self.error_reason = error_reason  # "404", "timeout", "connection", etc.


async def fetch_url(
    url: str,
    timeout: float = 30.0,
    retries: int = 3,
    use_cache: bool = True,
    force_playwright: bool = False,
    return_metadata: bool = False,
) -> Optional[str] | FetchResult:
    """Smart fetch: tries httpx first, falls back to Playwright if needed.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        use_cache: Whether to use local cache
        force_playwright: Skip httpx and go straight to Playwright
        return_metadata: If True, return FetchResult with method info

    Returns:
        HTML content (or FetchResult if return_metadata=True), or None if failed
    """
    # Check cache first
    if use_cache:
        cache_path = get_cache_path(url)
        if is_cache_valid(cache_path):
            html = load_from_cache(cache_path)
            if html:
                if return_metadata:
                    # We don't know method from cache, assume classic
                    return FetchResult(html, "cached", False)
                return html

    method = "httpx"
    is_spa = False
    html = None
    http_status = None
    error_reason = None

    # Try httpx first (fast path)
    if not force_playwright:
        httpx_result = await fetch_with_httpx(url, timeout=timeout, retries=retries)
        html = httpx_result.html
        http_status = httpx_result.status
        error_reason = httpx_result.error

        if html and needs_javascript(html):
            console.print(f"[dim]SPA detected, trying Playwright: {url[:50]}...[/dim]")
            is_spa = True
            html = None  # Reset to trigger Playwright

    # Fall back to Playwright (slow path)
    if html is None:
        method = "playwright"
        html = await fetch_with_playwright(url, timeout=timeout * 1000)
        if html:
            http_status = 200  # Playwright succeeded
            error_reason = None

    # Cache successful response
    if html and use_cache:
        save_to_cache(get_cache_path(url), url, html, method=method)

    if html is None:
        console.print(f"[red]Failed to fetch {url}[/red]")

    if return_metadata:
        return FetchResult(html, method, is_spa, http_status, error_reason)

    return html


async def fetch_urls_parallel(
    urls: list[str],
    max_concurrent: int = 10,
    delay_between: float = 0.2,
    use_cache: bool = True,
) -> dict[str, Optional[str]]:
    """Fetch multiple URLs in parallel with rate limiting.

    Args:
        urls: List of URLs to fetch
        max_concurrent: Maximum concurrent requests
        delay_between: Delay between batches
        use_cache: Whether to use local cache

    Returns:
        Dict mapping URL to HTML content (or None if failed)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, Optional[str]] = {}

    async def fetch_with_semaphore(url: str) -> tuple[str, Optional[str]]:
        async with semaphore:
            html = await fetch_url(url, use_cache=use_cache)
            await asyncio.sleep(delay_between)
            return url, html

    tasks = [fetch_with_semaphore(url) for url in urls]

    for coro in asyncio.as_completed(tasks):
        url, html = await coro
        results[url] = html
        if html:
            console.print(f"[dim]Fetched: {url[:60]}...[/dim]")

    return results
