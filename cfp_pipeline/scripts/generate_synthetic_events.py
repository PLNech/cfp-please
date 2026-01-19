#!/usr/bin/env python3
"""Generate synthetic conversion events for Algolia Recommend Trending models.

This script creates CSV files with synthetic events based on our popularity signals:
- CFPs: hnPoints, githubStars, popularityScore
- Talks: view_count, popularity_score

The generated events can be uploaded to Algolia Dashboard → Recommend → Create Model
→ One-time upload of past events.

Events format (per Algolia docs):
- userToken: unique session identifier
- timestamp: ISO8601 format
- objectID: record ID
- eventType: "conversion" (for Trending)
- eventName: descriptive label

Usage:
    poetry run python -m cfp_pipeline.scripts.generate_synthetic_events

Output:
    synthetic_events_cfps.csv
    synthetic_events_talks.csv
"""

import argparse
import csv
import hashlib
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from algoliasearch.insights.client import InsightsClient
from algoliasearch.search.client import SearchClientSync
from rich.console import Console
from rich.progress import track

console = Console()

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data"

# Event generation parameters
TARGET_EVENTS_CFP = 800  # Target 800 events for CFPs (>250 needed in 30 days)
TARGET_EVENTS_TALKS = 1500  # Target 1500 events for talks
DAYS_BACK = 25  # All events within 25 days (must be <30 for model)


