"""CLI for the CFP pipeline."""

import asyncio
import os

import typer
from dotenv import load_dotenv
from rich.console import Console

from cfp_pipeline.pipeline import run_pipeline, print_cfp_summary, print_stats
from cfp_pipeline.indexers.algolia import (
    get_algolia_client,
    configure_index,
    index_cfps,
    clear_index,
    get_index_stats,
)
from cfp_pipeline.enrichers import enrich_cfps
from cfp_pipeline.validators import validate_cfp_urls

# Load environment variables (override=True to beat shell env vars)
load_dotenv(override=True)

app = typer.Typer(
    name="cfp-pipeline",
    help="CFP aggregator data pipeline",
    add_completion=False,
)
console = Console()


@app.command()
def fetch(
    limit: int = typer.Option(0, "--limit", "-l", help="Limit number of CFPs (0 = all)"),
    show_summary: bool = typer.Option(True, "--summary/--no-summary", help="Show summary table"),
    show_stats: bool = typer.Option(True, "--stats/--no-stats", help="Show statistics"),
    include_closed: bool = typer.Option(False, "--include-closed", help="Include closed CFPs"),
):
    """Fetch CFPs from CallingAllPapers and display summary."""
    cfps = asyncio.run(run_pipeline(filter_open_only=not include_closed))

    if limit > 0:
        cfps = cfps[:limit]

    if show_summary:
        print_cfp_summary(cfps, limit=20)

    if show_stats:
        print_stats(cfps)


@app.command()
def sync(
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configure index settings"),
    include_closed: bool = typer.Option(False, "--include-closed", help="Include closed CFPs"),
):
    """Fetch CFPs and sync to Algolia index."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Make sure to set ALGOLIA_APP_ID and ALGOLIA_API_KEY in .env[/dim]")
        raise typer.Exit(1)

    # Run pipeline
    cfps = asyncio.run(run_pipeline(filter_open_only=not include_closed))

    if not cfps:
        console.print("[yellow]No CFPs to index[/yellow]")
        raise typer.Exit(0)

    # Configure index if requested
    if configure:
        configure_index(client, index_name)

    # Index records
    indexed_count = index_cfps(client, index_name, cfps)

    # Show stats
    stats = get_index_stats(client, index_name)
    console.print(f"\n[bold green]Sync complete![/bold green]")
    console.print(f"  Index: {stats.get('index_name')}")
    console.print(f"  Total records: {stats.get('num_records', 'unknown')}")


@app.command()
def stats(
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
):
    """Show Algolia index statistics."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    stats = get_index_stats(client, index_name)

    if "error" in stats:
        console.print(f"[red]Error: {stats['error']}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Index Statistics[/bold]")
    console.print(f"  Name: {stats['index_name']}")
    console.print(f"  Records: {stats['num_records']}")


@app.command()
def clear(
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear all records from Algolia index."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    if not confirm:
        typer.confirm(
            f"Are you sure you want to clear all records from '{index_name}'?",
            abort=True,
        )

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    clear_index(client, index_name)


@app.command()
def enrich(
    limit: int = typer.Option(10, "--limit", "-l", help="Max CFPs to enrich (0 = all)"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-enrich even if cached"),
    delay: float = typer.Option(0.5, "--delay", "-d", help="Delay between requests (seconds)"),
    show_sample: bool = typer.Option(True, "--sample/--no-sample", help="Show sample enriched record"),
):
    """Enrich CFPs with LLM-extracted descriptions and topics."""
    # Run pipeline to get CFPs
    cfps = asyncio.run(run_pipeline(filter_open_only=True))

    if not cfps:
        console.print("[yellow]No CFPs to enrich[/yellow]")
        raise typer.Exit(0)

    # Enrich
    limit_val = limit if limit > 0 else None
    enriched = asyncio.run(enrich_cfps(cfps, limit=limit_val, force=force, delay=delay))

    # Count enriched
    enriched_count = sum(1 for c in enriched if c.enriched)
    console.print(f"\n[bold]Enrichment Summary[/bold]")
    console.print(f"  Total CFPs: {len(enriched)}")
    console.print(f"  Enriched: {enriched_count}")

    # Show sample
    if show_sample:
        samples = [c for c in enriched if c.enriched][:1]
        if samples:
            s = samples[0]
            console.print(f"\n[bold]Sample Enriched Record:[/bold]")
            console.print(f"  Name: {s.name}")
            console.print(f"  Description: {s.description[:100] if s.description else 'N/A'}...")
            console.print(f"  Topics: {s.topics_normalized}")
            console.print(f"  Languages: {s.languages}")
            console.print(f"  Technologies: {s.technologies}")


@app.command()
def validate(
    workers: int = typer.Option(10, "--workers", "-w", help="Concurrent validation requests"),
):
    """Validate CFP URLs are reachable (check for 404s)."""
    # Run pipeline
    cfps = asyncio.run(run_pipeline(filter_open_only=True))

    if not cfps:
        console.print("[yellow]No CFPs to validate[/yellow]")
        raise typer.Exit(0)

    # Validate URLs
    valid, invalid = asyncio.run(validate_cfp_urls(cfps, max_workers=workers))

    console.print(f"\n[bold]Validation Summary[/bold]")
    console.print(f"  Total: {len(cfps)}")
    console.print(f"  [green]Valid: {len(valid)}[/green]")
    console.print(f"  [red]Invalid: {len(invalid)}[/red]")

    if invalid:
        console.print(f"\n[bold]Invalid CFPs:[/bold]")
        for cfp in invalid[:20]:
            url = cfp.cfp_url or cfp.url or "N/A"
            console.print(f"  - {cfp.name[:50]}")
            console.print(f"    [dim]{url}[/dim]")


@app.command()
def sync_enriched(
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
    enrich_limit: int = typer.Option(0, "--enrich-limit", help="Enrich up to N CFPs before sync (0 = use cache only)"),
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configure index settings"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate URLs before sync"),
):
    """Fetch, enrich (from cache), validate, and sync to Algolia."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Run pipeline
    cfps = asyncio.run(run_pipeline(filter_open_only=True))

    if not cfps:
        console.print("[yellow]No CFPs to sync[/yellow]")
        raise typer.Exit(0)

    # Enrich (from cache or limited new enrichment)
    limit_val = enrich_limit if enrich_limit > 0 else None
    cfps = asyncio.run(enrich_cfps(cfps, limit=limit_val, force=False))

    # Validate URLs (remove 404s)
    if validate:
        cfps, invalid = asyncio.run(validate_cfp_urls(cfps, max_workers=10))
        if invalid:
            console.print(f"[yellow]Removed {len(invalid)} invalid CFPs[/yellow]")

    # Configure and index
    if configure:
        configure_index(client, index_name)

    indexed_count = index_cfps(client, index_name, cfps)

    # Count enriched
    enriched_count = sum(1 for c in cfps if c.enriched)

    stats = get_index_stats(client, index_name)
    console.print(f"\n[bold green]Sync complete![/bold green]")
    console.print(f"  Index: {stats.get('index_name')}")
    console.print(f"  Total records: {stats.get('num_records', 'unknown')}")
    console.print(f"  Enriched records: {enriched_count}")


if __name__ == "__main__":
    app()
