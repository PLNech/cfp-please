#!/usr/bin/env python3
"""Discover potential Algolia employees via Gravatar heuristic.

Checks if firstname.lastname@algolia.com has a Gravatar.
If so, they're likely an Algolian we should add to algolia_speakers.json.
"""
import hashlib
import json
import os
import requests
from pathlib import Path

# Load env
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

from algoliasearch.search.client import SearchClientSync

APP_ID = os.environ['ALGOLIA_APP_ID']
API_KEY = os.environ['ALGOLIA_API_KEY']


def check_gravatar(email: str) -> bool:
    """Check if email has a Gravatar."""
    email_hash = hashlib.md5(email.encode('utf-8').lower()).hexdigest()
    url = f"https://gravatar.com/avatar/{email_hash}?d=404"
    try:
        resp = requests.head(url, timeout=5)
        return resp.status_code == 200
    except:
        return False


def get_email_variations(first_name: str, last_name: str) -> list[str]:
    """Generate email variations for a name."""
    first = first_name.lower().replace("-", "")
    last = last_name.lower().replace("-", "")
    
    variations = [
        f"{first}.{last}@algolia.com",           # sarah.dayan
        f"{first}{last}@algolia.com",             # sarahdayan
        f"{first[0]}{last}@algolia.com",          # sdayan
        f"{first[0]}.{last}@algolia.com",         # s.dayan
    ]
    
    # For hyphenated first names like "Paul-Louis"
    if "-" in first_name:
        parts = first_name.lower().split("-")
        initials = "".join(p[0] for p in parts)
        variations.extend([
            f"{initials}@algolia.com",            # pln
            f"{''.join(parts)}.{last}@algolia.com",  # paullouis.nech
        ])
    
    return variations


def main():
    print("=" * 70)
    print("DISCOVERING ALGOLIA SPEAKERS VIA GRAVATAR")
    print("=" * 70)
    
    client = SearchClientSync(APP_ID, API_KEY)
    
    # Load existing Algolia speakers
    speakers_path = Path(__file__).parent.parent.parent / "data" / "algolia_speakers.json"
    with open(speakers_path) as f:
        data = json.load(f)
    
    known_names = {s["name"].lower() for s in data["speakers"]}
    print(f"Known Algolia speakers: {len(known_names)}")
    
    # Get all speakers from index
    result = client.search_single_index("cfps_speakers", {
        "query": "",
        "filters": "is_algolia_speaker:false",
        "hitsPerPage": 1000,
        "attributesToRetrieve": ["objectID", "name", "talk_count", "total_views"]
    })
    
    print(f"Non-Algolia speakers to check: {result.nb_hits}")
    print()
    
    discoveries = []
    
    for hit in result.hits:
        h = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
        name = h["name"]
        
        # Skip if already known
        if name.lower() in known_names:
            continue
        
        # Parse name into first/last
        parts = name.split()
        if len(parts) < 2:
            continue
        
        first_name = parts[0]
        last_name = parts[-1]
        
        # Try email variations
        for email in get_email_variations(first_name, last_name):
            if check_gravatar(email):
                print(f"✓ FOUND: {name} ({email})")
                discoveries.append({
                    "name": name,
                    "objectID": h["objectID"],
                    "email": email,
                    "talk_count": h.get("talk_count", 0),
                    "total_views": h.get("total_views", 0),
                })
                break
    
    print()
    print("=" * 70)
    print(f"DISCOVERED {len(discoveries)} POTENTIAL ALGOLIA SPEAKERS")
    print("=" * 70)
    
    for d in discoveries:
        print(f"  {d['name']:25} | {d['talk_count']} talks | {d['total_views']:,} views")
        print(f"    → {d['email']}")
    
    if discoveries:
        # Save discoveries
        output_path = Path(__file__).parent.parent.parent / "data" / "gravatar_discoveries.json"
        with open(output_path, 'w') as f:
            json.dump(discoveries, f, indent=2)
        print(f"\nSaved to: {output_path}")
        print("Review and add to algolia_speakers.json manually.")


if __name__ == "__main__":
    main()
