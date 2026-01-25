#!/usr/bin/env python3
"""
Verify intel scraper outputs against live API responses.

Usage:
    poetry run python verify_intel.py "RustWeek 2026"
    poetry run python verify_intel.py "KubeCon" --all-sources

This helps catch:
- Stale cached data
- Query formulation issues
- API rate limits or errors
"""

import asyncio
import argparse
import json
from datetime import datetime

from enrichers.popularity import (
    fetch_hn_intel,
    fetch_github_intel,
    fetch_reddit_intel,
    fetch_devto_intel,
    _clean_name,
)


async def verify_source(name: str, source: str) -> dict:
    """Verify a single source and return comparison data."""
    clean = _clean_name(name)

    async with httpx.AsyncClient(timeout=15) as client:
        if source == "hn":
            return await fetch_hn_intel(client, name)
        elif source == "github":
            return await fetch_github_intel(client, name)
        elif source == "reddit":
            return await fetch_reddit_intel(client, name)
        elif source == "devto":
            return await fetch_devto_intel(client, name)


def format_number(n: int) -> str:
    """Format number with K suffix for readability."""
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


async def verify_all(name: str) -> dict:
    """Verify all sources and return full report."""
    results = {}

    sources = [
        ("HN", "hn"),
        ("GitHub", "github"),
        ("Reddit", "reddit"),
        ("DEV.to", "devto"),
    ]

    for label, source in sources:
        try:
            result = await verify_source(name, source)
            results[source] = {
                "success": True,
                # Show FILTERED count (noise-filtered results), not raw API count
                "total": len(result.get(f"{source[:-1] if source != 'devto' else source}_titles", [])) if "error" not in result else 0,
                "raw_total": result.get(f"total_{source[:-1] + '_s' if source == 'devto' else source}s", 0) if "error" not in result else 0,
                "error": result.get("error"),
                "titles": result.get(f"{source[:-1] if source != 'devto' else source}_titles", [])[:3] if "error" not in result else [],
            }
        except Exception as e:
            results[source] = {"success": False, "error": str(e)}

    return results


def print_report(name: str, results: dict):
    """Print a formatted verification report."""
    clean = _clean_name(name)
    print(f"\n{'='*60}")
    print(f"Intel Verification Report")
    print(f"{'='*60}")
    print(f"Conference: {name}")
    print(f"Cleaned name: {clean}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    sources = [
        ("HN", "hn", "Stories"),
        ("GitHub", "github", "Repos"),
        ("Reddit", "reddit", "Posts"),
        ("DEV.to", "devto", "Articles"),
    ]

    all_valid = True

    for label, source, noun in sources:
        data = results.get(source, {})
        error = data.get("error")

        if error:
            print(f"❌ {label}: ERROR - {error}")
            all_valid = False
        elif data.get("total", 0) == 0:
            print(f"⚠️  {label}: 0 {noun} (might be fine)")
        else:
            print(f"✅ {label}: {format_number(data.get('total', 0))} {noun}")
            titles = data.get("titles", [])
            if titles:
                print(f"   Sample: \"{titles[0][:50]}{'...' if len(titles[0]) > 50 else ''}\"")

    print()
    print("="*60)
    if all_valid:
        print("✓ All sources returned valid results")
    else:
        print("✗ Some sources had errors - check before indexing!")
    print("="*60)

    return all_valid


async def main():
    parser = argparse.ArgumentParser(description="Verify intel scraper outputs")
    parser.add_argument("name", nargs="?", help="Conference name to verify")
    parser.add_argument("--source", choices=["hn", "github", "reddit", "devto"],
                        help="Specific source to verify")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.name:
        parser.print_help()
        return

    if args.source:
        result = await verify_source(args.name, args.source)
        print(json.dumps(result, indent=2, default=str))
    else:
        results = await verify_all(args.name)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            all_valid = print_report(args.name, results)
            exit(0 if all_valid else 1)


if __name__ == "__main__":
    import httpx
    asyncio.run(main())