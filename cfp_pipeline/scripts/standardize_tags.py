#!/usr/bin/env python3
"""Tag standardization for transcript enrichment.

Groups similar keywords/topics and normalizes them for consistency.
Can run in parallel with enrichment pipeline.

Usage:
    poetry run python cfp_pipeline/scripts/standardize_tags.py --analyze  # Show tag clusters
    poetry run python cfp_pipeline/scripts/standardize_tags.py --apply    # Apply standardization
"""
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

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

# Canonical tag mappings - normalize variations to standard forms
CANONICAL_TAGS = {
    # TDD variations
    'test-driven development': 'Test-Driven Development (TDD)',
    'test driven development': 'Test-Driven Development (TDD)',
    'tdd': 'Test-Driven Development (TDD)',
    'test-driven development (tdd)': 'Test-Driven Development (TDD)',

    # AI variations
    'artificial intelligence': 'Artificial Intelligence (AI)',
    'ai': 'Artificial Intelligence (AI)',
    'a.i.': 'Artificial Intelligence (AI)',
    'machine learning': 'Machine Learning (ML)',
    'ml': 'Machine Learning (ML)',
    'llm': 'Large Language Models (LLM)',
    'llms': 'Large Language Models (LLM)',
    'large language model': 'Large Language Models (LLM)',
    'large language models': 'Large Language Models (LLM)',
    'generative ai': 'Generative AI',
    'gen ai': 'Generative AI',
    'genai': 'Generative AI',

    # DevOps variations
    'ci/cd': 'CI/CD',
    'ci cd': 'CI/CD',
    'continuous integration': 'CI/CD',
    'continuous delivery': 'CI/CD',
    'devops': 'DevOps',
    'dev ops': 'DevOps',
    'kubernetes': 'Kubernetes',
    'k8s': 'Kubernetes',
    'docker': 'Docker',
    'containerization': 'Containers',
    'containers': 'Containers',

    # Cloud variations
    'amazon web services': 'AWS',
    'aws': 'AWS',
    'google cloud': 'Google Cloud Platform (GCP)',
    'google cloud platform': 'Google Cloud Platform (GCP)',
    'gcp': 'Google Cloud Platform (GCP)',
    'microsoft azure': 'Azure',
    'azure': 'Azure',

    # JS framework variations
    'react.js': 'React',
    'reactjs': 'React',
    'react js': 'React',
    'vue.js': 'Vue.js',
    'vuejs': 'Vue.js',
    'vue js': 'Vue.js',
    'vue': 'Vue.js',
    'next.js': 'Next.js',
    'nextjs': 'Next.js',
    'angular.js': 'Angular',
    'angularjs': 'Angular',
    'node.js': 'Node.js',
    'nodejs': 'Node.js',
    'node js': 'Node.js',
    'typescript': 'TypeScript',
    'ts': 'TypeScript',
    'javascript': 'JavaScript',
    'js': 'JavaScript',

    # API variations
    'rest api': 'REST API',
    'restful api': 'REST API',
    'restful': 'REST API',
    'graphql': 'GraphQL',
    'graph ql': 'GraphQL',
    'api design': 'API Design',
    'api development': 'API Development',

    # Testing variations
    'unit testing': 'Unit Testing',
    'integration testing': 'Integration Testing',
    'end-to-end testing': 'E2E Testing',
    'e2e testing': 'E2E Testing',
    'e2e': 'E2E Testing',

    # Architecture patterns
    'microservices': 'Microservices',
    'micro services': 'Microservices',
    'microservice': 'Microservices',
    'serverless': 'Serverless',
    'server-less': 'Serverless',

    # Search variations
    'algolia': 'Algolia',
    'elasticsearch': 'Elasticsearch',
    'elastic search': 'Elasticsearch',
    'full-text search': 'Full-Text Search',
    'search': 'Search',

    # Database variations
    'postgresql': 'PostgreSQL',
    'postgres': 'PostgreSQL',
    'mysql': 'MySQL',
    'mongodb': 'MongoDB',
    'mongo': 'MongoDB',
    'redis': 'Redis',
    'sql': 'SQL',
    'nosql': 'NoSQL',
    'no-sql': 'NoSQL',
}


def normalize_tag(tag: str) -> str:
    """Normalize a tag to its canonical form."""
    # Lowercase for lookup
    tag_lower = tag.lower().strip()

    # Direct match
    if tag_lower in CANONICAL_TAGS:
        return CANONICAL_TAGS[tag_lower]

    # Return original with title case if no match
    return tag.strip()


