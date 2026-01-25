#!/usr/bin/env python3
"""
Audit cfps_intel_github index accuracy.

Evaluates:
1. Whether repos are official conference repos
2. Related projects vs noise
3. Star distribution and quality signals
"""

import os
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

from algoliasearch.search.client import SearchClientSync


@dataclass
class RepoAssessment:
    """Assessment of a single repo's relevance."""
    repo_name: str
    url: str
    stars: int
    category: str  # "official", "related", "noise"
    reason: str


@dataclass
class ConferenceAssessment:
    """Assessment of a conference's GitHub intel quality."""
    cfp_name: str
    total_repos: int
    total_stars: int
    repos: list
    official_count: int = 0
    related_count: int = 0
    noise_count: int = 0
    quality_score: float = 0.0


def classify_repo(conf_name: str, repo: dict) -> RepoAssessment:
    """
    Classify a repo as official/related/noise based on heuristics.

    Official: Conference org repo, official website, schedule apps
    Related: Talks, demos, workshop code from conference
    Noise: Random projects that happen to mention conference name
    """
    repo_name = repo.get("name", "").lower()
    full_name = repo.get("full_name", "").lower()
    description = (repo.get("description") or "").lower()
    url = repo.get("url", "")
    stars = repo.get("stars", 0)
    topics = [t.lower() for t in repo.get("topics", [])]

    # Normalize conference name for matching
    conf_lower = conf_name.lower()
    conf_parts = set(conf_lower.replace("-", " ").replace("_", " ").split())
    # Remove common words and years
    conf_parts -= {"2024", "2025", "2026", "the", "conference", "conf", "day", "days"}

    # Keywords that suggest official/org repos
    official_keywords = ["official", "website", "schedule", "app", "cfp", "call-for-papers"]

    # Keywords that suggest related talks/demos
    related_keywords = ["talk", "demo", "workshop", "presentation", "slides", "sample", "example"]

    # Keywords that suggest noise
    noise_keywords = ["awesome", "list", "collection", "interview", "prep", "learning"]

    # --- OFFICIAL DETECTION ---

    # Check if repo name closely matches conference name
    conf_key = max(conf_parts, key=len) if conf_parts else ""
    if len(conf_key) >= 4:
        # Exact match or very close
        if conf_key in repo_name or repo_name in conf_key:
            # Check for org indicators
            if any(kw in repo_name or kw in description for kw in official_keywords):
                return RepoAssessment(repo_name, url, stars, "official", "Official conference repo/site")
            if "org" in full_name.split("/")[0] or conf_key in full_name.split("/")[0]:
                return RepoAssessment(repo_name, url, stars, "official", f"Org repo: {full_name.split('/')[0]}")

    # Check topics for conference-specific tags
    for topic in topics:
        if conf_key in topic and len(conf_key) >= 4:
            if any(kw in description or kw in repo_name for kw in official_keywords):
                return RepoAssessment(repo_name, url, stars, "official", f"Tagged with {topic}")

    # --- RELATED DETECTION ---

    # Talks/demos from the conference
    for kw in related_keywords:
        if kw in repo_name or kw in description:
            if conf_key in repo_name or conf_key in description:
                return RepoAssessment(repo_name, url, stars, "related", f"Conference {kw}")

    # Year-specific repos (e.g., "kubecon-2025-demo")
    for year in ["2024", "2025", "2026"]:
        if year in repo_name and conf_key in repo_name:
            return RepoAssessment(repo_name, url, stars, "related", f"Year-specific repo ({year})")

    # Project using conference tech stack
    if any(conf_key in topic for topic in topics):
        return RepoAssessment(repo_name, url, stars, "related", "Related by topic")

    # --- NOISE DETECTION ---

    # Awesome lists and curated collections
    if "awesome" in repo_name or "awesome" in description[:50]:
        return RepoAssessment(repo_name, url, stars, "noise", "Awesome list")

    # Interview prep repos
    if any(kw in repo_name or kw in description for kw in noise_keywords):
        return RepoAssessment(repo_name, url, stars, "noise", "Generic learning/collection repo")

    # Very generic repos with low relevance signals
    if stars < 10 and not any(conf_key in s for s in [repo_name, description] + topics):
        return RepoAssessment(repo_name, url, stars, "noise", "Low relevance signals")

    # Default: weak relation if conference name appears somewhere
    if conf_key and len(conf_key) >= 4:
        if conf_key in description or conf_key in repo_name:
            return RepoAssessment(repo_name, url, stars, "related", "Mentions conference name")

    return RepoAssessment(repo_name, url, stars, "noise", "No clear connection")


