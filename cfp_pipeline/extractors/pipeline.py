"""Main extraction pipeline orchestrator.

Combines all extraction strategies:
1. Structured data (Schema.org, OpenGraph)
2. Platform-specific extractors
3. HTML heuristics

Returns the best available data for a given URL.
"""

import asyncio
import hashlib
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from cfp_pipeline.models import CFP, Location
from cfp_pipeline.extractors.fetch import fetch_url, fetch_urls_parallel
from cfp_pipeline.extractors.structured import ExtractedData, extract_structured_data
from cfp_pipeline.extractors.platforms import extract_platform_specific
from cfp_pipeline.extractors.heuristics import extract_heuristics
from cfp_pipeline.extractors.url_store import URLStore, StoredURL

console = Console()


def merge_extracted_data(*sources: Optional[ExtractedData]) -> ExtractedData:
    """Merge multiple extracted data sources, preferring higher confidence."""
    # Filter out None
    valid_sources = [s for s in sources if s and s.confidence > 0]

    if not valid_sources:
        return ExtractedData(extraction_method="none", confidence=0.0)

    # Sort by confidence descending
    valid_sources.sort(key=lambda x: x.confidence, reverse=True)

    # Start with highest confidence source
    result = valid_sources[0].model_copy()

    # Fill gaps from other sources
    for source in valid_sources[1:]:
        for field, value in source.model_dump().items():
            if field in ("extraction_method", "confidence"):
                continue
            current = getattr(result, field)
            # Fill if current is empty
            if (current is None or current == [] or current == "") and value:
                setattr(result, field, value)

    # Combine extraction methods
    methods = [s.extraction_method for s in valid_sources if s.extraction_method]
    result.extraction_method = "+".join(dict.fromkeys(methods))  # Dedupe while preserving order

    return result


def extracted_to_cfp(
    extracted: ExtractedData,
    url: str,
    cfp_url: Optional[str] = None,
    name_hint: Optional[str] = None,
    source: str = "extracted",
) -> Optional[CFP]:
    """Convert ExtractedData to CFP model.

    Args:
        extracted: Extracted data from page
        url: The URL we extracted from (event website)
        cfp_url: Direct CFP submission URL if different from url
        name_hint: Fallback name if extraction didn't find one
        source: Source identifier
    """
    # Must have at least a name
    name = extracted.name or name_hint
    if not name:
        return None

    # Generate object ID from URL
    url_normalized = url.rstrip("/").lower()
    object_id = hashlib.sha256(url_normalized.encode()).hexdigest()[:16]

    # Parse dates to timestamps
    def iso_to_timestamp(iso_date: Optional[str]) -> Optional[int]:
        if not iso_date:
            return None
        try:
            dt = datetime.strptime(iso_date, "%Y-%m-%d")
            return int(dt.timestamp())
        except ValueError:
            return None

    # Build location
    location = Location(
        city=extracted.city,
        country=extracted.country,
        raw=extracted.location_raw or "",
    )

    cfp = CFP(
        objectID=object_id,
        name=name,
        description=extracted.description,
        url=url,
        cfp_url=cfp_url or url,
        # CFP dates
        cfp_end_date=iso_to_timestamp(extracted.cfp_end_date),
        cfp_end_date_iso=extracted.cfp_end_date,
        cfp_start_date=iso_to_timestamp(extracted.cfp_start_date),
        cfp_start_date_iso=extracted.cfp_start_date,
        # Event dates
        event_start_date=iso_to_timestamp(extracted.event_start_date),
        event_start_date_iso=extracted.event_start_date,
        event_end_date=iso_to_timestamp(extracted.event_end_date),
        event_end_date_iso=extracted.event_end_date,
        # Location
        location=location,
        # Topics
        topics=extracted.topics,
        topics_normalized=[],  # Will be normalized later
        # Full text for search
        full_text=extracted.full_text,
        # Meta
        source=source,
        enriched=True,  # Mark as enriched since we extracted data
    )

    # Set event format
    if extracted.is_online:
        cfp.event_format = "virtual"

    return cfp


