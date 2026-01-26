"""CLI for the CFP pipeline."""

import asyncio
import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

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
from cfp_pipeline.extractors.url_store import URLStore
from cfp_pipeline.extractors.pipeline import extract_from_store, extract_cfp_from_url

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

    # Add favicon fallbacks for CFPs without icons
    from cfp_pipeline.enrichers.favicon import enrich_cfps_with_favicons
    asyncio.run(enrich_cfps_with_favicons(cfps))

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

    # Add favicon fallbacks for CFPs without icons
    from cfp_pipeline.enrichers.favicon import enrich_cfps_with_favicons
    asyncio.run(enrich_cfps_with_favicons(cfps))

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


@app.command()
def collect_urls(
    source: str = typer.Option(
        "all", "--source", "-s",
        help="Source to collect from (all, developerevents, callingallpapers, confstech, cfplist)"
    ),
):
    """Collect conference URLs from sources into the URL store."""
    store = URLStore()

    async def collect():
        total_new = 0

        if source in ("all", "developerevents"):
            from cfp_pipeline.sources.developerevents import get_cfps as get_devevents
            console.print("[cyan]Collecting from developers.events...[/cyan]")
            cfps = await get_devevents()
            urls = [{"url": c.url or c.cfp_url, "name": c.name, "cfp_url": c.cfp_url} for c in cfps if c.url or c.cfp_url]
            new = store.add_many(urls, source="developers.events")
            total_new += new
            console.print(f"  Added {new} new URLs from developers.events")

        if source in ("all", "callingallpapers"):
            from cfp_pipeline.sources.callingallpapers import get_cfps as get_cap
            console.print("[cyan]Collecting from CallingAllPapers...[/cyan]")
            cfps = await get_cap()
            urls = [{"url": c.url or c.cfp_url, "name": c.name, "cfp_url": c.cfp_url} for c in cfps if c.url or c.cfp_url]
            new = store.add_many(urls, source="callingallpapers")
            total_new += new
            console.print(f"  Added {new} new URLs from CallingAllPapers")

        if source in ("all", "confstech"):
            from cfp_pipeline.sources.confstech import get_cfps as get_confstech
            console.print("[cyan]Collecting from confs.tech...[/cyan]")
            cfps = await get_confstech()
            urls = [{"url": c.url or c.cfp_url, "name": c.name, "cfp_url": c.cfp_url} for c in cfps if c.url or c.cfp_url]
            new = store.add_many(urls, source="confs.tech")
            total_new += new
            console.print(f"  Added {new} new URLs from confs.tech")

        if source in ("all", "cfplist"):
            import httpx
            console.print("[cyan]Collecting from CFPlist API...[/cyan]")
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get("https://cfplist.herokuapp.com/api/cfps")
                    resp.raise_for_status()
                    data = resp.json()
                urls = [
                    {"url": c.get("link"), "name": c.get("conferenceName"), "cfp_url": c.get("cfpLink")}
                    for c in data if c.get("link")
                ]
                new = store.add_many(urls, source="cfplist")
                total_new += new
                console.print(f"  Added {new} new URLs from CFPlist")
            except Exception as e:
                console.print(f"[yellow]Failed to fetch CFPlist: {e}[/yellow]")

        return total_new

    total = asyncio.run(collect())

    # Show stats
    stats = store.stats()
    console.print(f"\n[bold green]Collection complete![/bold green]")
    console.print(f"  New URLs added: {total}")
    console.print(f"  Total in store: {stats['total']}")
    console.print(f"  By source: {stats['by_source']}")


@app.command()
def url_stats():
    """Show URL store statistics."""
    from cfp_pipeline.extractors.url_store import RETRYABLE_ERRORS, PERMANENT_ERRORS

    store = URLStore()
    stats = store.stats()

    console.print(f"\n[bold]URL Store Statistics[/bold]")
    console.print(f"  Total: {stats['total']}")
    console.print(f"  Pending: {stats['pending']}")
    console.print(f"  Extracted: [green]{stats['extracted']}[/green]")
    console.print(f"  Failed: [red]{stats['failed']}[/red]")

    console.print(f"\n[bold]By Source:[/bold]")
    for source, count in stats['by_source'].items():
        console.print(f"  {source}: {count}")

    # SPA vs Classic stats
    if stats['extracted'] > 0:
        console.print(f"\n[bold]Rendering Type (extracted sites):[/bold]")
        console.print(f"  SPA (needed JS): {stats['spa_count']} ({stats['spa_percentage']}%)")
        console.print(f"  Classic (static): {stats['classic_count']} ({100 - stats['spa_percentage']}%)")
        if stats['by_fetch_method']:
            console.print(f"\n[bold]By Fetch Method:[/bold]")
            for method, count in stats['by_fetch_method'].items():
                console.print(f"  {method}: {count}")

    # Error breakdown for failed URLs
    if stats['failed'] > 0:
        console.print(f"\n[bold]Error Breakdown (failed sites):[/bold]")
        if stats['by_error_reason']:
            for reason, count in sorted(stats['by_error_reason'].items(), key=lambda x: -x[1]):
                is_retryable = reason.lower() in RETRYABLE_ERRORS
                color = "yellow" if is_retryable else "red"
                retry_tag = " [retryable]" if is_retryable else " [permanent]"
                console.print(f"  [{color}]{reason}: {count}{retry_tag}[/{color}]")
        if stats['by_http_status']:
            console.print(f"\n[bold]By HTTP Status:[/bold]")
            for status, count in sorted(stats['by_http_status'].items()):
                console.print(f"  {status}: {count}")

        # Retry stats
        console.print(f"\n[bold]Retry Status:[/bold]")
        console.print(f"  Retryable (total): {stats['retryable_count']}")
        console.print(f"  Ready for retry now: [cyan]{stats['ready_for_retry']}[/cyan]")
        console.print(f"  Permanently failed: [red]{stats['permanently_failed']}[/red]")

        if stats['by_retry_count']:
            console.print(f"\n[bold]By Retry Attempt:[/bold]")
            for count, num in sorted(stats['by_retry_count'].items()):
                label = f"Attempt #{count + 1}" if count > 0 else "Not retried yet"
                console.print(f"  {label}: {num}")


