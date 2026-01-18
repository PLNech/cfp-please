#!/usr/bin/env python3
"""Research YouTube for missing Algolia DevCon talks.

This script:
1. Loads Algolia speakers data with known talks
2. Searches YouTube for DevCon playlists and individual talks
3. Outputs found videos for manual verification before indexing
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Load env
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

# DevCon YouTube playlists (from research)
DEVCON_PLAYLISTS = {
    "DevCon 2022": "PLuHdbqhRgWHLRlmvQ1OKLdjslSxXrAAjk",
    "DevCon 2023": "PLuHdbqhRgWHKQpmwZWPxVxE36Awb8FE1r",
    # DevCon 2024 and 2025 - need to find playlists
}

# Known DevCon talk searches
DEVCON_SEARCHES = [
    '"Algolia DevCon" 2022',
    '"Algolia DevCon" 2023',
    '"Algolia DevCon" 2024',
    'site:youtube.com "algolia" "devcon"',
]

# Algolia speakers to search for
PRIORITY_SPEAKERS = [
    "Sarah Dayan",
    "Paul-Louis Nech",
    "Haroen Viaene",
    "Dustin Coates",
    "Raed Chammam",
    "François Chalifour",
    "Lucas Bonomi",
]


def run_ytdlp(args: list[str], timeout: int = 60) -> dict:
    """Run yt-dlp with JSON output."""
    # Use poetry run to ensure yt-dlp is found
    cmd = ["poetry", "run", "yt-dlp", "--dump-json", "--flat-playlist"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return {"error": result.stderr}

        # Parse JSON lines
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    videos.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return {"videos": videos}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def search_youtube(query: str, max_results: int = 20) -> list[dict]:
    """Search YouTube for videos matching query."""
    print(f"  Searching: {query}")
    result = run_ytdlp([f"ytsearch{max_results}:{query}"])

    if "error" in result:
        print(f"    Error: {result['error']}")
        return []

    videos = result.get("videos", [])
    print(f"    Found {len(videos)} videos")
    return videos


def get_playlist_videos(playlist_id: str) -> list[dict]:
    """Get all videos from a YouTube playlist."""
    print(f"  Fetching playlist: {playlist_id}")
    result = run_ytdlp([f"https://www.youtube.com/playlist?list={playlist_id}"], timeout=120)

    if "error" in result:
        print(f"    Error: {result['error']}")
        return []

    videos = result.get("videos", [])
    print(f"    Found {len(videos)} videos")
    return videos


def extract_speaker(title: str) -> str | None:
    """Try to extract speaker name from video title."""
    # Common patterns:
    # "Talk Title - Speaker Name"
    # "Speaker Name: Talk Title"
    # "Talk Title by Speaker Name"
    # "Talk Title | Speaker Name"

    separators = [' - ', ' | ', ' by ', ': ']
    for sep in separators:
        if sep in title:
            parts = title.split(sep)
            # Speaker is usually the shorter part
            for part in parts:
                part = part.strip()
                # Likely a name if 2-4 words, each capitalized
                words = part.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                    return part
    return None


def main():
    print("=" * 70)
    print("RESEARCHING ALGOLIA DEVCON TALKS ON YOUTUBE")
    print("=" * 70)

    all_found = []

    # 1. Fetch from known playlists
    print("\n1. FETCHING FROM KNOWN PLAYLISTS")
    print("-" * 40)
    for name, playlist_id in DEVCON_PLAYLISTS.items():
        print(f"\n{name}:")
        videos = get_playlist_videos(playlist_id)
        for v in videos:
            v["source"] = f"playlist:{name}"
            v["year"] = int(name.split()[-1]) if name.split()[-1].isdigit() else None
        all_found.extend(videos)

    # 2. Search for DevCon talks
    print("\n2. SEARCHING FOR DEVCON TALKS")
    print("-" * 40)
    for query in DEVCON_SEARCHES:
        videos = search_youtube(query)
        for v in videos:
            v["source"] = f"search:{query}"
        all_found.extend(videos)

    # 3. Search for priority speakers + Algolia
    print("\n3. SEARCHING FOR PRIORITY SPEAKERS")
    print("-" * 40)
    for speaker in PRIORITY_SPEAKERS:
        query = f'"{speaker}" Algolia talk OR presentation OR conference'
        videos = search_youtube(query, max_results=10)
        for v in videos:
            v["source"] = f"speaker:{speaker}"
            v["detected_speaker"] = speaker
        all_found.extend(videos)

    # Dedupe by video ID
    seen_ids = set()
    unique_videos = []
    for v in all_found:
        vid = v.get("id") or v.get("url", "").split("v=")[-1].split("&")[0]
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            v["video_id"] = vid
            unique_videos.append(v)

    print("\n" + "=" * 70)
    print(f"FOUND {len(unique_videos)} UNIQUE VIDEOS")
    print("=" * 70)

    # Output results
    output_path = Path(__file__).parent.parent.parent / "data" / "devcon_youtube_research.json"
    output_path.parent.mkdir(exist_ok=True)

    output = {
        "metadata": {
            "total_found": len(unique_videos),
            "playlists_searched": list(DEVCON_PLAYLISTS.keys()),
            "searches_performed": DEVCON_SEARCHES + [f"speaker:{s}" for s in PRIORITY_SPEAKERS],
        },
        "videos": []
    }

    for v in unique_videos:
        video_data = {
            "video_id": v.get("video_id"),
            "title": v.get("title"),
            "url": v.get("url") or f"https://www.youtube.com/watch?v={v.get('video_id')}",
            "channel": v.get("channel") or v.get("uploader"),
            "duration": v.get("duration"),
            "view_count": v.get("view_count"),
            "source": v.get("source"),
            "detected_speaker": v.get("detected_speaker") or extract_speaker(v.get("title", "")),
            "year": v.get("year"),
        }
        output["videos"].append(video_data)
        print(f"\n[{video_data['video_id']}] {video_data['title'][:60]}...")
        print(f"   Speaker: {video_data['detected_speaker'] or 'Unknown'}")
        print(f"   Source: {video_data['source']}")

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n\nResults saved to: {output_path}")
    print("\nNext steps:")
    print("1. Review the JSON file for accuracy")
    print("2. Mark videos that are real DevCon talks")
    print("3. Run indexing script to add verified talks")


if __name__ == "__main__":
    main()