def get_algolia_client() -> SearchClientSync:
    """Get Algolia client from environment variables."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")

    if not app_id or not api_key:
        raise ValueError(
            "ALGOLIA_APP_ID and ALGOLIA_API_KEY must be set in environment"
        )

    return SearchClientSync(app_id, api_key)


def fetch_all_records(client: SearchClientSync, index_name: str) -> list[dict]:
    """Fetch all records from an index using search (paginated)."""
    console.print(f"[cyan]Fetching records from '{index_name}'...[/cyan]")

    records = []
    page = 0
    hits_per_page = 1000

    while True:
        response = client.search_single_index(
            index_name,
            {
                "query": "",
                "hitsPerPage": hits_per_page,
                "page": page,
                "attributesToRetrieve": [
                    "objectID",
                    # CFP fields
                    "hnPoints", "githubStars", "popularityScore", "name",
                    # Talk fields
                    "view_count", "popularity_score", "title",
                ],
            },
        )

        # Convert hits to dicts
        for hit in response.hits:
            record = {}
            # Extract common fields
            record["objectID"] = getattr(hit, "object_id", None)
            record["name"] = getattr(hit, "name", None)
            record["title"] = getattr(hit, "title", None)
            # CFP signals
            record["hnPoints"] = getattr(hit, "hn_points", None) or getattr(hit, "hnPoints", None)
            record["githubStars"] = getattr(hit, "github_stars", None) or getattr(hit, "githubStars", None)
            record["popularityScore"] = getattr(hit, "popularity_score", None) or getattr(hit, "popularityScore", None)
            # Talk signals
            record["view_count"] = getattr(hit, "view_count", None)
            records.append(record)

        # Check if there are more pages
        if page >= (response.nb_pages or 1) - 1:
            break
        page += 1

    console.print(f"  [dim]Fetched {len(records)} records[/dim]")
    return records


def calculate_event_weight(record: dict, is_talk: bool = False) -> int:
    """Calculate how many events a record should generate based on popularity.

    Higher popularity = more events = higher probability of appearing in Trending.
    Base weight ensures every record gets at least 1 event.
    """
    if is_talk:
        views = record.get("view_count", 0) or 0
        popularity = record.get("popularity_score", 0) or 0

        # Weight based on views (log scale to avoid massive skew)
        if views > 100000:
            return 15
        elif views > 50000:
            return 10
        elif views > 10000:
            return 7
        elif views > 1000:
            return 4
        elif popularity > 50:
            return 2
        return 1
    else:
        # CFP weighting - more generous to ensure we hit 250+ events
        hn = record.get("hnPoints", 0) or 0
        github = record.get("githubStars", 0) or 0
        popularity = record.get("popularityScore", 0) or 0

        weight = 2  # Base weight of 2 (ensures ~800 min events for 400 records)

        # HN engagement
        if hn > 100:
            weight += 8
        elif hn > 50:
            weight += 5
        elif hn > 10:
            weight += 3
        elif hn > 0:
            weight += 2

        # GitHub engagement
        if github > 1000:
            weight += 6
        elif github > 100:
            weight += 3
        elif github > 0:
            weight += 1

        # General popularity
        if popularity > 80:
            weight += 4
        elif popularity > 50:
            weight += 2
        elif popularity > 20:
            weight += 1

        return min(weight, 25)  # Higher cap


def generate_user_token(seed: str, event_num: int) -> str:
    """Generate a deterministic but unique user token."""
    data = f"{seed}_{event_num}"
    return f"synthetic_{hashlib.md5(data.encode()).hexdigest()[:12]}"


def generate_timestamp(days_back: int = DAYS_BACK) -> str:
    """Generate a random timestamp within the past N days."""
    now = datetime.utcnow()
    random_days = random.uniform(0, days_back)
    random_hours = random.uniform(0, 24)
    ts = now - timedelta(days=random_days, hours=random_hours)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_events_for_record(
    record: dict,
    event_count: int,
    event_name: str,
    is_talk: bool = False,
) -> Generator[dict, None, None]:
    """Generate conversion events for a single record."""
    object_id = record.get("objectID")
    if not object_id:
        return

    for i in range(event_count):
        yield {
            "userToken": generate_user_token(object_id, i),
            "timestamp": generate_timestamp(),
            "objectID": object_id,
            "eventType": "conversion",
            "eventName": event_name,
        }


def write_csv(events: list[dict], filepath: Path) -> int:
    """Write events to CSV file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["userToken", "timestamp", "objectID", "eventType", "eventName"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    return len(events)


def generate_cfp_events(client: SearchClientSync, index_name: str = "cfps") -> Path:
    """Generate synthetic events for CFP index."""
    records = fetch_all_records(client, index_name)

    # Calculate weights
    weighted_records = []
    for record in records:
        weight = calculate_event_weight(record, is_talk=False)
        weighted_records.append((record, weight))

    # Sort by weight to ensure popular items get events
    weighted_records.sort(key=lambda x: x[1], reverse=True)

    # Generate events
    all_events = []
    events_budget = TARGET_EVENTS_CFP

    for record, weight in track(weighted_records, description="Generating CFP events"):
        if events_budget <= 0:
            break

        # Allocate events based on weight
        event_count = min(weight, events_budget)
        events_budget -= event_count

        events = list(generate_events_for_record(
            record, event_count, "cfp_view", is_talk=False
        ))
        all_events.extend(events)

    # Shuffle to distribute timestamps
    random.shuffle(all_events)

    filepath = OUTPUT_DIR / "synthetic_events_cfps.csv"
    count = write_csv(all_events, filepath)
    console.print(f"[green]Generated {count} events for CFPs → {filepath}[/green]")
    return filepath


def generate_talk_events(client: SearchClientSync, index_name: str = "cfps_talks") -> Path:
    """Generate synthetic events for talks index."""
    records = fetch_all_records(client, index_name)

    # Calculate weights
    weighted_records = []
    for record in records:
        weight = calculate_event_weight(record, is_talk=True)
        weighted_records.append((record, weight))

    # Sort by weight
    weighted_records.sort(key=lambda x: x[1], reverse=True)

    # Generate events
    all_events = []
    events_budget = TARGET_EVENTS_TALKS

    for record, weight in track(weighted_records, description="Generating talk events"):
        if events_budget <= 0:
            break

        event_count = min(weight, events_budget)
        events_budget -= event_count

        events = list(generate_events_for_record(
            record, event_count, "talk_watch", is_talk=True
        ))
        all_events.extend(events)

    # Shuffle
    random.shuffle(all_events)

    filepath = OUTPUT_DIR / "synthetic_events_talks.csv"
    count = write_csv(all_events, filepath)
    console.print(f"[green]Generated {count} events for talks → {filepath}[/green]")
    return filepath


def push_events_to_insights(index_name: str, events: list[dict], batch_size: int = 100):
    """Push events to Algolia Insights API."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")

    if not app_id or not api_key:
        raise ValueError("ALGOLIA_APP_ID and ALGOLIA_API_KEY must be set")

    client = InsightsClient(app_id, api_key)

    console.print(f"[cyan]Pushing {len(events)} events to Insights API for '{index_name}'...[/cyan]")

    # Push in batches
    total_pushed = 0
    for i in track(range(0, len(events), batch_size), description="Pushing events"):
        batch = events[i:i + batch_size]

        # Convert to Insights API format
        insights_events = []
        for evt in batch:
            insights_events.append({
                "eventType": "conversion",
                "eventName": evt["eventName"],
                "index": index_name,
                "userToken": evt["userToken"],
                "objectIDs": [evt["objectID"]],
                "timestamp": int(datetime.fromisoformat(evt["timestamp"].replace("Z", "+00:00")).timestamp() * 1000),
            })

        try:
            client.push_events({"events": insights_events})
            total_pushed += len(batch)
        except Exception as e:
            console.print(f"[red]Error pushing batch: {e}[/red]")

    console.print(f"[green]Pushed {total_pushed} events to Insights API[/green]")
    return total_pushed


def load_events_from_csv(filepath: Path) -> list[dict]:
    """Load events from existing CSV file."""
    events = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(row)
    return events


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate and push synthetic events for Algolia Recommend")
    parser.add_argument("--push", action="store_true", help="Push existing CSV events to Insights API")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate CSV files with fresh timestamps")
    parser.add_argument("--index", choices=["cfps", "cfps_talks", "both"], default="both",
                        help="Which index to process")
    args = parser.parse_args()

    console.print("[bold]Synthetic Events for Algolia Recommend[/bold]")
    console.print(f"Target: {TARGET_EVENTS_CFP} CFP events, {TARGET_EVENTS_TALKS} talk events")
    console.print(f"Time range: past {DAYS_BACK} days\n")

    search_client = get_algolia_client()

    cfp_path = OUTPUT_DIR / "synthetic_events_cfps.csv"
    talk_path = OUTPUT_DIR / "synthetic_events_talks.csv"

    # Regenerate CSVs if requested or they don't exist
    if args.regenerate or not cfp_path.exists() or not talk_path.exists():
        if args.index in ("cfps", "both"):
            generate_cfp_events(search_client)
        if args.index in ("cfps_talks", "both"):
            generate_talk_events(search_client)

    # Push to Insights API if requested
    if args.push:
        if args.index in ("cfps", "both") and cfp_path.exists():
            cfp_events = load_events_from_csv(cfp_path)
            push_events_to_insights("cfps", cfp_events)

        if args.index in ("cfps_talks", "both") and talk_path.exists():
            talk_events = load_events_from_csv(talk_path)
            push_events_to_insights("cfps_talks", talk_events)

        console.print("\n[bold green]Events pushed![/bold green]")
        console.print("Model will retrain automatically (usually within 24h)")
    else:
        console.print("\n[bold green]CSVs generated![/bold green]")
        console.print("\n[bold]Options:[/bold]")
        console.print("1. Run with --push to push events via Insights API")
        console.print("2. Or upload CSVs manually in Dashboard → Recommend → Create Model")
        console.print(f"   - {cfp_path}")
        console.print(f"   - {talk_path}")


if __name__ == "__main__":
    main()