@app.command()
def extract(
    limit: int = typer.Option(10, "--limit", "-l", help="Max URLs to extract (0 = all pending)"),
    retry: bool = typer.Option(False, "--retry", "-r", help="Include retryable failed URLs (respects backoff)"),
    force_retry: bool = typer.Option(False, "--force-retry", "-f", help="Force retry all retryable URLs (ignores backoff)"),
    workers: int = typer.Option(3, "--workers", "-w", help="Concurrent extractions"),
    url: str = typer.Option(None, "--url", "-u", help="Extract from a single URL"),
):
    """Extract CFP data from pending URLs in the store.

    By default, only processes new/pending URLs. Use --retry to include failed URLs
    that are eligible for retry (transient errors like timeouts, with exponential backoff).

    Permanent failures (404, 403, low_confidence) are not retried.
    """

    async def run_extraction():
        if url:
            # Single URL extraction
            console.print(f"[cyan]Extracting from: {url}[/cyan]")
            cfp = await extract_cfp_from_url(url, source="cli")
            if cfp:
                console.print(f"\n[bold green]Extracted:[/bold green]")
                console.print(f"  Name: {cfp.name}")
                console.print(f"  Description: {cfp.description[:100] if cfp.description else 'N/A'}...")
                console.print(f"  CFP Deadline: {cfp.cfp_end_date_iso or 'N/A'}")
                console.print(f"  Event Date: {cfp.event_start_date_iso or 'N/A'}")
                console.print(f"  Location: {cfp.location.raw or 'N/A'}")
                console.print(f"  Topics: {cfp.topics[:5]}")
                if cfp.full_text:
                    console.print(f"  Full text: {len(cfp.full_text)} chars")
                return [cfp]
            else:
                console.print("[red]Extraction failed[/red]")
                return []

        # Batch extraction from store
        limit_val = limit if limit > 0 else None
        return await extract_from_store(
            limit=limit_val,
            include_retryable=retry or force_retry,
            force_retry=force_retry,
            max_concurrent=workers,
        )

    cfps = asyncio.run(run_extraction())

    if cfps and len(cfps) > 1:
        # Show summary table
        table = Table(title=f"Extracted CFPs ({len(cfps)})")
        table.add_column("Name", style="cyan", max_width=40)
        table.add_column("Deadline", style="red")
        table.add_column("Location", style="green")
        table.add_column("Topics", style="blue", max_width=30)

        for cfp in cfps[:20]:
            table.add_row(
                cfp.name[:40],
                cfp.cfp_end_date_iso or "?",
                cfp.location.raw[:20] if cfp.location.raw else "?",
                ", ".join(cfp.topics[:3]) or "-",
            )

        console.print(table)


