#!/usr/bin/env python3
"""Smart transcript enrichment pipeline.

Pipeline stages:
1. SCAN: Check transcript availability for all talks (fast, no download)
2. RANK: Prioritize by views, Algolia speakers, recency
3. ENRICH: Fetch transcripts + MiniMax summaries with retry logic
4. INDEX: Batch update Algolia

Usage:
    poetry run python cfp_pipeline/scripts/transcript_pipeline.py --scan     # Check availability
    poetry run python cfp_pipeline/scripts/transcript_pipeline.py --enrich   # Run enrichment
    poetry run python cfp_pipeline/scripts/transcript_pipeline.py --all      # Full pipeline
"""
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Load env
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

from algoliasearch.search.client import SearchClientSync
from algoliasearch.search.models.browse_params_object import BrowseParamsObject

console = Console()

APP_ID = os.environ['ALGOLIA_APP_ID']
API_KEY = os.environ['ALGOLIA_API_KEY']
ENABLERS_JWT = os.environ.get('ENABLERS_JWT', '')
ENABLERS_URL = "https://inference.api.enablers.algolia.net/v1/chat/completions"
MODEL = "minimax-m2.1"

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
SCAN_RESULTS_PATH = DATA_DIR / "transcript_scan.json"


@dataclass
class TalkInfo:
    """Talk metadata for prioritization."""
    object_id: str
    title: str
    speaker: str
    view_count: int
    is_algolia_speaker: bool
    year: int
    has_transcript: bool = False
    transcript_enriched: bool = False

    @property
    def priority_score(self) -> float:
        """Higher = process first."""
        score = 0.0
        # Algolia speakers get big boost
        if self.is_algolia_speaker:
            score += 100000
        # Views matter (log scale to not over-weight viral)
        score += min(self.view_count, 100000)
        # Recent talks slightly preferred
        if self.year:
            score += (self.year - 2015) * 100
        return score


def get_video_id(object_id: str) -> Optional[str]:
    """Extract YouTube video ID from objectID."""
    if object_id.startswith("yt_"):
        return object_id[3:]
    return None


def check_transcript_available(video_id: str) -> bool:
    """Quick check if English transcript exists - SKIP for speed, handle in fetch."""
    # Skip pre-check, just try to fetch and handle failure gracefully
    return True