def assess_conference(record: dict) -> ConferenceAssessment:
    """Assess all repos for a conference."""
    cfp_name = record.get("cfpName", "Unknown")
    repos = record.get("repos", [])
    total_stars = record.get("totalStars", 0)

    assessments = []
    for repo in repos:
        assessment = classify_repo(cfp_name, repo)
        assessments.append(assessment)

    official = sum(1 for a in assessments if a.category == "official")
    related = sum(1 for a in assessments if a.category == "related")
    noise = sum(1 for a in assessments if a.category == "noise")

    # Quality score: weighted average
    # Official=1.0, Related=0.5, Noise=0.0
    total = len(assessments) or 1
    quality = (official * 1.0 + related * 0.5) / total

    return ConferenceAssessment(
        cfp_name=cfp_name,
        total_repos=len(repos),
        total_stars=total_stars,
        repos=assessments,
        official_count=official,
        related_count=related,
        noise_count=noise,
        quality_score=quality
    )


def main():
    # Load Algolia credentials
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")

    if not app_id or not api_key:
        print("Error: ALGOLIA_APP_ID and ALGOLIA_API_KEY required in .env")
        return

    client = SearchClientSync(app_id, api_key)
    index_name = "cfps_intel_github"

    # Load test conferences
    fixtures_path = "/home/pln/Work/Perso/CallForPapersPlease/tests/fixtures/test_conferences.json"
    with open(fixtures_path) as f:
        test_data = json.load(f)
    test_conferences = {c["name"] for c in test_data["conferences"]}

    print(f"\n{'='*70}")
    print("GitHub Intel Index Audit")
    print(f"{'='*70}")
    print(f"Test set: {len(test_conferences)} conferences from fixtures")

    # Fetch all records from GitHub intel index
    all_records = []
    try:
        # Browse all records
        result = client.search_single_index(index_name, {
            "query": "",
            "hitsPerPage": 1000,
        })
        # Convert Pydantic Hit objects to dicts
        all_records = [hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit) for hit in result.hits]
        total_in_index = result.nb_hits
    except Exception as e:
        print(f"Error querying index: {e}")
        return

    print(f"Total records in index: {total_in_index}")

    # Find overlap with test set
    indexed_names = {r.get("cfpName") for r in all_records}
    overlap = test_conferences & indexed_names
    print(f"Test conferences with GitHub data: {len(overlap)}/{len(test_conferences)}")

    # === SUMMARY STATS ===
    print(f"\n{'='*70}")
    print("SUMMARY STATISTICS")
    print(f"{'='*70}")

    total_repos = sum(len(r.get("repos", [])) for r in all_records)
    total_stars = sum(r.get("totalStars", 0) for r in all_records)
    repos_per_conf = total_repos / len(all_records) if all_records else 0

    print(f"Conferences with GitHub data: {len(all_records)}")
    print(f"Total repos indexed: {total_repos}")
    print(f"Total stars: {total_stars:,}")
    print(f"Avg repos per conference: {repos_per_conf:.1f}")

    # Star distribution
    star_counts = []
    for r in all_records:
        for repo in r.get("repos", []):
            star_counts.append(repo.get("stars", 0))

    if star_counts:
        star_counts.sort(reverse=True)
        print(f"\nStar distribution:")
        print(f"  Max: {star_counts[0]:,}")
        print(f"  Median: {star_counts[len(star_counts)//2]:,}")
        print(f"  p90: {star_counts[int(len(star_counts)*0.1)]:,}")
        print(f"  >1000 stars: {sum(1 for s in star_counts if s >= 1000)}")
        print(f"  >100 stars: {sum(1 for s in star_counts if s >= 100)}")
        print(f"  <10 stars: {sum(1 for s in star_counts if s < 10)}")

    # === QUALITY ASSESSMENT ===
    print(f"\n{'='*70}")
    print("QUALITY ASSESSMENT (Sample of 20 conferences)")
    print(f"{'='*70}")

    # Sample 20 conferences that have GitHub data
    sample_records = [r for r in all_records if r.get("cfpName") in test_conferences]
    if len(sample_records) < 20:
        # Add more from index if not enough overlap
        extra = [r for r in all_records if r.get("cfpName") not in test_conferences]
        sample_records.extend(extra[:20-len(sample_records)])

    random.seed(42)  # Reproducible
    sample = random.sample(sample_records, min(20, len(sample_records)))

    assessments = []
    for record in sample:
        assessment = assess_conference(record)
        assessments.append(assessment)

    # Aggregate quality metrics
    total_official = sum(a.official_count for a in assessments)
    total_related = sum(a.related_count for a in assessments)
    total_noise = sum(a.noise_count for a in assessments)
    total_assessed = total_official + total_related + total_noise

    print(f"\nQuality breakdown across {len(assessments)} sampled conferences:")
    print(f"  Official repos: {total_official} ({100*total_official/total_assessed:.1f}%)")
    print(f"  Related repos:  {total_related} ({100*total_related/total_assessed:.1f}%)")
    print(f"  Noise repos:    {total_noise} ({100*total_noise/total_assessed:.1f}%)")

    avg_quality = sum(a.quality_score for a in assessments) / len(assessments)
    print(f"\nAverage quality score: {avg_quality:.2f} (0=all noise, 1=all official)")

    # === HIGH SIGNAL PATTERNS ===
    print(f"\n{'='*70}")
    print("HIGH-SIGNAL PATTERNS")
    print(f"{'='*70}")

    official_examples = []
    for a in assessments:
        for repo in a.repos:
            if repo.category == "official":
                official_examples.append((a.cfp_name, repo))

    print(f"\nOfficial repo examples ({len(official_examples)} found):")
    for conf, repo in official_examples[:5]:
        print(f"  - [{conf}] {repo.repo_name} ({repo.stars} stars)")
        print(f"    Reason: {repo.reason}")
        print(f"    URL: {repo.url}")

    # Related examples
    related_examples = []
    for a in assessments:
        for repo in a.repos:
            if repo.category == "related" and repo.stars >= 50:
                related_examples.append((a.cfp_name, repo))

    print(f"\nHigh-value related repos ({len(related_examples)} with 50+ stars):")
    for conf, repo in sorted(related_examples, key=lambda x: -x[1].stars)[:5]:
        print(f"  - [{conf}] {repo.repo_name} ({repo.stars} stars)")
        print(f"    Reason: {repo.reason}")

    # === LOW SIGNAL PATTERNS ===
    print(f"\n{'='*70}")
    print("LOW-SIGNAL PATTERNS (Noise)")
    print(f"{'='*70}")

    noise_reasons = Counter()
    for a in assessments:
        for repo in a.repos:
            if repo.category == "noise":
                noise_reasons[repo.reason] += 1

    print(f"\nNoise classification breakdown:")
    for reason, count in noise_reasons.most_common():
        print(f"  {reason}: {count}")

    noise_examples = []
    for a in assessments:
        for repo in a.repos:
            if repo.category == "noise":
                noise_examples.append((a.cfp_name, repo))

    print(f"\nNoise examples:")
    for conf, repo in noise_examples[:5]:
        print(f"  - [{conf}] {repo.repo_name} ({repo.stars} stars)")
        print(f"    Reason: {repo.reason}")

    # === TOP 5 BY QUALITY ===
    print(f"\n{'='*70}")
    print("TOP 5 CONFERENCES BY GITHUB QUALITY")
    print(f"{'='*70}")

    # Sort by quality score, then by total_stars
    top = sorted(assessments, key=lambda a: (a.quality_score, a.total_stars), reverse=True)[:5]

    for i, a in enumerate(top, 1):
        print(f"\n{i}. {a.cfp_name}")
        print(f"   Quality: {a.quality_score:.2f} | Repos: {a.total_repos} | Stars: {a.total_stars:,}")
        print(f"   Breakdown: {a.official_count} official, {a.related_count} related, {a.noise_count} noise")

    # === RECOMMENDATIONS ===
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    signal_ratio = (total_official + total_related) / total_assessed if total_assessed else 0

    if signal_ratio >= 0.6:
        verdict = "KEEP"
        reasoning = "Good signal-to-noise ratio"
    elif signal_ratio >= 0.3:
        verdict = "FILTER"
        reasoning = "Moderate noise - apply filtering"
    else:
        verdict = "DROP or MAJOR FILTER"
        reasoning = "High noise ratio"

    print(f"\nVerdict: {verdict}")
    print(f"Reasoning: {reasoning}")
    print(f"Signal ratio: {100*signal_ratio:.1f}% (official + related)")

    print(f"\nFiltering strategy suggestions:")
    print(f"  1. Star threshold: Repos with <10 stars account for {sum(1 for s in star_counts if s < 10)} repos")
    print(f"     Recommend: Filter repos with <5 stars unless official")
    print(f"  2. Topic matching: Require at least one topic overlap with conference theme")
    print(f"  3. Name matching: Boost repos where conference name appears in repo name or org")
    print(f"  4. Awesome list filter: Remove repos starting with 'awesome-'")
    print(f"  5. Keep high-star noise: Even 'noise' repos with 1000+ stars may be valuable context")

    # === DETAILED SAMPLE OUTPUT ===
    print(f"\n{'='*70}")
    print("DETAILED SAMPLE (3 conferences)")
    print(f"{'='*70}")

    for a in assessments[:3]:
        print(f"\n>>> {a.cfp_name}")
        print(f"    Total repos: {a.total_repos}, Stars: {a.total_stars}")
        print(f"    Quality: {a.quality_score:.2f}")
        print(f"    Repos:")
        for repo in a.repos[:5]:
            emoji = {"official": "🟢", "related": "🟡", "noise": "🔴"}[repo.category]
            print(f"      {emoji} {repo.repo_name} ({repo.stars}★) - {repo.reason}")


