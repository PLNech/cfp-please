"""Main pipeline orchestration."""

import asyncio
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table

from cfp_pipeline.models import CFP
from cfp_pipeline.sources.callingallpapers import get_cfps
from cfp_pipeline.normalizers.location import normalize_location
from cfp_pipeline.normalizers.topics import normalize_topics

console = Console()


def is_cfp_open(cfp: CFP) -> bool:
    """Check if a CFP is currently open (deadline not passed)."""
    if not cfp.cfp_end_date:
        return True  # Assume open if no end date
    now = int(datetime.now().timestamp())
    return cfp.cfp_end_date > now


def enrich_cfp(cfp: CFP) -> CFP:
    """Apply normalizers to enrich a CFP record."""
    # Normalize location
    cfp.location = normalize_location(cfp.location)

    # Normalize topics
    cleaned_topics, categories = normalize_topics(cfp.topics)
    cfp.topics = cleaned_topics
    cfp.topics_normalized = categories

    return cfp


async def run_pipeline(
    filter_open_only: bool = True,
) -> list[CFP]:
    """Run the full data pipeline.

    1. Fetch from CallingAllPapers
    2. Enrich with location and topic normalization
    3. Optionally filter to open CFPs only

    Returns:
        List of enriched CFP records ready for indexing.
    """
    console.print("\n[bold cyan]Starting CFP Pipeline[/bold cyan]\n")

    # Step 1: Fetch
    cfps = await get_cfps()
    console.print(f"[dim]Raw CFPs fetched: {len(cfps)}[/dim]")

    # Step 2: Enrich
    console.print("[cyan]Enriching CFPs...[/cyan]")
    enriched = [enrich_cfp(cfp) for cfp in cfps]

    # Step 3: Filter to open CFPs (deadline not passed)
    if filter_open_only:
        before_count = len(enriched)
        enriched = [cfp for cfp in enriched if is_cfp_open(cfp)]
        console.print(
            f"[dim]Filtered to open CFPs: {len(enriched)} "
            f"(removed {before_count - len(enriched)} closed)[/dim]"
        )

    console.print(f"[green]Pipeline complete: {len(enriched)} CFPs ready[/green]\n")
    return enriched


def print_cfp_summary(cfps: list[CFP], limit: int = 10) -> None:
    """Print a summary table of CFPs."""
    table = Table(title=f"CFP Summary (showing {min(len(cfps), limit)} of {len(cfps)})")
    table.add_column("Name", style="cyan", max_width=30)
    table.add_column("Location", style="green", max_width=20)
    table.add_column("Region", style="yellow")
    table.add_column("CFP Ends", style="red")
    table.add_column("Days", style="magenta", justify="right")
    table.add_column("Categories", style="blue", max_width=25)

    # Sort by days until close
    sorted_cfps = sorted(
        cfps,
        key=lambda c: c.days_until_cfp_close if c.days_until_cfp_close else 999,
    )

    for cfp in sorted_cfps[:limit]:
        location_str = cfp.location.city or cfp.location.country or cfp.location.raw or "?"
        region = cfp.location.region or cfp.location.continent or "-"
        days = str(cfp.days_until_cfp_close) if cfp.days_until_cfp_close is not None else "?"
        categories = ", ".join(cfp.topics_normalized[:3]) or "-"

        table.add_row(
            cfp.name[:30],
            location_str[:20],
            region,
            cfp.cfp_end_date_iso or "?",
            days,
            categories,
        )

    console.print(table)


def print_stats(cfps: list[CFP]) -> None:
    """Print statistics about the CFP dataset."""
    console.print("\n[bold]Statistics[/bold]")

    # By open/closed status (computed from dates)
    open_count = sum(1 for cfp in cfps if is_cfp_open(cfp))
    closed_count = len(cfps) - open_count
    console.print(f"  By status: {{'open': {open_count}, 'closed': {closed_count}}}")

    # By region
    regions = {}
    for cfp in cfps:
        region = cfp.location.region or cfp.location.continent or "Unknown"
        regions[region] = regions.get(region, 0) + 1
    top_regions = sorted(regions.items(), key=lambda x: x[1], reverse=True)[:5]
    console.print(f"  Top regions: {dict(top_regions)}")

    # By category
    categories = {}
    for cfp in cfps:
        for cat in cfp.topics_normalized:
            categories[cat] = categories.get(cat, 0) + 1
    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
    console.print(f"  Top categories: {dict(top_cats)}")