def fetch_transcript(video_id: str, retries: int = 3) -> Optional[str]:
    """Fetch transcript with retry logic."""
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retries):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "sub"
            try:
                cmd = [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--sub-lang", "en",
                    "--sub-format", "json3",
                    "--skip-download",
                    "--no-warnings",
                    "--socket-timeout", "30",
                    "-o", str(output_path),
                    url
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

                sub_file = output_path.with_suffix(".en.json3")
                if not sub_file.exists():
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return None

                with open(sub_file) as f:
                    data = json.load(f)

                text_parts = []
                for event in data.get("events", []):
                    for seg in event.get("segs", []):
                        text = seg.get("utf8", "")
                        if text and text.strip() and text not in ["[Music]", "[Applause]", "\n"]:
                            text_parts.append(text.strip())

                if not text_parts:
                    return None

                full_text = " ".join(text_parts)
                full_text = re.sub(r'\s+', ' ', full_text).strip()
                return full_text

            except subprocess.TimeoutExpired:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue

    return None


def summarize_with_minimax(transcript: str, title: str, speaker: str, retries: int = 3) -> dict:
    """Summarize transcript with retry logic."""
    # Truncate if too long
    max_length = 6000
    if len(transcript) > max_length:
        transcript = transcript[:max_length] + "..."

    prompt = f"""Analyze this conference talk transcript and provide:
1. A 2-3 sentence summary capturing the main points
2. 5-10 relevant keywords (technical terms, concepts)
3. 2-5 main topics/themes
4. 3-5 key takeaways for the audience

Talk: "{title}" by {speaker or "Unknown Speaker"}

Transcript:
{transcript}

Respond in JSON format:
{{
  "summary": "...",
  "keywords": ["...", "..."],
  "topics": ["...", "..."],
  "key_takeaways": ["...", "..."]
}}"""

    headers = {
        "Authorization": f"Bearer {ENABLERS_JWT}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    for attempt in range(retries):
        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(ENABLERS_URL, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return json.loads(json_match.group())

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue

    return {}


def scan_all_talks(client: SearchClientSync) -> list[TalkInfo]:
    """Scan all talks and check transcript availability."""
    console.print("[bold]STAGE 1: Scanning all talks...[/bold]")

    talks = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=[
            "objectID", "title", "speaker", "view_count",
            "year", "transcript_enriched"
        ],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            obj_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            if not obj_id or not obj_id.startswith("yt_"):
                continue

            # Skip already enriched
            if getattr(hit, "transcript_enriched", False):
                continue

            talks.append(TalkInfo(
                object_id=obj_id,
                title=getattr(hit, "title", "") or "",
                speaker=getattr(hit, "speaker", "") or "",
                view_count=getattr(hit, "view_count", 0) or 0,
                is_algolia_speaker=False,  # Will check later
                year=getattr(hit, "year", 0) or 0,
                transcript_enriched=False,
            ))

    client.browse_objects("cfps_talks", aggregator, browse_params)
    console.print(f"Found {len(talks)} talks to check")

    # Load Algolia speakers for flagging
    speakers_path = DATA_DIR / "algolia_speakers.json"
    algolia_names = set()
    if speakers_path.exists():
        with open(speakers_path) as f:
            data = json.load(f)
            for s in data.get("speakers", []):
                algolia_names.add(s["name"].lower())
                for alias in s.get("aliases", []):
                    algolia_names.add(alias.lower())

    # Flag Algolia speakers
    for talk in talks:
        if talk.speaker and talk.speaker.lower() in algolia_names:
            talk.is_algolia_speaker = True

    # Skip slow transcript check - we'll handle failures during enrichment
    # Mark all as potentially available
    for talk in talks:
        talk.has_transcript = True

    available = talks
    console.print(f"[green]Talks to enrich: {len(available)} (will skip failures during enrichment)[/green]")

    # Sort by priority
    available.sort(key=lambda t: t.priority_score, reverse=True)

    # Save to file
    scan_data = {
        "scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_talks": len(talks),
        "transcripts_available": len(available),
        "talks": [
            {
                "object_id": t.object_id,
                "title": t.title,
                "speaker": t.speaker,
                "view_count": t.view_count,
                "is_algolia_speaker": t.is_algolia_speaker,
                "year": t.year,
                "priority_score": t.priority_score,
            }
            for t in available
        ]
    }

    with open(SCAN_RESULTS_PATH, 'w') as f:
        json.dump(scan_data, f, indent=2)

    console.print(f"Saved scan results to {SCAN_RESULTS_PATH}")

    # Show top priority talks
    console.print("\n[bold]Top 10 priority talks:[/bold]")
    for t in available[:10]:
        badge = "🔷" if t.is_algolia_speaker else "  "
        console.print(f"  {badge} {t.view_count:>6,} views | {t.speaker[:20]:20} | {t.title[:40]}...")

    return available


def enrich_talks(client: SearchClientSync, limit: Optional[int] = None, batch_size: int = 50):
    """Enrich talks with transcripts and summaries."""
    console.print("\n[bold]STAGE 2: Enriching talks...[/bold]")

    # Load scan results
    if not SCAN_RESULTS_PATH.exists():
        console.print("[red]No scan results found. Run --scan first.[/red]")
        return

    with open(SCAN_RESULTS_PATH) as f:
        scan_data = json.load(f)

    talks = scan_data.get("talks", [])
    if limit:
        talks = talks[:limit]

    console.print(f"Processing {len(talks)} talks (priority-ranked)")

    updates = []
    stats = {"success": 0, "no_transcript": 0, "error": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Enriching...", total=len(talks))

        for i, talk in enumerate(talks):
            video_id = get_video_id(talk["object_id"])

            # Fetch transcript
            transcript = fetch_transcript(video_id)

            if not transcript:
                stats["no_transcript"] += 1
                progress.advance(task)
                continue

            # Summarize
            enrichment = summarize_with_minimax(
                transcript,
                talk["title"],
                talk["speaker"]
            )

            if enrichment:
                update = {
                    "objectID": talk["object_id"],
                    "transcript_text": transcript[:10000],
                    "transcript_summary": enrichment.get("summary", ""),
                    "transcript_keywords": enrichment.get("keywords", []),
                    "transcript_topics": enrichment.get("topics", []),
                    "transcript_takeaways": enrichment.get("key_takeaways", []),
                    "transcript_enriched": True,
                }
                updates.append(update)
                stats["success"] += 1

                # Batch update every N talks
                if len(updates) >= batch_size:
                    client.partial_update_objects("cfps_talks", updates)
                    console.print(f"\n  [green]Indexed batch of {len(updates)} talks[/green]")
                    updates = []
            else:
                stats["error"] += 1

            progress.advance(task)
            time.sleep(0.5)  # Rate limit

    # Final batch
    if updates:
        client.partial_update_objects("cfps_talks", updates)
        console.print(f"\n  [green]Indexed final batch of {len(updates)} talks[/green]")

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]ENRICHMENT COMPLETE[/bold]")
    console.print(f"  Success:       {stats['success']}")
    console.print(f"  No transcript: {stats['no_transcript']}")
    console.print(f"  Errors:        {stats['error']}")

    # Update scan file to remove processed talks
    remaining = [t for t in scan_data["talks"] if t["object_id"] not in {u["objectID"] for u in updates}]
    scan_data["talks"] = remaining
    scan_data["last_enriched"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(SCAN_RESULTS_PATH, 'w') as f:
        json.dump(scan_data, f, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Smart transcript enrichment pipeline")
    parser.add_argument("--scan", action="store_true", help="Scan talks for transcript availability")
    parser.add_argument("--enrich", action="store_true", help="Enrich talks with transcripts")
    parser.add_argument("--all", action="store_true", help="Run full pipeline (scan + enrich)")
    parser.add_argument("--limit", type=int, help="Limit number of talks to enrich")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for Algolia updates")

    args = parser.parse_args()

    client = SearchClientSync(APP_ID, API_KEY)

    if args.all or args.scan:
        scan_all_talks(client)

    if args.all or args.enrich:
        enrich_talks(client, limit=args.limit, batch_size=args.batch_size)

    if not (args.scan or args.enrich or args.all):
        parser.print_help()


if __name__ == "__main__":
    main()
