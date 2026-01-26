#!/usr/bin/env python3
"""Clean up garbage speaker profiles from Algolia.

Removes speakers that are clearly not real people (talk titles, product names, etc.)

Usage:
    poetry run python cfp_pipeline/scripts/cleanup_garbage_speakers.py --dry-run
    poetry run python cfp_pipeline/scripts/cleanup_garbage_speakers.py --delete
"""

import argparse
import os
import re
from pathlib import Path

from algoliasearch.search.client import SearchClientSync
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()

# Load env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)


# Patterns that indicate garbage speaker names
GARBAGE_PATTERNS = [
    # Talk titles / technical terms
    r"^(opening|closing)\s+(keynote|ceremony|session)",
    r"^demo\s+(lab|session|room)",
    r"keynote$",
    r"^(tech|cloud|azure|aws|gcp)\s+(talk|training|session|sherpas)",
    r"^(beyond|based|applied|advanced|modern)\s+\w+$",  # "Beyond Pandas", "Based Linting"
    r"^(unlocking|building|scaling|optimizing)\s+",
    r"^(react|vue|angular|python|java|rust)\s+(admin|dev|programming)",
    r"\s+(interview|tutorial|guide|workshop|webinar)$",
    r"^(many|several|multiple)\s+\w+$",
    r"community$",
    r"^playwright\s+\w+$",
    r"^testcontainers\s+",
    r"^(windows|linux|mac)\s+developer$",
    r"^umbraco\s+",
    r"responds$",
    r"^swift\s+programming",
]

# Also exact matches for known garbage
GARBAGE_EXACT = {
    "beyond-pandas", "based-linting", "opening-keynote", "demo-lab",
    "many-lives", "cloud-training", "react-admin", "azure-malayalam",
    "tech-sherpas", "playwright-java", "cloudnativefolks-community",
    "windows-developer", "umbraco-keynote", "testcontainers-desktop",
    "vispero-responds", "swift-programming-logic", "driven-microservices-adoption-journey",
    "optimising-machine-learning-workflows", "open-source-chaos-engineering",
}


def is_garbage_speaker(name: str, slug: str) -> bool:
    """Check if a speaker name is likely garbage."""
    # Exact match on slug
    if slug in GARBAGE_EXACT:
        return True

    # Pattern match on name
    name_lower = name.lower()
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return True

    return False


def find_garbage_speakers(client: SearchClientSync) -> list[dict]:
    """Find all garbage speakers in the index."""
    from algoliasearch.search.models.browse_params_object import BrowseParamsObject

    garbage = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID", "name", "talk_count", "total_views"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            slug = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            name = getattr(hit, "name", "")
            talk_count = getattr(hit, "talk_count", 0)
            total_views = getattr(hit, "total_views", 0)

            if is_garbage_speaker(name, slug):
                garbage.append({
                    "objectID": slug,
                    "name": name,
                    "talk_count": talk_count,
                    "total_views": total_views,
                })

    client.browse_objects("cfps_speakers", aggregator, browse_params)

    return garbage


def main():
    parser = argparse.ArgumentParser(description="Clean up garbage speaker profiles")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be deleted")
    parser.add_argument("--delete", "-d", action="store_true", help="Actually delete garbage speakers")

    args = parser.parse_args()

    if not args.dry_run and not args.delete:
        console.print("[yellow]Specify --dry-run or --delete[/yellow]")
        return

    # Initialize client
    client = SearchClientSync(
        os.environ["ALGOLIA_APP_ID"],
        os.environ["ALGOLIA_API_KEY"],
    )

    # Find garbage
    garbage = find_garbage_speakers(client)

    if not garbage:
        console.print("[green]No garbage speakers found![/green]")
        return

    # Show table
    table = Table(title=f"Garbage Speakers Found ({len(garbage)})")
    table.add_column("Name", style="red")
    table.add_column("Slug")
    table.add_column("Talks", justify="right")
    table.add_column("Views", justify="right")

    for g in sorted(garbage, key=lambda x: x["name"]):
        table.add_row(
            g["name"],
            g["objectID"],
            str(g["talk_count"]),
            f"{g['total_views']:,}",
        )

    console.print(table)

    if args.delete:
        console.print(f"\n[cyan]Deleting {len(garbage)} garbage speakers...[/cyan]")
        object_ids = [g["objectID"] for g in garbage]
        client.delete_objects("cfps_speakers", object_ids)
        console.print("[green]Done![/green]")
    else:
        console.print(f"\n[yellow]Dry run - would delete {len(garbage)} speakers[/yellow]")
        console.print("[dim]Run with --delete to actually remove them[/dim]")


if __name__ == "__main__":
    main()
