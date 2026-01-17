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
):
    """Fetch YouTube talks for conferences and index to Algolia.

    Creates a separate 'talks' index linked to CFPs by conference ID.
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

    async def run():
        if conference:
            # Single conference mode
            # Generate a fake ID from name for testing
            import hashlib
            conf_id = hashlib.sha256(conference.lower().encode()).hexdigest()[:16]
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


if __name__ == "__main__":
    app()
