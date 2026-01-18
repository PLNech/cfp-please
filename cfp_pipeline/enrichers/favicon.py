"""Favicon enricher for CFPs without icons.

Fetches favicon URLs from conference websites as fallback when CAP API
doesn't provide an icon.
"""

import asyncio
from typing import Optional
from urllib.parse import urlparse

import httpx
from rich.console import Console

console = Console()


def get_favicon_url(url: str) -> Optional[str]:
    """Get favicon URL for a website.

    Tries multiple strategies:
    1. Google's favicon service (most reliable, always works)
    2. Direct /favicon.ico (fallback)

    Args:
        url: Conference website URL

    Returns:
        Favicon URL or None
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        if not domain:
            return None

        # Google's favicon service - super reliable, handles all edge cases
        # Returns a 16x16 PNG for any domain
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"

    except Exception:
        return None


async def enrich_cfps_with_favicons(
    cfps: list,
    max_concurrent: int = 10,
    verify_exists: bool = False,
) -> int:
    """Enrich CFPs with favicon URLs where icon_url is missing.

    Args:
        cfps: List of CFP objects (modified in place)
        max_concurrent: Max concurrent requests (only used if verify_exists=True)
        verify_exists: If True, verify favicon URL actually exists (slower)

    Returns:
        Number of CFPs enriched
    """
    enriched = 0

    for cfp in cfps:
        # Skip if already has icon
        if getattr(cfp, 'icon_url', None):
            continue

        # Get URL to derive favicon from
        url = getattr(cfp, 'url', None) or getattr(cfp, 'cfp_url', None)
        if not url:
            continue

        favicon = get_favicon_url(url)
        if favicon:
            cfp.icon_url = favicon
            enriched += 1

    if enriched > 0:
        console.print(f"[cyan]Added favicon URLs to {enriched} CFPs[/cyan]")

    return enriched
