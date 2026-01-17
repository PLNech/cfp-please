"""Enrichment module for CFP data.

Supports parallel processing with configurable concurrency (default: 8 workers).
"""

import asyncio
from typing import Optional

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn

from cfp_pipeline.models import CFP
from cfp_pipeline.enrichers.llm import (
    enrich_from_url,
    get_enablers_token,
    load_enrichment_cache,
    save_enrichment_cache,
    close_http_client,
)
from cfp_pipeline.enrichers.schema import EnrichedData

console = Console()

# Max concurrent LLM workers
MAX_CONCURRENT_WORKERS = 8


def apply_enrichment(cfp: CFP, enrichment: EnrichedData) -> CFP:
    """Apply enrichment data to a CFP record."""
    cfp.description = enrichment.description
    cfp.topics_normalized = enrichment.topics
    cfp.languages = enrichment.languages
    cfp.audience_level = enrichment.audience_level
    cfp.event_format = enrichment.format
    cfp.talk_types = enrichment.talk_types
    cfp.industries = enrichment.industries
    cfp.technologies = enrichment.technologies
    cfp.enriched = True
    return cfp


async def enrich_cfp(
    cfp: CFP,
    token: str,
    cache: dict[str, EnrichedData],
    semaphore: asyncio.Semaphore,
    force: bool = False,
) -> tuple[CFP, bool]:
    """Enrich a single CFP with LLM-extracted data.

    Returns tuple of (CFP, was_newly_enriched).
    """
    # Check cache first (no semaphore needed)
    if not force and cfp.object_id in cache:
        return apply_enrichment(cfp, cache[cfp.object_id]), False

    # Skip if already enriched and not forcing
    if not force and cfp.enriched and cfp.description:
        return cfp, False

    # Try event URL first, then CFP URL
    url = cfp.url or cfp.cfp_url
    if not url:
        return cfp, False

    # Acquire semaphore for LLM calls
    async with semaphore:
        enrichment = await enrich_from_url(cfp.name, url, token)

    if enrichment:
        # Update cache (thread-safe as we're single-threaded async)
        cache[cfp.object_id] = enrichment
        return apply_enrichment(cfp, enrichment), True

    return cfp, False


async def enrich_cfps(
    cfps: list[CFP],
    limit: Optional[int] = None,
    force: bool = False,
    delay: float = 0.5,  # Kept for CLI compatibility, but less relevant with parallel
    max_workers: int = MAX_CONCURRENT_WORKERS,
) -> list[CFP]:
    """Enrich multiple CFPs with LLM-extracted data.

    Args:
        cfps: List of CFPs to enrich
        limit: Max number to enrich (None = all)
        force: Re-enrich even if already enriched
        delay: Delay between requests (legacy, less relevant with parallel)
        max_workers: Max concurrent enrichment workers (default: 8)

    Returns:
        List of enriched CFPs
    """
    try:
        token = get_enablers_token()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Set ENABLERS_JWT in .env or environment[/dim]")
        return cfps

    # Load cache
    cache = load_enrichment_cache()
    console.print(f"[dim]Loaded {len(cache)} cached enrichments[/dim]")

    # Filter to CFPs needing enrichment
    if not force:
        to_enrich = [c for c in cfps if c.object_id not in cache and not c.enriched]
    else:
        to_enrich = list(cfps)  # Copy to avoid mutation

    if limit:
        to_enrich = to_enrich[:limit]

    if not to_enrich:
        console.print("[green]All CFPs already enriched[/green]")
        # Apply cache to all
        return [
            apply_enrichment(c, cache[c.object_id]) if c.object_id in cache else c
            for c in cfps
        ]

    console.print(f"[cyan]Enriching {len(to_enrich)} CFPs with {max_workers} workers...[/cyan]")

    # Semaphore limits concurrent LLM calls
    semaphore = asyncio.Semaphore(max_workers)
    enriched_count = 0

    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Enriching...", total=len(to_enrich))

            # Create all tasks
            async def process_cfp(cfp: CFP) -> tuple[CFP, bool]:
                result = await enrich_cfp(cfp, token, cache, semaphore, force)
                progress.advance(task)
                return result

            # Run all in parallel (semaphore controls concurrency)
            results = await asyncio.gather(
                *[process_cfp(cfp) for cfp in to_enrich],
                return_exceptions=True,
            )

        # Count successful enrichments
        for result in results:
            if isinstance(result, tuple) and result[1]:
                enriched_count += 1
            elif isinstance(result, Exception):
                console.print(f"[yellow]Error: {result}[/yellow]")

    finally:
        # Save cache even if interrupted
        save_enrichment_cache(cache)
        # Close HTTP client
        await close_http_client()

    console.print(f"[green]Enriched {enriched_count}/{len(to_enrich)} CFPs[/green]")

    # Apply cache to all CFPs
    result = []
    for cfp in cfps:
        if cfp.object_id in cache:
            result.append(apply_enrichment(cfp, cache[cfp.object_id]))
        else:
            result.append(cfp)

    return result