def collect_all_tags(client: SearchClientSync) -> dict[str, int]:
    """Collect all transcript keywords and their frequencies."""
    tag_counts: dict[str, int] = defaultdict(int)

    def aggregator(response):
        for hit in response.hits:
            h = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
            keywords = h.get('transcript_keywords') or []
            topics = h.get('transcript_topics') or []

            for tag in keywords + topics:
                tag_counts[tag] += 1

    client.browse_objects('cfps_talks', aggregator, BrowseParamsObject(
        attributes_to_retrieve=['transcript_keywords', 'transcript_topics'],
        filters='transcript_enriched:true',
        hits_per_page=1000,
    ))

    return dict(tag_counts)


def find_similar_tags(tags: dict[str, int]) -> dict[str, list[str]]:
    """Group tags that would normalize to the same canonical form."""
    groups: dict[str, list[str]] = defaultdict(list)

    for tag in tags:
        canonical = normalize_tag(tag)
        groups[canonical].append(tag)

    # Only return groups with multiple variants
    return {k: v for k, v in groups.items() if len(v) > 1}


def analyze_tags(client: SearchClientSync):
    """Analyze tag distribution and show clusters."""
    console.print("[bold]Analyzing transcript tags...[/bold]")

    tag_counts = collect_all_tags(client)
    console.print(f"Found [green]{len(tag_counts)}[/green] unique tags")

    # Find similar tags
    similar = find_similar_tags(tag_counts)

    if similar:
        console.print(f"\n[bold yellow]Found {len(similar)} tag clusters to standardize:[/bold yellow]")

        table = Table(title="Tag Clusters")
        table.add_column("Canonical", style="green")
        table.add_column("Variations", style="cyan")
        table.add_column("Total Count", justify="right")

        for canonical, variants in sorted(similar.items(), key=lambda x: -sum(tag_counts.get(v, 0) for v in x[1])):
            total = sum(tag_counts.get(v, 0) for v in variants)
            variants_str = ", ".join(f"{v} ({tag_counts.get(v, 0)})" for v in variants[:5])
            if len(variants) > 5:
                variants_str += f" +{len(variants)-5} more"
            table.add_row(canonical, variants_str, str(total))

        console.print(table)
    else:
        console.print("[green]No tag variations found - tags are already standardized![/green]")

    # Show top tags
    console.print("\n[bold]Top 20 Tags:[/bold]")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:20]:
        console.print(f"  {count:>4} | {tag}")


def standardize_tags(client: SearchClientSync, dry_run: bool = False):
    """Apply tag standardization to all enriched talks."""
    console.print("[bold]Standardizing transcript tags...[/bold]")

    updates = []
    stats = {"updated": 0, "unchanged": 0}

    def processor(response):
        for hit in response.hits:
            h = hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit)
            obj_id = h.get('objectID')

            keywords = h.get('transcript_keywords') or []
            topics = h.get('transcript_topics') or []

            # Normalize
            new_keywords = list(dict.fromkeys(normalize_tag(k) for k in keywords))  # dedupe
            new_topics = list(dict.fromkeys(normalize_tag(t) for t in topics))

            # Check if changed
            if new_keywords != keywords or new_topics != topics:
                updates.append({
                    'objectID': obj_id,
                    'transcript_keywords': new_keywords,
                    'transcript_topics': new_topics,
                })
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1

    client.browse_objects('cfps_talks', processor, BrowseParamsObject(
        attributes_to_retrieve=['objectID', 'transcript_keywords', 'transcript_topics'],
        filters='transcript_enriched:true',
        hits_per_page=1000,
    ))

    console.print(f"Records to update: [yellow]{stats['updated']}[/yellow]")
    console.print(f"Records unchanged: [green]{stats['unchanged']}[/green]")

    if updates and not dry_run:
        # Batch update
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            client.partial_update_objects('cfps_talks', batch)
            console.print(f"  Updated batch {i//batch_size + 1}/{(len(updates)-1)//batch_size + 1}")

        console.print(f"[green]✓ Standardized {stats['updated']} records[/green]")
    elif dry_run:
        console.print("[yellow]Dry run - no changes applied[/yellow]")
        if updates:
            console.print("\nSample changes:")
            for u in updates[:3]:
                console.print(f"  {u['objectID']}: {u['transcript_keywords'][:3]}...")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Standardize transcript tags")
    parser.add_argument("--analyze", action="store_true", help="Analyze tag distribution")
    parser.add_argument("--apply", action="store_true", help="Apply standardization")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without applying")

    args = parser.parse_args()

    client = SearchClientSync(APP_ID, API_KEY)

    if args.analyze or not (args.apply or args.dry_run):
        analyze_tags(client)

    if args.apply:
        standardize_tags(client, dry_run=False)
    elif args.dry_run:
        standardize_tags(client, dry_run=True)


if __name__ == "__main__":
    main()