class ExtractionResult:
    """Result of CFP extraction with metadata."""
    def __init__(
        self,
        cfp: Optional[CFP],
        fetch_method: str,
        is_spa: bool,
        http_status: Optional[int] = None,
        error_reason: Optional[str] = None,
    ):
        self.cfp = cfp
        self.fetch_method = fetch_method
        self.is_spa = is_spa
        self.http_status = http_status
        self.error_reason = error_reason


async def extract_cfp_from_url(
    url: str,
    cfp_url: Optional[str] = None,
    name_hint: Optional[str] = None,
    source: str = "extracted",
    use_cache: bool = True,
    return_metadata: bool = False,
) -> Optional[CFP] | ExtractionResult:
    """Extract CFP data from a single URL.

    Tries multiple extraction strategies in order:
    1. Platform-specific extractor (if URL matches known platform)
    2. Structured data (Schema.org JSON-LD, OpenGraph)
    3. HTML heuristics (pattern matching)

    Args:
        url: Event or CFP page URL
        cfp_url: Direct CFP submission URL if different
        name_hint: Fallback name if extraction fails
        source: Source identifier for the CFP record
        use_cache: Whether to use cached HTML
        return_metadata: If True, return ExtractionResult with fetch method info

    Returns:
        CFP object (or ExtractionResult if return_metadata=True), or None if extraction failed
    """
    from cfp_pipeline.extractors.fetch import FetchResult

    # Fetch HTML with metadata
    result = await fetch_url(url, use_cache=use_cache, return_metadata=True)

    if isinstance(result, FetchResult):
        html = result.html
        fetch_method = result.method
        is_spa = result.is_spa
        http_status = result.http_status
        error_reason = result.error_reason
    else:
        html = result
        fetch_method = "unknown"
        is_spa = False
        http_status = None
        error_reason = None

    if not html:
        if return_metadata:
            return ExtractionResult(None, fetch_method, is_spa, http_status, error_reason)
        return None

    # Try platform-specific first (highest confidence for known platforms)
    platform_data = extract_platform_specific(html, url)

    # Try structured data
    structured_data = extract_structured_data(html)

    # Try heuristics as fallback
    heuristic_data = extract_heuristics(html)

    # Merge all sources
    merged = merge_extracted_data(platform_data, structured_data, heuristic_data)

    # Skip if confidence is too low
    if merged.confidence < 0.2:
        console.print(f"[yellow]Low confidence ({merged.confidence:.2f}) for {url}[/yellow]")
        if return_metadata:
            return ExtractionResult(None, fetch_method, is_spa, http_status, "low_confidence")
        return None

    # Convert to CFP
    cfp = extracted_to_cfp(
        merged,
        url=url,
        cfp_url=cfp_url,
        name_hint=name_hint,
        source=source,
    )

    if cfp:
        spa_tag = " [SPA]" if is_spa else ""
        console.print(
            f"[green]Extracted:[/green] {cfp.name[:50]}{spa_tag} "
            f"[dim](confidence: {merged.confidence:.2f}, method: {merged.extraction_method})[/dim]"
        )

    if return_metadata:
        return ExtractionResult(cfp, fetch_method, is_spa, http_status, error_reason)

    return cfp


