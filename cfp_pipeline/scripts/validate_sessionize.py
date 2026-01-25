"""Systematic validation of Sessionize scraper.

Usage:
    poetry run python cfp_pipeline/scripts/validate_sessionize.py --batch 0  # First 10
    poetry run python cfp_pipeline/scripts/validate_sessionize.py --batch 1  # Next 10
    poetry run python cfp_pipeline/scripts/validate_sessionize.py --all      # All 100
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(override=True)

from cfp_pipeline.indexers.algolia import get_algolia_client
from cfp_pipeline.extractors.fetch import fetch_url
from cfp_pipeline.enrichers.sessionize import scrape_sessionize, SessionizeData

console = Console()

CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "sessionize_validation"
RESULTS_FILE = CACHE_DIR / "validation_results.json"


def get_sessionize_cfps(limit: int = 100) -> list[dict]:
    """Get CFPs with Sessionize URLs from Algolia."""
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    client = get_algolia_client()
    index_name = os.environ.get('ALGOLIA_INDEX_NAME', 'cfps')

    # Browse all records and filter for Sessionize URLs
    cfps = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=['objectID', 'name', 'cfpUrl', 'url'],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            cfp_url = getattr(hit, 'cfpUrl', None) or getattr(hit, 'url', None)
            if cfp_url and 'sessionize.com' in cfp_url.lower():
                cfps.append({
                    'id': getattr(hit, 'objectID', None),
                    'name': getattr(hit, 'name', 'Unknown'),
                    'url': cfp_url,
                })

    client.browse_objects(index_name, aggregator, browse_params)

    return cfps[:limit]


def extract_relevant_text(html: str) -> str:
    """Extract text sections likely to contain CFP info."""
    soup = BeautifulSoup(html, 'html.parser')

    # Remove noise
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()

    # Get main content
    main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main'))
    if main:
        text = main.get_text(separator='\n')
    else:
        text = soup.get_text(separator='\n')

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Filter to relevant sections (look for keywords)
    keywords = [
        'session', 'format', 'duration', 'minute', 'hour',
        'speaker', 'benefit', 'travel', 'hotel', 'accommodation', 'ticket', 'free',
        'attend', 'participant', 'people',
        'track', 'topic', 'category',
        'workshop', 'talk', 'presentation', 'keynote', 'panel', 'lightning',
        'submission', 'deadline', 'close',
    ]

    relevant_lines = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            # Include context (2 lines before and after)
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            for j in range(start, end):
                if lines[j] not in relevant_lines:
                    relevant_lines.append(lines[j])

    return '\n'.join(relevant_lines[:100])  # Limit to 100 lines


async def validate_single(cfp: dict) -> dict:
    """Validate scraping for a single CFP."""
    url = cfp['url']
    name = cfp['name']

    result = {
        'name': name,
        'url': url,
        'html_fetched': False,
        'relevant_text': '',
        'parsed': None,
        'issues': [],
    }

    # Fetch HTML
    html = await fetch_url(url, use_cache=True)
    if not html:
        result['issues'].append('FETCH_FAILED')
        return result

    result['html_fetched'] = True
    result['relevant_text'] = extract_relevant_text(html)

    # Parse with our scraper
    data = await scrape_sessionize(url)
    result['parsed'] = {
        'is_open': data.is_open,
        'session_formats': [{'name': f.name, 'duration': f.duration} for f in data.session_formats],
        'benefits': {
            'travel': data.benefits.travel,
            'hotel': data.benefits.hotel,
            'ticket': data.benefits.ticket,
            'payment': data.benefits.payment,
        },
        'attendance': data.attendance,
        'tracks': data.tracks,
        'target_audience': data.target_audience,
    }

    # Identify potential issues by checking text for keywords we might have missed
    text_lower = result['relevant_text'].lower()

    # Check for session format keywords not captured
    format_keywords = ['workshop', 'lightning', 'keynote', 'panel', 'session', 'presentation', 'talk']

    # Look for duration mentions, but exclude false positives like "X hours ago", "X hours left", "in X hours"
    duration_match = re.search(r'(\d+)\s*(?:min|minute|hour)', text_lower)
    if duration_match and not data.session_formats:
        # Check if it's a false positive (time countdown, not session duration)
        context = text_lower[max(0, duration_match.start()-20):duration_match.end()+20]
        is_false_positive = any(fp in context for fp in [
            'hours ago', 'hours left', 'hour ago', 'hour left',
            'in \d+ hour', 'finished', 'opens at', 'closes at',
            'minutes ago', 'minutes left',
        ])
        if not is_false_positive:
            result['issues'].append(f'MISSED_DURATION: found "{duration_match.group(0)}" but no formats extracted')

    # Check for benefit keywords not captured
    # But exclude negative statements ("unable to", "not covering", "won't", etc.)
    negative_travel = any(neg in text_lower for neg in [
        'unable to sponsor', 'unable to cover', 'not covering travel',
        "won't cover travel", "don't cover travel", "cannot cover travel",
        "no travel", "travel not", "not able to cover"
    ])
    negative_hotel = any(neg in text_lower for neg in [
        'unable to sponsor', 'unable to cover', 'not covering hotel',
        'not covering accommodation', "won't cover hotel", "no hotel",
        "hotel not", "accommodation not"
    ])

    # More specific check for travel benefit - must have positive indicators
    travel_benefit_patterns = [
        'travel covered', 'cover travel', 'travel reimbursement', 'travel assistance',
        'travel support', 'pay for travel', 'flight reimbursement', 'airfare covered',
        'travel expenses covered', 'reimburse travel'
    ]
    if any(p in text_lower for p in travel_benefit_patterns) and not data.benefits.travel and not negative_travel:
        result['issues'].append('MISSED_TRAVEL: travel benefit pattern in text but not extracted')
    # More specific check for hotel benefit
    hotel_benefit_patterns = [
        'hotel covered', 'accommodation covered', 'cover hotel', 'cover accommodation',
        'free accommodation', 'free hotel', 'complimentary hotel', 'hotel nights',
        'nights accommodation', 'provide accommodation', 'provide hotel'
    ]
    if any(p in text_lower for p in hotel_benefit_patterns) and not data.benefits.hotel and not negative_hotel:
        result['issues'].append('MISSED_HOTEL: hotel benefit pattern in text but not extracted')
    # More specific check for free ticket - look for actual ticket-related phrases
    free_ticket_patterns = [
        'free ticket', 'free admission', 'free entry', 'free attendance',
        'free for speaker', 'speakers attend free', 'complimentary ticket',
        'free-to-attend', 'free to attend', 'free event', 'free conference'
    ]
    if any(p in text_lower for p in free_ticket_patterns) and not data.benefits.ticket:
        result['issues'].append('MISSED_FREE_TICKET: free ticket pattern in text but ticket not True')

    # Check for attendance not captured
    attendance_match = re.search(r'(\d{3,})\s*(?:attendee|participant|people)', text_lower)
    if attendance_match and not data.attendance:
        result['issues'].append(f'MISSED_ATTENDANCE: found "{attendance_match.group(0)}" but not extracted')

    return result


async def validate_batch(cfps: list[dict], batch_num: int) -> list[dict]:
    """Validate a batch of CFPs."""
    console.print(f"\n[bold cyan]Validating batch {batch_num} ({len(cfps)} CFPs)[/bold cyan]\n")

    results = []
    for i, cfp in enumerate(cfps):
        console.print(f"[dim]{i+1}/{len(cfps)}: {cfp['name'][:50]}...[/dim]")
        result = await validate_single(cfp)
        results.append(result)
        await asyncio.sleep(0.3)  # Rate limiting

    return results


def print_validation_report(results: list[dict], verbose: bool = False):
    """Print validation report."""
    console.print("\n" + "="*80)
    console.print("[bold]VALIDATION REPORT[/bold]")
    console.print("="*80 + "\n")

    # Summary stats
    total = len(results)
    fetched = sum(1 for r in results if r['html_fetched'])
    with_formats = sum(1 for r in results if r['parsed'] and r['parsed']['session_formats'])
    with_benefits = sum(1 for r in results if r['parsed'] and any(r['parsed']['benefits'].values()))
    with_attendance = sum(1 for r in results if r['parsed'] and r['parsed']['attendance'])
    with_issues = sum(1 for r in results if r['issues'])

    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    table.add_row("Total CFPs", str(total), "100%")
    table.add_row("HTML Fetched", str(fetched), f"{100*fetched//total}%")
    table.add_row("With Session Formats", str(with_formats), f"{100*with_formats//total}%")
    table.add_row("With Benefits", str(with_benefits), f"{100*with_benefits//total}%")
    table.add_row("With Attendance", str(with_attendance), f"{100*with_attendance//total}%")
    table.add_row("With Issues", str(with_issues), f"{100*with_issues//total}%", style="yellow" if with_issues else "green")

    console.print(table)

    # Issue breakdown
    if with_issues:
        console.print("\n[bold]Issues Found:[/bold]")
        issue_counts = {}
        for r in results:
            for issue in r['issues']:
                issue_type = issue.split(':')[0]
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        for issue_type, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            console.print(f"  {issue_type}: {count}")

    # Detailed results for CFPs with issues
    if verbose:
        console.print("\n[bold]Detailed Issues:[/bold]\n")
        for r in results:
            if r['issues']:
                console.print(f"[yellow]{r['name']}[/yellow]")
                console.print(f"  URL: {r['url']}")
                for issue in r['issues']:
                    console.print(f"  [red]! {issue}[/red]")
                if r['parsed']:
                    console.print(f"  Parsed formats: {r['parsed']['session_formats']}")
                    console.print(f"  Parsed benefits: {r['parsed']['benefits']}")
                console.print()

    # Show sample of relevant text for debugging
    console.print("\n[bold]Sample Relevant Text (first CFP with issues):[/bold]")
    for r in results:
        if r['issues'] and r['relevant_text']:
            console.print(f"\n[cyan]{r['name']}[/cyan]")
            console.print("-" * 40)
            # Show first 50 lines
            lines = r['relevant_text'].split('\n')[:50]
            for line in lines:
                console.print(f"  {line[:100]}")
            break


def save_results(results: list[dict], batch_num: int):
    """Save results to cache for later analysis."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results
    all_results = {}
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            all_results = json.load(f)

    # Add this batch
    all_results[f'batch_{batch_num}'] = results

    with open(RESULTS_FILE, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    console.print(f"\n[dim]Results saved to {RESULTS_FILE}[/dim]")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Validate Sessionize scraper')
    parser.add_argument('--batch', type=int, default=0, help='Batch number (0-9 for first 100)')
    parser.add_argument('--all', action='store_true', help='Run all 100')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--size', type=int, default=10, help='Batch size')
    args = parser.parse_args()

    # Get all Sessionize CFPs
    console.print("[cyan]Fetching Sessionize CFPs from index...[/cyan]")
    all_cfps = get_sessionize_cfps(limit=200)  # Get more than 100 for validation set
    console.print(f"[green]Found {len(all_cfps)} CFPs with Sessionize URLs[/green]")

    if args.all:
        # Run first 100 (training set)
        cfps = all_cfps[:100]
        results = await validate_batch(cfps, 0)
        print_validation_report(results, verbose=args.verbose)
        save_results(results, 'all_100')

    if hasattr(args, 'validation') and args.validation:
        # Run next 100 (validation set)
        cfps = all_cfps[100:200]
        if len(cfps) < 100:
            console.print(f"[yellow]Only {len(cfps)} CFPs available for validation set[/yellow]")
        results = await validate_batch(cfps, 'validation')
        print_validation_report(results, verbose=args.verbose)
        save_results(results, 'validation_100')
    else:
        # Run single batch
        start = args.batch * args.size
        end = start + args.size
        cfps = all_cfps[start:end]

        if not cfps:
            console.print(f"[yellow]No CFPs in batch {args.batch}[/yellow]")
            return

        results = await validate_batch(cfps, args.batch)
        print_validation_report(results, verbose=args.verbose)
        save_results(results, args.batch)


if __name__ == '__main__':
    asyncio.run(main())