def audit_high_star_repos():
    """Deep dive on high-star repos - are they truly related or noise?"""
    app_id = os.environ.get("ALGOLIA_APP_ID")
    api_key = os.environ.get("ALGOLIA_API_KEY")
    client = SearchClientSync(app_id, api_key)

    result = client.search_single_index("cfps_intel_github", {
        "query": "",
        "hitsPerPage": 1000,
    })
    all_records = [hit.to_dict() if hasattr(hit, 'to_dict') else dict(hit) for hit in result.hits]

    # Collect all repos with 1000+ stars
    high_star_repos = []
    for record in all_records:
        cfp_name = record.get("cfpName", "Unknown")
        for repo in record.get("repos", []):
            stars = repo.get("stars", 0)
            if stars >= 1000:
                assessment = classify_repo(cfp_name, repo)
                high_star_repos.append({
                    "conference": cfp_name,
                    "repo": repo.get("full_name") or repo.get("name"),
                    "stars": stars,
                    "description": (repo.get("description") or "")[:80],
                    "category": assessment.category,
                    "reason": assessment.reason,
                })

    print(f"\n{'='*70}")
    print("HIGH-STAR REPOS DEEP DIVE (1000+ stars)")
    print(f"{'='*70}")
    print(f"\nTotal repos with 1000+ stars: {len(high_star_repos)}")

    # Group by category
    by_cat = defaultdict(list)
    for r in high_star_repos:
        by_cat[r["category"]].append(r)

    for cat in ["official", "related", "noise"]:
        repos = by_cat[cat]
        print(f"\n{cat.upper()} ({len(repos)} repos):")
        for r in sorted(repos, key=lambda x: -x["stars"])[:10]:
            print(f"  [{r['conference']}] {r['repo']} ({r['stars']:,}★)")
            print(f"    Desc: {r['description']}")
            print(f"    Why: {r['reason']}")


if __name__ == "__main__":
    import sys
    if "--high-star" in sys.argv:
        audit_high_star_repos()
    else:
        main()