async def extract_cfps_batch(
    entries: list[StoredURL],
    max_concurrent: int = 5,
    use_cache: bool = True,
    is_retry: bool = False,
) -> list[CFP]:
    """Extract CFPs from multiple URLs in parallel.

    Args:
        entries: List of StoredURL entries to process
        max_concurrent: Maximum concurrent extractions
        use_cache: Whether to use cached HTML
        is_retry: Whether these entries are being retried (for retry count tracking)

    Returns:
        List of successfully extracted CFPs
    """
    store = URLStore()
    cfps: list[CFP] = []
    semaphore = asyncio.Semaphore(max_concurrent)
    spa_count = 0
    classic_count = 0

    async def process_entry(entry: StoredURL) -> Optional[CFP]:
        nonlocal spa_count, classic_count
        async with semaphore:
            try:
                result = await extract_cfp_from_url(
                    url=entry.url,
                    cfp_url=entry.cfp_url,
                    name_hint=entry.name,
                    source=entry.source,
                    use_cache=use_cache,
                    return_metadata=True,
                )

                if isinstance(result, ExtractionResult):
                    cfp = result.cfp
                    fetch_method = result.fetch_method
                    is_spa = result.is_spa
                    http_status = result.http_status
                    error_reason = result.error_reason
                else:
                    cfp = result
                    fetch_method = "unknown"
                    is_spa = False
                    http_status = None
                    error_reason = None

                # Track SPA vs classic
                if cfp:
                    if is_spa:
                        spa_count += 1
                    else:
                        classic_count += 1
                    store.mark_extracted(entry.url, fetch_method=fetch_method, is_spa=is_spa)
                    return cfp
                else:
                    store.mark_failed(
                        entry.url,
                        http_status=http_status,
                        error_reason=error_reason,
                        is_retry=is_retry,
                    )
                    return None

            except Exception as e:
                console.print(f"[red]Error extracting {entry.url}: {e}[/red]")
                store.mark_failed(
                    entry.url,
                    error_reason=f"exception:{type(e).__name__}",
                    is_retry=is_retry,
                )
                return None

    # Process with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting CFPs...", total=len(entries))

        tasks = [process_entry(entry) for entry in entries]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                cfps.append(result)
            progress.advance(task)

    # Show SPA stats
    total_extracted = spa_count + classic_count
    if total_extracted > 0:
        spa_pct = round(spa_count / total_extracted * 100, 1)
        console.print(f"\n[green]Successfully extracted {len(cfps)}/{len(entries)} CFPs[/green]")
        console.print(f"[dim]SPA sites: {spa_count} ({spa_pct}%) | Classic: {classic_count} ({100 - spa_pct}%)[/dim]")
    else:
        console.print(f"\n[green]Successfully extracted {len(cfps)}/{len(entries)} CFPs[/green]")

    return cfps


async def extract_from_store(
    limit: Optional[int] = None,
    include_retryable: bool = False,
    force_retry: bool = False,
    max_concurrent: int = 5,
) -> list[CFP]:
    """Extract CFPs from pending URLs in the store.

    Args:
        limit: Maximum number of URLs to process
        include_retryable: Include URLs eligible for retry (with backoff)
        force_retry: Force retry all retryable URLs (ignore backoff timing)
        max_concurrent: Maximum concurrent extractions

    Returns:
        List of extracted CFPs
    """
    store = URLStore()
    all_cfps: list[CFP] = []

    # Get pending URLs
    pending = store.get_pending(limit=limit)

    if pending:
        console.print(f"\n[cyan]Extracting {len(pending)} pending URLs...[/cyan]\n")
        cfps = await extract_cfps_batch(pending, max_concurrent=max_concurrent, is_retry=False)
        all_cfps.extend(cfps)

    # Optionally retry failed URLs
    if include_retryable:
        remaining_limit = (limit - len(pending)) if limit else None
        if remaining_limit is None or remaining_limit > 0:
            retryable = store.get_retryable(limit=remaining_limit, ignore_backoff=force_retry)

            if retryable:
                console.print(f"\n[cyan]Retrying {len(retryable)} failed URLs (with backoff)...[/cyan]")
                # Show retry context
                retry_counts = {}
                for entry in retryable:
                    retry_counts[entry.retry_count] = retry_counts.get(entry.retry_count, 0) + 1
                for count, num in sorted(retry_counts.items()):
                    console.print(f"  [dim]Attempt #{count + 1}: {num} URLs[/dim]")

                # Clear cache for retries - we want fresh fetches
                cfps = await extract_cfps_batch(
                    retryable,
                    max_concurrent=max_concurrent,
                    use_cache=False,  # Fresh fetch for retries
                    is_retry=True,
                )
                all_cfps.extend(cfps)
            else:
                console.print("[dim]No URLs ready for retry (check backoff timing)[/dim]")

    if not all_cfps and not pending:
        console.print("[yellow]No pending or retryable URLs to extract[/yellow]")

    return all_cfps