@app.command()
def extract_sync(
    limit: int = typer.Option(50, "--limit", "-l", help="Max URLs to extract"),
    workers: int = typer.Option(3, "--workers", "-w", help="Concurrent extractions"),
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
):
    """Extract CFPs from URL store and sync to Algolia."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    async def run():
        limit_val = limit if limit > 0 else None
        return await extract_from_store(limit=limit_val, max_concurrent=workers)

    cfps = asyncio.run(run())

    if not cfps:
        console.print("[yellow]No CFPs extracted[/yellow]")
        raise typer.Exit(0)

    # Apply normalizers
    from cfp_pipeline.normalizers.location import normalize_location
    from cfp_pipeline.normalizers.topics import normalize_topics

    for cfp in cfps:
        cfp.location = normalize_location(cfp.location)
        cleaned, normalized = normalize_topics(cfp.topics)
        cfp.topics = cleaned
        cfp.topics_normalized = normalized

    # Index
    indexed_count = index_cfps(client, index_name, cfps)

    stats = get_index_stats(client, index_name)
    console.print(f"\n[bold green]Extract & Sync complete![/bold green]")
    console.print(f"  Extracted: {len(cfps)} CFPs")
    console.print(f"  Indexed: {indexed_count}")
    console.print(f"  Total in index: {stats.get('num_records', 'unknown')}")


# ===== TALKS COMMANDS =====


@app.command()
def fetch_talks(
    conference: str = typer.Option(None, "--conference", "-c", help="Single conference name to fetch talks for"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of conferences to process (0 = all)"),
    talks_per_conf: int = typer.Option(50, "--talks", "-t", help="Max talks per conference"),
    years: str = typer.Option("2023,2024,2025", "--years", "-y", help="Years to search (comma-separated)"),
    skip_existing: bool = typer.Option(False, "--skip-existing", "-s", help="Skip conferences that already have talks"),
):
    """Fetch YouTube talks for conferences and index to Algolia.

    Creates a separate 'talks' index linked to CFPs by conference ID.
    Use --skip-existing to avoid re-fetching conferences that already have talks.
    """
    from cfp_pipeline.enrichers.youtube import fetch_talks_for_conference, fetch_talks_for_conferences
    from cfp_pipeline.indexers.talks import (
        configure_talks_index,
        index_talks,
        get_talks_index_name,
        get_talks_stats,
    )

    # Parse years
    year_list = [int(y.strip()) for y in years.split(",")] if years else None

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Get existing conference IDs if skipping
    existing_conf_ids = set()
    if skip_existing:
        try:
            index_name = get_talks_index_name()
            # Get all unique conference IDs from talks index
            result = client.search_single_index(
                index_name,
                {"query": "", "hitsPerPage": 0, "facets": ["conference_id"]}
            )
            facets = getattr(result, 'facets', {}) or {}
            if 'conference_id' in facets:
                existing_conf_ids = set(facets['conference_id'].keys())
            console.print(f"[dim]Found {len(existing_conf_ids)} conferences with existing talks[/dim]")
        except Exception as e:
            console.print(f"[dim]Could not check existing talks: {e}[/dim]")

    async def run():
        if conference:
            # Single conference mode
            import hashlib
            conf_id = hashlib.sha256(conference.lower().encode()).hexdigest()[:16]
            if skip_existing and conf_id in existing_conf_ids:
                console.print(f"[yellow]Skipping {conference} (already has talks)[/yellow]")
                return []
            console.print(f"[cyan]Fetching talks for: {conference}[/cyan]")
            return await fetch_talks_for_conference(
                conference_id=conf_id,
                conference_name=conference,
                max_results=talks_per_conf,
                years=year_list,
            )
        else:
            # Multi-conference mode - get conferences from pipeline
            cfps = await run_pipeline(filter_open_only=True)
            if not cfps:
                console.print("[yellow]No conferences found[/yellow]")
                return []

            # Filter out conferences that already have talks
            if skip_existing and existing_conf_ids:
                original_count = len(cfps)
                cfps = [c for c in cfps if c.object_id not in existing_conf_ids]
                skipped = original_count - len(cfps)
                if skipped > 0:
                    console.print(f"[dim]Skipping {skipped} conferences with existing talks[/dim]")

            # Limit conferences
            selected = cfps[:limit] if limit > 0 else cfps
            console.print(f"[cyan]Fetching talks for {len(selected)} conferences...[/cyan]")

            conferences = [{"id": cfp.object_id, "name": cfp.name} for cfp in selected]
            return await fetch_talks_for_conferences(
                conferences=conferences,
                max_results_per_conf=talks_per_conf,
                years=year_list,
                max_concurrent=2,
            )

    talks = asyncio.run(run())

    if not talks:
        console.print("[yellow]No talks found[/yellow]")
        raise typer.Exit(0)

    # Configure and index
    configure_talks_index(client)
    indexed = index_talks(client, talks)

    # Show stats
    stats = get_talks_stats(client)
    console.print(f"\n[bold green]Talks sync complete![/bold green]")
    console.print(f"  Talks fetched: {len(talks)}")
    console.print(f"  Talks indexed: {indexed}")
    console.print(f"  Total in index: {stats.get('num_talks', 'unknown')}")

    # Show sample
    if talks:
        console.print(f"\n[bold]Sample talks:[/bold]")
        for talk in talks[:5]:
            views = f"{talk.view_count:,}" if talk.view_count else "?"
            console.print(f"  - {talk.title[:50]}...")
            console.print(f"    [dim]{talk.conference_name} | {talk.year or '?'} | {views} views[/dim]")


@app.command()
def add_talks(
    conference: str = typer.Option(..., "--conference", "-c", help="Conference name"),
    urls: str = typer.Option(None, "--urls", "-u", help="Comma-separated YouTube URLs"),
    file: str = typer.Option(None, "--file", "-f", help="File with YouTube URLs (one per line, # comments allowed)"),
    speaker: str = typer.Option(None, "--speaker", "-s", help="Override speaker name for all talks"),
):
    """Add specific YouTube talks to the talks index.

    Provide URLs either directly via --urls or from a file.

    Example:
        cfp add-talks -c "KubeCon" -u "https://youtube.com/watch?v=abc,https://youtube.com/watch?v=xyz"
        cfp add-talks -c "PyCon" -f talks.txt -s "Guido van Rossum"
    """
    import hashlib
    from cfp_pipeline.enrichers.youtube import fetch_talks_by_urls
    from cfp_pipeline.indexers.talks import (
        configure_talks_index,
        index_talks,
        get_talks_stats,
    )

    # Collect URLs
    url_list = []
    if urls:
        url_list.extend([u.strip() for u in urls.split(",") if u.strip()])
    if file:
        try:
            with open(file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Support "URL # comment" format
                        url = line.split("#")[0].strip()
                        if url:
                            url_list.append(url)
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            raise typer.Exit(1)

    if not url_list:
        console.print("[red]No URLs provided. Use --urls or --file[/red]")
        raise typer.Exit(1)

    # Generate conference ID
    conf_id = hashlib.sha256(conference.lower().encode()).hexdigest()[:16]

    console.print(f"[cyan]Adding {len(url_list)} talks for: {conference}[/cyan]")
    console.print(f"[dim]Conference ID: {conf_id}[/dim]")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Build URL items
    items = [
        {"url": url, "conference_id": conf_id, "conference_name": conference, "speaker": speaker}
        for url in url_list
    ]

    # Fetch talks
    talks = asyncio.run(fetch_talks_by_urls(items, max_concurrent=3))

    if not talks:
        console.print("[yellow]No talks fetched[/yellow]")
        raise typer.Exit(0)

    # Configure and index
    configure_talks_index(client)
    indexed = index_talks(client, talks)

    # Show stats
    stats = get_talks_stats(client)
    console.print(f"\n[bold green]Talks added![/bold green]")
    console.print(f"  Fetched: {len(talks)}")
    console.print(f"  Indexed: {indexed}")
    console.print(f"  Total in index: {stats.get('num_talks', 'unknown')}")

    # Show what was added
    console.print(f"\n[bold]Added talks:[/bold]")
    for talk in talks:
        views = f"{talk.view_count:,}" if talk.view_count else "?"
        console.print(f"  - {talk.title[:60]}")
        console.print(f"    [dim]{talk.speaker or 'Unknown'} | {talk.year or '?'} | {views} views[/dim]")


@app.command()
def import_channel(
    channel_url: str = typer.Argument(
        ...,
        help="YouTube channel URL (e.g., https://www.youtube.com/@Algolia)"
    ),
    conference_id: str = typer.Option(
        "channel-import",
        "--conference-id", "-c",
        help="Conference ID for all imported talks"
    ),
    conference_name: str = typer.Option(
        None,
        "--conference-name", "-n",
        help="Conference name for all imported talks (default: channel name)"
    ),
    limit: int = typer.Option(
        0, "--limit", "-l",
        help="Max videos to import (0 = all)"
    ),
    min_duration: int = typer.Option(
        5, "--min-duration", "-d",
        help="Minimum video duration in minutes (filter shorts)"
    ),
    skip_existing: bool = typer.Option(
        True, "--skip-existing/--no-skip-existing",
        help="Skip videos already in index"
    ),
):
    """Import all talks from a YouTube channel.

    Example:
        cfp import-channel https://www.youtube.com/@Algolia -n "Algolia" --limit 100
    """
    import yt_dlp
    from cfp_pipeline.indexers.talks import (
        configure_talks_index, index_talks, get_talks_stats
    )
    from cfp_pipeline.models.talk import Talk
    from cfp_pipeline.enrichers.youtube import _get_best_thumbnail, _extract_speaker_from_title

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Fetching videos from {channel_url}...[/cyan]")

    # Get existing video IDs if skip_existing
    existing_ids = set()
    if skip_existing:
        from cfp_pipeline.indexers.talks import get_talks_index_name
        index_name = get_talks_index_name()
        try:
            page = 0
            while True:
                result = client.search_single_index(
                    index_name,
                    {"query": "", "hitsPerPage": 1000, "page": page, "attributesToRetrieve": ["objectID"]}
                )
                for hit in result.hits:
                    oid = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
                    if oid and oid.startswith("yt_"):
                        existing_ids.add(oid[3:])  # Strip yt_ prefix
                if len(result.hits) < 1000:
                    break
                page += 1
            console.print(f"[dim]Found {len(existing_ids)} existing videos in index[/dim]")
        except Exception:
            pass

    # Use yt-dlp to get channel videos
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': True,
        'ignoreerrors': True,
    }

    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Normalize channel URL to videos page
        if not channel_url.endswith('/videos'):
            if channel_url.endswith('/'):
                channel_url = channel_url[:-1]
            channel_url = f"{channel_url}/videos"

        result = ydl.extract_info(channel_url, download=False)
        if result and 'entries' in result:
            channel_title = result.get('playlist_uploader') or result.get('channel') or 'Unknown'
            if conference_name is None:
                conference_name = channel_title

            for entry in result['entries']:
                if entry is None:
                    continue

                video_id = entry.get('id', '')
                if skip_existing and video_id in existing_ids:
                    continue

                duration = entry.get('duration') or 0
                if duration < min_duration * 60:
                    continue

                videos.append(entry)

                if limit > 0 and len(videos) >= limit:
                    break

    console.print(f"[dim]Found {len(videos)} new videos (>={min_duration}min, not in index)[/dim]")

    if not videos:
        console.print("[yellow]No new videos to import[/yellow]")
        raise typer.Exit(0)

    # Convert to Talk objects
    talks = []
    for entry in videos:
        video_id = entry.get('id', '')
        title = entry.get('title', '')
        clean_title, speaker = _extract_speaker_from_title(title)

        # Try to extract year from upload date or title
        year = None
        upload_date = entry.get('timestamp')
        if upload_date:
            from datetime import datetime
            try:
                year = datetime.fromtimestamp(upload_date).year
            except Exception:
                pass

        talk = Talk(
            objectID=f"yt_{video_id}",
            conference_id=conference_id,
            conference_name=conference_name,
            title=clean_title,
            original_title=title,
            speaker=speaker,
            description=(entry.get('description') or '')[:500],
            url=entry.get('url') or f"https://www.youtube.com/watch?v={video_id}",
            thumbnail_url=_get_best_thumbnail(entry),
            year=year,
            duration_seconds=entry.get('duration'),
            duration_minutes=round((entry.get('duration') or 0) / 60) if entry.get('duration') else None,
            view_count=entry.get('view_count'),
        )
        talks.append(talk)

    # Configure and index
    configure_talks_index(client)
    indexed = index_talks(client, talks)

    # Show stats
    stats = get_talks_stats(client)
    console.print(f"\n[bold green]Channel import complete![/bold green]")
    console.print(f"  Channel: {conference_name}")
    console.print(f"  Imported: {indexed}")
    console.print(f"  Total in index: {stats.get('num_talks', 'unknown')}")

    # Show sample
    if talks:
        console.print(f"\n[bold]Sample imported talks:[/bold]")
        for talk in talks[:5]:
            views = f"{talk.view_count:,}" if talk.view_count else "?"
            thumb = "YES" if talk.thumbnail_url else "NO"
            console.print(f"  - [{thumb}] {talk.title[:50]}")
            console.print(f"    [dim]{talk.speaker or 'Unknown'} | {views} views[/dim]")


@app.command()
def talks_stats():
    """Show talks index statistics."""
    from cfp_pipeline.indexers.talks import get_talks_stats, get_talks_index_name

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    stats = get_talks_stats(client)

    if "error" in stats:
        console.print(f"[yellow]Talks index not found or empty[/yellow]")
        console.print(f"[dim]Run 'cfp fetch-talks' to populate it[/dim]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Talks Index Statistics[/bold]")
    console.print(f"  Index: {stats['index_name']}")
    console.print(f"  Total talks: {stats['num_talks']}")


# ===== INTEL COMMANDS =====


@app.command()
def fetch_intel(
    conference: str = typer.Option(None, "--conference", "-c", help="Single conference name"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of conferences to process"),
    include_ddg: bool = typer.Option(False, "--ddg", help="Include DuckDuckGo search (slower)"),
    output: str = typer.Option(None, "--output", "-o", help="Save JSON to file"),
):
    """Gather intelligence about conferences from HN, GitHub, Reddit, DEV.to.

    Pulls rich data: stories, repos, posts, articles, topics, languages, and more.
    All keyless APIs - no authentication required.
    """
    from cfp_pipeline.enrichers.popularity import gather_conference_intel, gather_intel_batch

    async def run():
        if conference:
            console.print(f"[cyan]Gathering intel for: {conference}[/cyan]")
            intel = await gather_conference_intel(conference, include_ddg=include_ddg)
            return {conference: intel}
        else:
            # Get conferences from pipeline
            cfps = await run_pipeline(filter_open_only=True)
            if not cfps:
                console.print("[yellow]No conferences found[/yellow]")
                return {}

            selected = cfps[:limit] if limit > 0 else cfps
            console.print(f"[cyan]Gathering intel for {len(selected)} conferences...[/cyan]")

            names = [cfp.name for cfp in selected]
            return await gather_intel_batch(names, include_ddg=include_ddg)

    results = asyncio.run(run())

    if not results:
        raise typer.Exit(0)

    # Summary table
    table = Table(title=f"Conference Intelligence ({len(results)} conferences)")
    table.add_column("Conference", style="cyan", max_width=35)
    table.add_column("Score", justify="right", style="yellow")
    table.add_column("HN", justify="right")
    table.add_column("GitHub", justify="right")
    table.add_column("Reddit", justify="right")
    table.add_column("DEV.to", justify="right")
    table.add_column("Topics", max_width=30)

    # Sort by popularity score
    sorted_results = sorted(results.items(), key=lambda x: x[1].popularity_score, reverse=True)

    for name, intel in sorted_results[:20]:
        table.add_row(
            name[:35],
            f"{intel.popularity_score:.1f}",
            str(intel.hn_total_stories),
            str(intel.github_total_repos),
            str(intel.reddit_total_posts),
            str(intel.devto_total_articles),
            ", ".join(intel.all_topics[:3]) or "-",
        )

    console.print(table)

    # Save to file if requested
    if output:
        import json
        data = {name: intel.to_dict() for name, intel in results.items()}
        with open(output, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"\n[green]Saved to {output}[/green]")

    # Show detailed sample
    if sorted_results:
        top_name, top_intel = sorted_results[0]
        console.print(f"\n[bold]Top Conference: {top_name}[/bold]")
        console.print(f"  HN: {top_intel.hn_total_stories} stories, {top_intel.hn_total_points} pts")
        console.print(f"  GitHub: {top_intel.github_total_repos} repos, {top_intel.github_total_stars} ⭐")
        console.print(f"  Reddit: {top_intel.reddit_total_posts} posts in r/{', r/'.join(top_intel.reddit_subreddits[:3])}")
        console.print(f"  DEV.to: {top_intel.devto_total_articles} articles")
        console.print(f"  Languages: {', '.join(top_intel.github_languages[:5])}")
        console.print(f"  Topics: {', '.join(top_intel.all_topics[:10])}")
        console.print(f"  Related URLs: {len(top_intel.all_related_urls)}")

        if top_intel.hn_stories:
            console.print(f"\n  [dim]Top HN: {top_intel.hn_stories[0].title}[/dim]")
        if top_intel.github_repos:
            console.print(f"  [dim]Top Repo: {top_intel.github_repos[0].full_name} ({top_intel.github_repos[0].stars}⭐)[/dim]")


@app.command()
def intel_stats(
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
):
    """Show intel data statistics for TalkFlix carousel planning."""
    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Query stats for different carousel categories
    queries = [
        ("Total CFPs", ""),
        ("Intel-enriched", "intelEnriched:true"),
        ("With popularity score", "popularityScore > 0"),
        ("With HN stories", "hnStories > 0"),
        ("With GitHub repos", "githubRepos > 0"),
        ("With Reddit posts", "redditPosts > 0"),
        ("Hot deadlines (<=7d)", "daysUntilCfpClose >= 0 AND daysUntilCfpClose <= 7"),
        ("Warning deadlines (7-30d)", "daysUntilCfpClose > 7 AND daysUntilCfpClose <= 30"),
    ]

    table = Table(title="Intel Statistics for TalkFlix")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for name, filters in queries:
        try:
            params = {"query": "", "hitsPerPage": 0}
            if filters:
                params["filters"] = filters
            res = client.search_single_index(index_name, params)
            table.add_row(name, str(res.nb_hits))
        except Exception as e:
            table.add_row(name, f"[red]Error: {e}[/red]")

    console.print(table)

    # Also check talks index
    console.print("\n[bold]Talks Index:[/bold]")
    talks_index = os.environ.get("ALGOLIA_TALKS_INDEX", "cfps_talks")
    try:
        res = client.search_single_index(talks_index, {"query": "", "hitsPerPage": 0})
        console.print(f"  Total talks: {res.nb_hits}")

        # Viral talks
        res2 = client.search_single_index(
            talks_index,
            {"query": "", "hitsPerPage": 0, "filters": "view_count > 10000"}
        )
        console.print(f"  Viral (>10K views): {res2.nb_hits}")
    except Exception as e:
        console.print(f"  [red]Error: {e}[/red]")

    # Recommendations
    console.print("\n[bold]Recommendations:[/bold]")
    console.print("  - Run [cyan]poetry run cfp sync-intel --limit 0[/cyan] to enrich all CFPs")
    console.print("  - Run [cyan]poetry run cfp fetch-talks --limit 0 --talks 100[/cyan] for more talks")


@app.command()
def sync_intel(
    limit: int = typer.Option(20, "--limit", "-l", help="Max CFPs to enrich with intel (0 = all)"),
    include_ddg: bool = typer.Option(False, "--ddg", help="Include DuckDuckGo search (slower)"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-gather intel even if already enriched"),
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
):
    """Gather conference intel (HN, GitHub, Reddit, DEV.to) and sync to Algolia.

    Enriches CFPs with popularity scores, comments, topics, and community data.
    All keyless APIs - no authentication required.
    """
    from cfp_pipeline.enrichers.popularity import enrich_cfps_with_intel

    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    async def run():
        # Run pipeline to get CFPs
        cfps = await run_pipeline(filter_open_only=True)
        if not cfps:
            return []

        # Enrich with intel
        limit_val = limit if limit > 0 else None
        return await enrich_cfps_with_intel(
            cfps,
            limit=limit_val,
            include_ddg=include_ddg,
            skip_existing=not force,
        )

    cfps = asyncio.run(run())

    if not cfps:
        console.print("[yellow]No CFPs to sync[/yellow]")
        raise typer.Exit(0)

    # Index records
    indexed_count = index_cfps(client, index_name, cfps)

    # Count intel-enriched
    intel_count = sum(1 for c in cfps if c.intel_enriched)

    stats = get_index_stats(client, index_name)
    console.print(f"\n[bold green]Intel sync complete![/bold green]")
    console.print(f"  Index: {stats.get('index_name')}")
    console.print(f"  Total records: {stats.get('num_records', 'unknown')}")
    console.print(f"  Intel-enriched: {intel_count}")

    # Show top by popularity
    enriched = [c for c in cfps if c.intel_enriched and c.popularity_score]
    if enriched:
        top = sorted(enriched, key=lambda x: x.popularity_score or 0, reverse=True)[:5]
        console.print(f"\n[bold]Top by Popularity:[/bold]")
        for c in top:
            console.print(
                f"  {c.popularity_score:.1f} - {c.name[:40]} "
                f"(HN:{c.hn_stories}, GH:{c.github_repos}, Reddit:{c.reddit_posts})"
            )


# ===== SESSIONIZE ENRICHMENT =====


@app.command()
def sync_sessionize(
    limit: int = typer.Option(20, "--limit", "-l", help="Max CFPs to enrich (0 = all with Sessionize URLs)"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-enrich even if already done"),
    url: str = typer.Option(None, "--url", "-u", help="Test a single Sessionize URL"),
    index_name: str = typer.Option(
        None, "--index", "-i",
        help="Algolia index name (default: ALGOLIA_INDEX_NAME env var)"
    ),
):
    """Enrich CFPs with Sessionize data (session formats, speaker benefits, etc).

    Scrapes public Sessionize CFP pages to extract:
    - Session formats (talks, workshops, lightning talks) with durations
    - Speaker benefits (travel, hotel, free ticket)
    - Attendance estimates
    - Tracks/topics
    """
    from cfp_pipeline.enrichers.sessionize import (
        test_scrape,
        enrich_cfps_with_sessionize,
        is_sessionize_url,
    )

    # Single URL test mode
    if url:
        asyncio.run(test_scrape(url))
        return

    index_name = index_name or os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    async def run():
        # Run pipeline to get CFPs
        cfps = await run_pipeline(filter_open_only=True)
        if not cfps:
            return []

        # Count Sessionize URLs
        sessionize_count = sum(
            1 for c in cfps
            if is_sessionize_url(c.cfp_url) or is_sessionize_url(c.url)
        )
        console.print(f"[dim]Found {sessionize_count} CFPs with Sessionize URLs[/dim]")

        # Enrich with Sessionize
        limit_val = limit if limit > 0 else None
        return await enrich_cfps_with_sessionize(
            cfps,
            limit=limit_val,
            skip_existing=not force,
        )

    cfps = asyncio.run(run())

    if not cfps:
        console.print("[yellow]No CFPs to sync[/yellow]")
        raise typer.Exit(0)

    # Index records
    indexed_count = index_cfps(client, index_name, cfps)

    # Count sessionize-enriched
    enriched_count = sum(1 for c in cfps if c.sessionize_enriched)

    stats = get_index_stats(client, index_name)
    console.print(f"\n[bold green]Sessionize sync complete![/bold green]")
    console.print(f"  Index: {stats.get('index_name')}")
    console.print(f"  Total records: {stats.get('num_records', 'unknown')}")
    console.print(f"  Sessionize-enriched: {enriched_count}")

    # Show sample enriched
    enriched = [c for c in cfps if c.sessionize_enriched and c.session_formats]
    if enriched:
        console.print(f"\n[bold]Sample Enriched CFPs:[/bold]")
        for c in enriched[:5]:
            formats = ", ".join(f"{f['name']}" for f in c.session_formats[:3])
            benefits = []
            if c.speaker_benefits.get('travel'):
                benefits.append(f"Travel: {c.speaker_benefits['travel']}")
            if c.speaker_benefits.get('hotel'):
                benefits.append(f"Hotel: {c.speaker_benefits['hotel']}")
            if c.speaker_benefits.get('ticket'):
                benefits.append("Free ticket")

            console.print(f"  {c.name[:40]}")
            console.print(f"    Formats: {formats}")
            if benefits:
                console.print(f"    Benefits: {', '.join(benefits)}")


# ===== SPEAKERS COMMANDS =====


@app.command()
def build_speakers(
    limit: int = typer.Option(0, "--limit", "-l", help="Max speakers to index (0 = all)"),
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configure index settings"),
):
    """Build speaker profiles from talks index and sync to Algolia.

    Aggregates speaker data from cfps_talks: talks, views, topics, conferences.
    Computes achievements based on stats.
    """
    from cfp_pipeline.indexers.speakers import (
        configure_speakers_index,
        build_speakers_from_talks,
        index_speakers,
        get_speakers_stats,
    )

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Build speakers from talks
    limit_val = limit if limit > 0 else None
    speakers = build_speakers_from_talks(client, limit=limit_val)

    if not speakers:
        console.print("[yellow]No speakers found in talks index[/yellow]")
        raise typer.Exit(0)

    # Configure and index
    if configure:
        configure_speakers_index(client)

    indexed = index_speakers(client, speakers)

    # Show stats
    stats = get_speakers_stats(client)
    console.print(f"\n[bold green]Speaker index built![/bold green]")
    console.print(f"  Total speakers: {stats.get('num_speakers', 'unknown')}")

    # Show top speakers
    console.print(f"\n[bold]Top Speakers by Influence:[/bold]")
    for speaker in speakers[:10]:
        badges = " ".join(f"[{a}]" for a in speaker.achievements[:3])
        console.print(
            f"  {speaker.influence_score:,.0f} - {speaker.name}"
            f" ({speaker.talk_count} talks, {speaker.total_views:,} views)"
        )
        if badges:
            console.print(f"    [dim]{badges}[/dim]")


@app.command()
def speaker_stats(
    top: int = typer.Option(20, "--top", "-t", help="Show top N speakers"),
    topic: str = typer.Option(None, "--topic", help="Filter by topic"),
    metric: str = typer.Option("influence", "--metric", "-m", help="Sort by: influence, views, talks"),
):
    """Show speaker leaderboard with stats."""
    from cfp_pipeline.indexers.speakers import get_speakers_index_name, get_speakers_stats

    # Get Algolia client
    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    index_name = get_speakers_index_name()

    # Check if index exists
    stats = get_speakers_stats(client)
    if "error" in stats:
        console.print(f"[yellow]Speakers index not found or empty[/yellow]")
        console.print(f"[dim]Run 'poetry run cfp build-speakers' to create it[/dim]")
        raise typer.Exit(0)

    # Query speakers
    params = {"query": "", "hitsPerPage": top}

    if topic:
        params["filters"] = f"topics:\"{topic}\""

    results = client.search_single_index(index_name, params)
    speakers = results.hits

    if not speakers:
        console.print("[yellow]No speakers found[/yellow]")
        raise typer.Exit(0)

    # Build table
    title = f"Speaker Leaderboard ({stats['num_speakers']} total)"
    if topic:
        title += f" - Topic: {topic}"

    table = Table(title=title)
    table.add_column("#", style="dim", width=3)
    table.add_column("Speaker", style="cyan", max_width=25)
    table.add_column("Company", style="blue", max_width=15)
    table.add_column("Talks", justify="right")
    table.add_column("Views", justify="right", style="green")
    table.add_column("Years", justify="right")
    table.add_column("Influence", justify="right", style="yellow")
    table.add_column("Achievements", max_width=30)

    for i, s in enumerate(speakers, 1):
        views = getattr(s, "total_views", 0) or 0
        views_str = f"{views // 1000}K" if views >= 1000 else str(views)

        achievements = getattr(s, "achievements", []) or []
        badges = ", ".join(achievements[:2]) if achievements else "-"

        table.add_row(
            str(i),
            (getattr(s, "name", "?") or "?")[:25],
            (getattr(s, "company", None) or "-")[:15],
            str(getattr(s, "talk_count", 0) or 0),
            views_str,
            str(getattr(s, "active_years", 0) or 0),
            f"{getattr(s, 'influence_score', 0) or 0:,.0f}",
            badges,
        )

    console.print(table)

    # Show summary stats
    console.print(f"\n[bold]Index Stats:[/bold]")
    console.print(f"  Total speakers: {stats['num_speakers']}")

    # Achievement breakdown
    all_achievements = []
    for s in speakers:
        all_achievements.extend(getattr(s, "achievements", []) or [])

    if all_achievements:
        from collections import Counter
        achievement_counts = Counter(all_achievements).most_common(5)
        console.print(f"\n[bold]Top Achievements:[/bold]")
        for achievement, count in achievement_counts:
            console.print(f"  {achievement}: {count}")


@app.command()
def fix_speakers():
    """Re-extract speaker names from existing talks using improved regex.

    Useful after improving the speaker extraction patterns.
    """
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject
    from cfp_pipeline.indexers.talks import get_talks_index_name
    from cfp_pipeline.enrichers.youtube import _extract_speaker_from_title

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    index_name = get_talks_index_name()
    console.print(f"[cyan]Re-extracting speakers from {index_name}...[/cyan]")

    # Collect all talks that need updating
    updates = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID", "original_title", "title", "speaker"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            object_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            original_title = getattr(hit, "original_title", None) or getattr(hit, "title", "")
            current_speaker = getattr(hit, "speaker", None)

            if not original_title:
                continue

            # Re-extract speaker
            clean_title, new_speaker = _extract_speaker_from_title(original_title)

            # Only update if we found a speaker and it's different/new
            if new_speaker and new_speaker != current_speaker:
                updates.append({
                    "objectID": object_id,
                    "title": clean_title,
                    "speaker": new_speaker,
                    "speakers": [new_speaker],
                })

    client.browse_objects(index_name, aggregator, browse_params)

    console.print(f"[dim]Found {len(updates)} talks to update[/dim]")

    if not updates:
        console.print("[yellow]No talks need updating[/yellow]")
        raise typer.Exit(0)

    # Batch update
    console.print(f"[cyan]Updating {len(updates)} talks...[/cyan]")
    client.partial_update_objects(index_name, updates)

    console.print(f"[bold green]Updated {len(updates)} talks with speaker names![/bold green]")

    # Show sample
    console.print(f"\n[bold]Sample updates:[/bold]")
    for update in updates[:10]:
        console.print(f"  {update['title'][:40]}... → {update['speaker']}")


# ===== Recommend Model Setup =====


@app.command("generate-events")
def generate_events(
    target_cfps: int = typer.Option(500, "--cfps", help="Target number of CFP events"),
    target_talks: int = typer.Option(1000, "--talks", help="Target number of talk events"),
    days: int = typer.Option(60, "--days", help="Event time range (days back)"),
):
    """Generate synthetic conversion events for Algolia Recommend Trending models.

    Creates CSV files based on popularity signals (HN points, GitHub stars, view counts).
    Upload these to Algolia Dashboard → Recommend → Create Model → One-time upload.
    """
    from cfp_pipeline.scripts.generate_synthetic_events import (
        get_algolia_client,
        generate_cfp_events,
        generate_talk_events,
        TARGET_EVENTS_CFP,
        TARGET_EVENTS_TALKS,
        DAYS_BACK,
    )
    import cfp_pipeline.scripts.generate_synthetic_events as gen

    # Override defaults if provided
    gen.TARGET_EVENTS_CFP = target_cfps
    gen.TARGET_EVENTS_TALKS = target_talks
    gen.DAYS_BACK = days

    console.print("[bold]Synthetic Events Generator for Algolia Recommend[/bold]")
    console.print(f"Target: {target_cfps} CFP events, {target_talks} talk events")
    console.print(f"Time range: past {days} days\n")

    try:
        client = get_algolia_client()
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    cfp_path = generate_cfp_events(client)
    talk_path = generate_talk_events(client)

    console.print("\n[bold green]Done![/bold green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Go to https://dashboard.algolia.com → Recommend → Create Model")
    console.print("2. Select 'Trending Items' model")
    console.print("3. Select index (cfps or cfps_talks)")
    console.print("4. Under 'Events collection', click 'One-time upload of past events'")
    console.print(f"5. Upload the corresponding CSV:\n   - {cfp_path}\n   - {talk_path}")


# ===== Discovery Commands =====


@app.command()
def discover_speakers(
    speakers: str = typer.Argument(..., help="Comma-separated speaker names to discover from"),
    max_speakers: int = typer.Option(50, "--max-speakers", "-m", help="Max speakers to process"),
    max_talks: int = typer.Option(30, "--max-talks", "-t", help="Max talks per speaker"),
    concurrent: int = typer.Option(3, "--concurrent", "-c", help="Max concurrent searches"),
    clear: bool = typer.Option(False, "--clear", help="Clear existing discovery data first"),
):
    """Discover talks and channels for specific speakers.

    Uses BFS to find:
    - Talks by the speakers
    - YouTube channels they speak on
    - New speakers who also speak on those channels

    Example:
        cfp discover-speakers "Daniel Phiri,Guido van Rossum"
        cfp discover-speakers "Daniel Phiri" --max-speakers 100 --max-talks 50
    """
    from cfp_pipeline.discovery.engine import DiscoveryEngine

    engine = DiscoveryEngine()

    if clear:
        engine.clear()

    # Load existing if not clearing
    if not clear:
        engine.load()

    # Parse speakers
    speaker_list = [s.strip() for s in speakers.split(",") if s.strip()]
    if not speaker_list:
        console.print("[red]No speakers provided[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Starting discovery from {len(speaker_list)} seed speakers...[/cyan]")

    # Add seed speakers
    added = engine.add_seed_speakers(speaker_list)
    console.print(f"[green]Added {added} seed speakers[/green]")

    # Run discovery
    stats = asyncio.run(engine.discover_from_speakers(
        max_speakers=max_speakers,
        max_talks_per_speaker=max_talks,
        max_concurrent=concurrent,
    ))

    # Save state
    engine.save()

    # Print summary
    engine.print_summary()

    console.print(f"\n[bold]Discovery Stats:[/bold]")
    console.print(f"  Speakers processed: {stats['new_speakers_last_run']}")
    console.print(f"  Channels discovered: {stats['new_channels_last_run']}")
    console.print(f"  Talks discovered: {stats['new_talks_last_run']}")


@app.command()
def discover_channels(
    channel_urls: str = typer.Argument(..., help="Comma-separated YouTube channel URLs"),
    max_talks: int = typer.Option(20, "--max-talks", "-t", help="Max talks per channel"),
    min_duration: int = typer.Option(5, "--min-duration", "-d", help="Min talk duration in minutes"),
):
    """Discover talks and speakers from YouTube channels.

    Extracts all talks from channels and builds a speaker list.

    Example:
        cfp discover-channels "https://youtube.com/@Algolia,https://youtube.com/@Vercel"
        cfp discover-channels "https://youtube.com/@Prisma" --min-duration 10
    """
    import yt_dlp
    from cfp_pipeline.discovery.engine import DiscoveryEngine, _is_conference_channel

    engine = DiscoveryEngine()
    engine.load()

    url_list = [u.strip() for u in channel_urls.split(",") if u.strip()]

    console.print(f"[cyan]Discovering from {len(url_list)} channels...[/cyan]")

    for channel_url in url_list:
        # Normalize to videos page
        if not channel_url.endswith('/videos'):
            if channel_url.endswith('/'):
                channel_url = channel_url[:-1]
            channel_url = f"{channel_url}/videos"

        console.print(f"[dim]Fetching: {channel_url}[/dim]")

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': True,
            'ignoreerrors': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(channel_url, download=False)

                if not result or 'entries' not in result:
                    console.print(f"[yellow]No videos found at {channel_url}[/yellow]")
                    continue

                channel_name = result.get('playlist_uploader') or result.get('channel') or 'Unknown'

                # Check if it's a conference channel
                is_conf = _is_conference_channel(channel_name)

                console.print(f"[cyan]  {channel_name}: {len(result['entries'])} videos[/cyan]")

                # Process each video
                speaker_counts: dict[str, int] = {}
                talks_found = 0

                for entry in result['entries']:
                    if not entry:
                        continue

                    duration = entry.get('duration') or 0
                    if duration < min_duration * 60:
                        continue

                    # Extract speaker from title
                    from cfp_pipeline.enrichers.youtube import _extract_speaker_from_title
                    title = entry.get('title', '')
                    clean_title, speaker = _extract_speaker_from_title(title)

                    video_id = entry.get('id', '')
                    if not video_id:
                        continue

                    # Create talk record
                    if video_id not in engine.talks:
                        engine.talks[video_id] = {
                            'youtube_id': video_id,
                            'title': clean_title,
                            'speaker': speaker,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'channel': channel_name,
                            'year': None,
                            'view_count': entry.get('view_count', 0),
                            'duration_seconds': duration,
                            'thumbnail_url': entry.get('thumbnail'),
                            'source': 'channel_discovery',
                            'discovered_at': datetime.now().isoformat(),
                            'ingested': False,
                        }
                        talks_found += 1

                    if speaker:
                        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

                console.print(f"    [green]Added {talks_found} talks ({len(speaker_counts)} speakers)[/green]")

                # Add or update channel
                if channel_name not in engine.channels:
                    from cfp_pipeline.discovery.engine import DiscoveryChannel
                    engine.channels[channel_name] = DiscoveryChannel(
                        name=channel_name,
                        url=channel_url,
                        source="channel_import",
                        is_conference=is_conf,
                    )

                ch = engine.channels[channel_name]
                ch.talk_count += talks_found
                ch.speakers = list(speaker_counts.keys())

        except Exception as e:
            console.print(f"[red]Error fetching {channel_url}: {e}[/red]")
            continue

    # Save state
    engine.save()
    engine.print_summary()


@app.command()
def explore(
    limit: int = typer.Option(20, "--limit", "-l", help="Items per category"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
    conference_only: bool = typer.Option(False, "--conference-only", help="Only show conference channels"),
):
    """Explore discovered speakers and channels for --explore deep dives.

    Shows the current discovery graph with:
    - Top conference channels (for deep-dive CFP fetching)
    - Top speakers (for finding similar speakers)
    - Statistics about what's been discovered

    Example:
        cfp explore
        cfp explore --limit 50 --conference-only
        cfp explore --format json
    """
    from cfp_pipeline.discovery.engine import DiscoveryEngine, load_discovery_list

    engine = DiscoveryEngine()
    loaded = engine.load()

    if not loaded:
        console.print("[yellow]No discovery data found. Run:[/yellow]")
        console.print("  cfp discover-speakers \"Speaker Name\"")
        console.print("  cfp discover-channels https://youtube.com/@Channel")
        raise typer.Exit(0)

    engine.print_summary()

    if format == "json":
        import json
        data = {
            "channels": engine.get_channels_for_explore(limit=limit),
            "speakers": engine.get_speakers_for_explore(limit=limit),
            "stats": engine.stats,
        }
        console.print(json.dumps(data, indent=2))
        return

    # Show top channels
    channels = engine.get_top_channels(limit=limit, conference_only=conference_only)

    if channels:
        table = Table(title="Top Channels")
        table.add_column("Channel", style="cyan")
        table.add_column("Talks", justify="right")
        table.add_column("Speakers", justify="right")
        table.add_column("Type")

        for ch in channels:
            ch_type = "CONF" if ch.is_conference else "COMP" if ch.is_company else "OTHER"
            table.add_row(
                ch.name[:40],
                str(ch.talk_count),
                str(len(ch.speakers)),
                ch_type,
            )

        console.print(table)

    # Show top speakers
    speakers = engine.get_top_speakers(limit=limit)

    if speakers:
        table = Table(title="Top Speakers")
        table.add_column("Speaker", style="green")
        table.add_column("Talks", justify="right")
        table.add_column("Views", justify="right")
        table.add_column("Channels")

        for sp in speakers:
            table.add_row(
                sp.name[:30],
                str(sp.talk_count),
                f"{sp.total_views:,}",
                str(len(sp.channels)),
            )

        console.print(table)

    console.print("\n[bold]Next steps for deep dives:[/bold]")
    console.print("1. Pick a channel and run: cfp fetch-talks -c \"Channel Name\" --talks 100")
    console.print("2. Pick a speaker and run: cfp discover-speakers \"Speaker Name\" --max-speakers 100")
    console.print("3. Clear and restart: cfp discover-speakers \"New Speaker\" --clear")


@app.command()
def discovery_clear():
    """Clear all discovery data."""
    from cfp_pipeline.discovery.engine import DiscoveryEngine

    engine = DiscoveryEngine()
    engine.clear()

    console.print("[green]Discovery data cleared[/green]")


if __name__ == "__main__":
    app()
