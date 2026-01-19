#!/usr/bin/env python3
"""Enrich talks with YouTube transcripts via parallel focused extractions.

Pipeline:
1. Fetch transcript from YouTube (via yt-dlp)
2. Parallel LLM calls for deep extraction:
   - Summary (2-3 sentences)
   - Keywords (20 technical terms)
   - Topics (5-10 themes)
   - Bangers (4-10 quotable punchlines)
3. Merge results and update Algolia
"""
import asyncio
import json
import os
import re
import subprocess
import tempfile
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

ENABLERS_URL = "https://inference.api.enablers.algolia.net/v1/chat/completions"
MODEL = "minimax-m2.1"


def get_video_id(object_id: str) -> Optional[str]:
    """Extract YouTube video ID from objectID."""
    if object_id.startswith("yt_"):
        return object_id[3:]
    return None


def fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript from YouTube using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"

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
                "-o", str(output_path),
                url
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            sub_file = output_path.with_suffix(".en.json3")
            if not sub_file.exists():
                return None

            with open(sub_file) as f:
                data = json.load(f)

            text_parts = []
            for event in data.get("events", []):
                for seg in event.get("segs", []):
                    text = seg.get("utf8", "")
                    if text and text.strip() and text not in ["[Music]", "[Applause]"]:
                        text_parts.append(text.strip())

            if not text_parts:
                return None

            full_text = " ".join(text_parts)
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            return full_text

        except Exception:
            return None


# ============ PARALLEL EXTRACTION PROMPTS ============

PROMPT_SUMMARY = """Analyze this conference talk transcript and write a compelling 2-3 sentence summary.
Focus on: What problem does it solve? What's the key insight? Who should watch this?

Talk: "{title}" by {speaker}

Transcript (excerpt):
{transcript}

Respond with ONLY the summary text, no JSON or formatting."""

PROMPT_KEYWORDS = """Extract exactly 20 technical keywords from this conference talk transcript.
Include: technologies, frameworks, concepts, methodologies, tools mentioned.
Be specific (e.g., "React Server Components" not just "React").

Talk: "{title}" by {speaker}

Transcript (excerpt):
{transcript}

Respond with a JSON array of 20 keywords:
["keyword1", "keyword2", ...]"""

PROMPT_TOPICS = """Identify 5-10 main topics/themes from this conference talk.
These should be broader categories that describe what the talk covers.
Examples: "Performance Optimization", "Developer Experience", "Testing Strategies", "System Design"

Talk: "{title}" by {speaker}

Transcript (excerpt):
{transcript}

Respond with a JSON array of 5-10 topics:
["topic1", "topic2", ...]"""

PROMPT_BANGERS = """Extract 4-10 "bangers" from this conference talk - the most quotable, memorable, impactful one-liners.

Look for:
- Provocative statements that challenge conventional wisdom
- Memorable insights that could be tweeted
- Funny or witty observations
- Powerful conclusions or realizations
- Wisdom that stands alone without context

Talk: "{title}" by {speaker}

Transcript (excerpt):
{transcript}

Respond with a JSON array of 4-10 quotable lines (exact or near-exact quotes from the talk):
["quote1", "quote2", ...]"""


