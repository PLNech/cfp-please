"""Validate CFP URLs are reachable."""

import asyncio
from typing import Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cfp_pipeline.models import CFP

console = Console()

# Shared client for connection pooling
_client: Optional[httpx.AsyncClient] = None

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0"
)


async def get_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    return _client


async def validate_url(url: str) -> tuple[bool, int]:
    """Check if URL is reachable.

    Returns:
        (is_valid, status_code)
    """
    if not url:
        return False, 0

    try:
        client = await get_client()
        response = await client.head(url)
        # Accept 2xx and 3xx as valid
        is_valid = response.status_code < 400
        return is_valid, response.status_code
    except httpx.TimeoutException:
        return False, 408  # Request Timeout
    except httpx.RequestError:
        return False, 0
    except Exception:
        return False, 0


async def validate_cfp_urls(
    cfps: list[CFP],
    max_workers: int = 10,
    remove_invalid: bool = True,
) -> tuple[list[CFP], list[CFP]]:
    """Validate CFP URLs and optionally remove invalid ones.

    Args:
        cfps: List of CFPs to validate
        max_workers: Concurrent validation limit
        remove_invalid: If True, return only valid CFPs

    Returns:
        (valid_cfps, invalid_cfps)
    """
    console.print(f"[cyan]Validating {len(cfps)} CFP URLs...[/cyan]")

    semaphore = asyncio.Semaphore(max_workers)

    async def check_cfp(cfp: CFP) -> tuple[CFP, bool, int]:
        async with semaphore:
            # Check CFP URL first, fall back to event URL
            url = cfp.cfp_url or cfp.url
            is_valid, status = await validate_url(url)
            return cfp, is_valid, status

    valid_cfps = []
    invalid_cfps = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating...", total=len(cfps))

        results = await asyncio.gather(
            *[check_cfp(cfp) for cfp in cfps],
            return_exceptions=True,
        )

        for result in results:
            progress.advance(task)

            if isinstance(result, Exception):
                continue

            cfp, is_valid, status = result

            if is_valid:
                valid_cfps.append(cfp)
            else:
                invalid_cfps.append(cfp)
                if status == 404:
                    console.print(f"  [red]404[/red] {cfp.name[:50]}")
                elif status == 403:
                    console.print(f"  [yellow]403[/yellow] {cfp.name[:50]}")

    console.print(
        f"[green]Valid: {len(valid_cfps)}[/green] | "
        f"[red]Invalid: {len(invalid_cfps)}[/red]"
    )

    return valid_cfps, invalid_cfps


async def close_client():
    """Close the shared HTTP client."""
    global _client
    if _client:
        await _client.aclose()
        _client = None
