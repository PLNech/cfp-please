#!/usr/bin/env python3
"""Audit description status in Algolia index."""

import os
from algoliasearch.search.client import SearchClientSync


def audit_descriptions():
    """Browse all records and count description status."""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")
    index_name = os.environ.get("ALGOLIA_INDEX_NAME", "cfps")

    if not app_id or not api_key:
        print("Error: ALGOLIA_APP_ID and ALGOLIA_API_KEY must be set")
        return

    client = SearchClientSync(app_id, api_key)

    # Browse all records
    has_desc = 0
    no_desc = 0
    has_topics = 0
    no_topics = 0
    enriched_count = 0
    total = 0

    print(f"Auditing index '{index_name}'...\n")

    # Use browse to get all records
    response = client.browse(
        index_name,
        browse_params={"attributesToRetrieve": ["name", "description", "topicsNormalized", "enriched"]},
    )

    def process_hit(hit):
        """Extract stats from a hit (handles both dict and Pydantic models)."""
        # Convert to dict if needed
        data = hit if isinstance(hit, dict) else hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
        desc = data.get("description", "")
        topics = data.get("topicsNormalized", [])
        enriched = data.get("enriched", False)
        return bool(desc and str(desc).strip()), bool(topics and len(topics) > 0), bool(enriched)

    for hit in response.hits:
        total += 1
        hd, ht, he = process_hit(hit)
        has_desc += hd
        no_desc += not hd
        has_topics += ht
        no_topics += not ht
        enriched_count += he

    # Handle pagination
    while response.cursor:
        response = client.browse(
            index_name,
            browse_params={
                "attributesToRetrieve": ["name", "description", "topicsNormalized", "enriched"],
                "cursor": response.cursor,
            },
        )
        for hit in response.hits:
            total += 1
            hd, ht, he = process_hit(hit)
            has_desc += hd
            no_desc += not hd
            has_topics += ht
            no_topics += not ht
            enriched_count += he

    print("=" * 50)
    print(f"Total records: {total}")
    print("=" * 50)
    print(f"\nDescriptions:")
    print(f"  ✓ Has description: {has_desc} ({has_desc/total*100:.1f}%)")
    print(f"  ✗ No description:  {no_desc} ({no_desc/total*100:.1f}%)")
    print(f"\nTopics (normalized):")
    print(f"  ✓ Has topics: {has_topics} ({has_topics/total*100:.1f}%)")
    print(f"  ✗ No topics:  {no_topics} ({no_topics/total*100:.1f}%)")
    print(f"\nEnriched flag:")
    print(f"  ✓ Enriched: {enriched_count} ({enriched_count/total*100:.1f}%)")
    print("=" * 50)


if __name__ == "__main__":
    audit_descriptions()