async def call_llm(client: httpx.AsyncClient, prompt: str) -> str:
    """Make async LLM call."""
    headers = {
        "Authorization": f"Bearer {ENABLERS_JWT}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    try:
        response = await client.post(ENABLERS_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        console.print(f"  [red]LLM error: {e}[/red]")
        return ""


def parse_json_array(text: str) -> list:
    """Extract JSON array from LLM response."""
    try:
        # Find array in response
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return json.loads(match.group())
    except:
        pass
    return []


async def extract_all(transcript: str, title: str, speaker: str) -> dict:
    """Run all extractions in parallel."""
    # Truncate for prompts (keep reasonable context)
    excerpt = transcript[:6000] if len(transcript) > 6000 else transcript

    async with httpx.AsyncClient(timeout=90.0) as client:
        # Prepare prompts
        prompts = {
            "summary": PROMPT_SUMMARY.format(title=title, speaker=speaker or "Unknown", transcript=excerpt),
            "keywords": PROMPT_KEYWORDS.format(title=title, speaker=speaker or "Unknown", transcript=excerpt),
            "topics": PROMPT_TOPICS.format(title=title, speaker=speaker or "Unknown", transcript=excerpt),
            "bangers": PROMPT_BANGERS.format(title=title, speaker=speaker or "Unknown", transcript=excerpt),
        }

        # Run all in parallel
        tasks = {key: call_llm(client, prompt) for key, prompt in prompts.items()}
        results = await asyncio.gather(*tasks.values())

        # Map results back
        result_map = dict(zip(tasks.keys(), results))

        return {
            "summary": result_map["summary"].strip(),
            "keywords": parse_json_array(result_map["keywords"])[:20],
            "topics": parse_json_array(result_map["topics"])[:10],
            "bangers": parse_json_array(result_map["bangers"])[:10],
        }


def main(limit: int = 50, skip_existing: bool = True):
    """Enrich talks with transcripts via parallel extraction."""
    console.print("[bold]TRANSCRIPT ENRICHMENT (Parallel Extraction)[/bold]")
    console.print("=" * 60)

    client = SearchClientSync(APP_ID, API_KEY)

    # Browse talks needing enrichment
    talks_to_process = []

    browse_params = BrowseParamsObject(
        attributes_to_retrieve=["objectID", "title", "speaker", "transcript_enriched"],
        hits_per_page=1000,
    )

    def aggregator(response):
        for hit in response.hits:
            obj_id = getattr(hit, "object_id", None) or getattr(hit, "objectID", None)
            if not obj_id or not obj_id.startswith("yt_"):
                continue
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
        console.print(f"Processing first {limit}")

    updates = []
    stats = {"success": 0, "no_transcript": 0, "error": 0}

    for i, talk in enumerate(talks_to_process):
        obj_id = talk["objectID"]
        video_id = get_video_id(obj_id)

        console.print(f"\n[{i+1}/{len(talks_to_process)}] {talk['title'][:50]}...")

        # Fetch transcript
        transcript = fetch_transcript(video_id)
        if not transcript:
            console.print(f"  [dim]No transcript[/dim]")
            stats["no_transcript"] += 1
            continue

        console.print(f"  [green]Transcript: {len(transcript)} chars[/green]")

        # Parallel extraction
        try:
            enrichment = asyncio.run(extract_all(transcript, talk["title"], talk["speaker"]))
        except Exception as e:
            console.print(f"  [red]Extraction error: {e}[/red]")
            stats["error"] += 1
            continue

        if enrichment.get("summary"):
            update = {
                "objectID": obj_id,
                "transcript_summary": enrichment["summary"],
                "transcript_keywords": enrichment["keywords"],
                "transcript_topics": enrichment["topics"],
                "transcript_bangers": enrichment["bangers"],
                "transcript_enriched": True,
            }
            updates.append(update)
            stats["success"] += 1

            console.print(f"  [cyan]Summary: {enrichment['summary'][:70]}...[/cyan]")
            console.print(f"  [dim]Keywords: {len(enrichment['keywords'])} | Topics: {len(enrichment['topics'])} | Bangers: {len(enrichment['bangers'])}[/dim]")
            if enrichment["bangers"]:
                console.print(f"  [yellow]💥 \"{enrichment['bangers'][0][:60]}...\"[/yellow]")
        else:
            stats["error"] += 1

    # Batch update Algolia
    if updates:
        console.print(f"\n[bold]Updating {len(updates)} talks...[/bold]")
        batch_size = 50
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            client.partial_update_objects("cfps_talks", batch)
            console.print(f"  {i + len(batch)}/{len(updates)}")

    console.print("\n" + "=" * 60)
    console.print(f"[bold]Done![/bold] Success: {stats['success']} | No transcript: {stats['no_transcript']} | Errors: {stats['error']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    main(limit=None if args.all else args.limit, skip_existing=not args.force)
