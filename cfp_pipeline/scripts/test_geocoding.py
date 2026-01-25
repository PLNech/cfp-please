"""Test geocoding pipeline on 100 Sessionize CFPs.

Usage:
    poetry run python cfp_pipeline/scripts/test_geocoding.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

load_dotenv(override=True)

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cfp_pipeline.indexers.algolia import get_algolia_client
from cfp_pipeline.enrichers.sessionize import (
    scrape_sessionize,
    geocode_location,
    extract_location_entities,
)

console = Console()


def get_sessionize_cfps(limit: int = 100) -> list[dict]:
    """Get CFPs with Sessionize URLs from Algolia."""
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    client = get_algolia_client()
    index_name = os.environ.get('ALGOLIA_INDEX_NAME', 'cfps')

    cfps = []
    browse_params = BrowseParamsObject(
        attributes_to_retrieve=['objectID', 'name', 'cfpUrl', 'url', 'location'],
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
                    'existing_location': getattr(hit, 'location', {}),
                })

    client.browse_objects(index_name, aggregator, browse_params)
    return cfps[:limit]


async def test_geocoding_pipeline(limit: int = 100):
    """Test geocoding on N Sessionize CFPs."""
    console.print(f"[cyan]Fetching up to {limit} Sessionize CFPs...[/cyan]")
    cfps = get_sessionize_cfps(limit)
    console.print(f"[green]Found {len(cfps)} CFPs with Sessionize URLs[/green]\n")

    results = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing...", total=len(cfps))

        for cfp in cfps:
            name = cfp['name'][:40]
            progress.update(task, description=f"[cyan]{name}...")

            try:
                # Scrape to get location_raw
                data = await scrape_sessionize(cfp['url'])
                location_raw = data.location_raw or ""

                # Try geocoding
                coords = None
                ner_entities = {}
                if location_raw:
                    coords = await geocode_location(location_raw)
                    ner_entities = extract_location_entities(location_raw)

                results.append({
                    'name': cfp['name'],
                    'url': cfp['url'],
                    'location_raw': location_raw,
                    'ner_city': ner_entities.get('city', ''),
                    'ner_country': ner_entities.get('country', ''),
                    'lat': coords[0] if coords else None,
                    'lng': coords[1] if coords else None,
                    'geocoded': coords is not None,
                    'has_location': bool(location_raw),
                })

            except Exception as e:
                results.append({
                    'name': cfp['name'],
                    'url': cfp['url'],
                    'location_raw': '',
                    'ner_city': '',
                    'ner_country': '',
                    'lat': None,
                    'lng': None,
                    'geocoded': False,
                    'has_location': False,
                    'error': str(e),
                })

            progress.advance(task)
            await asyncio.sleep(0.5)  # Rate limiting for Nominatim

    # Stats
    total = len(results)
    has_location = sum(1 for r in results if r['has_location'])
    geocoded = sum(1 for r in results if r['geocoded'])
    has_ner_city = sum(1 for r in results if r['ner_city'])
    has_ner_country = sum(1 for r in results if r['ner_country'])
    errors = sum(1 for r in results if r.get('error'))

    console.print("\n" + "=" * 80)
    console.print("[bold]GEOCODING PIPELINE STATS[/bold]")
    console.print("=" * 80 + "\n")

    stats_table = Table(title="Summary")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Count", justify="right")
    stats_table.add_column("Rate", justify="right")

    stats_table.add_row("Total CFPs", str(total), "100%")
    stats_table.add_row("Has location_raw", str(has_location), f"{100*has_location//total}%")
    stats_table.add_row("Successfully geocoded", str(geocoded), f"{100*geocoded//total}%")
    stats_table.add_row("NER: city extracted", str(has_ner_city), f"{100*has_ner_city//total}%")
    stats_table.add_row("NER: country extracted", str(has_ner_country), f"{100*has_ner_country//total}%")
    stats_table.add_row("Errors", str(errors), f"{100*errors//total}%" if total else "0%")

    console.print(stats_table)

    # Show sample results
    console.print("\n[bold]Sample Results (first 20):[/bold]\n")

    sample_table = Table()
    sample_table.add_column("Conference", style="cyan", max_width=30)
    sample_table.add_column("Location Raw", max_width=35)
    sample_table.add_column("NER", max_width=25)
    sample_table.add_column("Coords", max_width=20)
    sample_table.add_column("Status")

    for r in results[:20]:
        ner = f"{r['ner_city']}, {r['ner_country']}" if r['ner_city'] else r['ner_country'] or "-"
        coords = f"{r['lat']:.2f}, {r['lng']:.2f}" if r['lat'] else "-"
        status = "[green]✓[/green]" if r['geocoded'] else ("[red]✗[/red]" if r['has_location'] else "[dim]no loc[/dim]")

        sample_table.add_row(
            r['name'][:30],
            (r['location_raw'] or '-')[:35],
            ner[:25],
            coords,
            status,
        )

    console.print(sample_table)

    # Show failures for debugging
    failures = [r for r in results if r['has_location'] and not r['geocoded']]
    if failures:
        console.print(f"\n[yellow]Geocoding Failures ({len(failures)}):[/yellow]")
        for f in failures[:10]:
            console.print(f"  • {f['name'][:40]}: '{f['location_raw']}'")

    return results


if __name__ == '__main__':
    asyncio.run(test_geocoding_pipeline(100))
