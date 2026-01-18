#!/usr/bin/env python3
"""Enrich talks with YouTube transcripts, AI summaries, and keywords.

Pipeline:
1. Fetch transcript from YouTube (via yt-dlp for reliability)
2. Summarize transcript with MiniMax M2.1
3. Extract keywords/topics from content
4. Update talks index with enriched data
"""
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console

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

# Algolia Enablers API endpoint
ENABLERS_URL = "https://inference.api.enablers.algolia.net/v1/chat/completions"
MODEL = "minimax-m2.1"


def get_video_id(object_id: str) -> Optional[str]:
    """Extract YouTube video ID from objectID."""
    if object_id.startswith("yt_"):
        return object_id[3:]
    return None


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript from YouTube using yt-dlp.

    Uses json3 subtitle format which contains the raw ASR text.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "sub"

        try:
            # Fetch auto-generated English subtitles
            cmd = [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--sub-format", "json3",
                "--skip-download",
                "--no-warnings",
                "-o", str(output_path),
                url
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Find the downloaded subtitle file
            sub_file = output_path.with_suffix(".en.json3")
            if not sub_file.exists():
                console.print(f"  [dim]No English subtitles available[/dim]")
                return None

            # Parse json3 format
            with open(sub_file) as f:
                data = json.load(f)

            # Extract text from events
            text_parts = []
            for event in data.get("events", []):
                for seg in event.get("segs", []):
                    text = seg.get("utf8", "")
                    if text and text.strip() and text not in ["[Music]", "[Applause]"]:
                        text_parts.append(text.strip())

            if not text_parts:
                console.print(f"  [dim]Empty transcript[/dim]")
                return None

            # Combine and clean
            full_text = " ".join(text_parts)
            full_text = re.sub(r'\s+', ' ', full_text).strip()

            return full_text

        except subprocess.TimeoutExpired:
            console.print(f"  [dim]Timeout fetching transcript[/dim]")
            return None
        except Exception as e:
            console.print(f"  [red]Error fetching transcript: {e}[/red]")
            return None


def summarize_with_minimax(
    transcript: str,
    title: str,
    speaker: str,
    max_length: int = 4000
) -> dict:
    """Summarize transcript and extract keywords using MiniMax.

    Returns:
        {
            "summary": "2-3 sentence summary",
            "keywords": ["keyword1", "keyword2", ...],
            "topics": ["topic1", "topic2", ...],
            "key_takeaways": ["takeaway1", "takeaway2", ...]
        }
    """
    # Truncate transcript if too long
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

    try:
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

        with httpx.Client(timeout=90.0) as client:
            response = client.post(ENABLERS_URL, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON from response
            # Find JSON block if wrapped in markdown
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                return result

    except Exception as e:
        console.print(f"  [red]MiniMax error: {e}[/red]")

    return {}


def main(limit: int = 50, skip_existing: bool = True):
    """Enrich talks with transcripts and AI summaries."""
    console.print("[bold]TRANSCRIPT ENRICHMENT PIPELINE[/bold]")
    console.print("=" * 60)

    client = SearchClientSync(APP_ID, API_KEY)

    # Browse talks that need enrichment
    talks_to_process = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=[
            "objectID", "title", "speaker", "transcript_enriched"
        ],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            obj_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)

            # Skip non-YouTube talks
            if not obj_id or not obj_id.startswith("yt_"):
                continue

            # Skip already enriched if requested
            if skip_existing and getattr(hit, "transcript_enriched", False):
                continue

            talks_to_process.append({
                "objectID": obj_id,
                "title": getattr(hit, "title", ""),
                "speaker": getattr(hit, "speaker", ""),
            })

    client.browse_objects("cfps_talks", aggregator, browse_params)

    console.print(f"Found {len(talks_to_process)} talks to process")

    if limit:
        talks_to_process = talks_to_process[:limit]
        console.print(f"Processing first {limit} talks")

    # Process talks
    updates = []
    stats = {"success": 0, "no_transcript": 0, "error": 0}

    for i, talk in enumerate(talks_to_process):
        obj_id = talk["objectID"]
        video_id = get_video_id(obj_id)

        console.print(f"\n[{i+1}/{len(talks_to_process)}] {talk['title'][:50]}...")

        # Fetch transcript
        transcript = fetch_transcript(video_id)

        if not transcript:
            stats["no_transcript"] += 1
            continue

        console.print(f"  [green]Got transcript ({len(transcript)} chars)[/green]")

        # Summarize with MiniMax
        enrichment = summarize_with_minimax(
            transcript,
            talk["title"],
            talk["speaker"]
        )

        if enrichment:
            update = {
                "objectID": obj_id,
                "transcript_text": transcript[:10000],  # Store first 10K chars
                "transcript_summary": enrichment.get("summary", ""),
                "transcript_keywords": enrichment.get("keywords", []),
                "transcript_topics": enrichment.get("topics", []),
                "transcript_takeaways": enrichment.get("key_takeaways", []),
                "transcript_enriched": True,
            }
            updates.append(update)
            stats["success"] += 1

            console.print(f"  [cyan]Summary: {enrichment.get('summary', '')[:80]}...[/cyan]")
            console.print(f"  [dim]Keywords: {', '.join(enrichment.get('keywords', [])[:5])}[/dim]")
        else:
            stats["error"] += 1

        # Rate limit
        time.sleep(1)

    # Batch update Algolia
    if updates:
        console.print(f"\n[bold]Updating {len(updates)} talks in Algolia...[/bold]")

        batch_size = 50
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            client.partial_update_objects("cfps_talks", batch)
            console.print(f"  Updated {i + len(batch)}/{len(updates)}")

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]ENRICHMENT COMPLETE[/bold]")
    console.print(f"  Success: {stats['success']}")
    console.print(f"  No transcript: {stats['no_transcript']}")
    console.print(f"  Errors: {stats['error']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrich talks with transcripts")
    parser.add_argument("--limit", type=int, default=50, help="Max talks to process")
    parser.add_argument("--all", action="store_true", help="Process all talks (ignore limit)")
    parser.add_argument("--force", action="store_true", help="Re-process already enriched talks")

    args = parser.parse_args()

    main(
        limit=None if args.all else args.limit,
        skip_existing=not args.force
    )
